"""Compara motores de fala para texto locais nesta maquina.

Mede, para cada motor: tempo de carga do modelo, latencia por frase (primeira
chamada e mediana das seguintes), fator tempo real, taxa de erro de palavra e
memoria usada.

Nao instala nada no projeto. Roda dentro do venv descartavel do scratchpad.
"""

import gc
import json
import re
import statistics
import time
import unicodedata
from pathlib import Path

import jiwer
import numpy as np
import psutil

AQUI = Path(__file__).parent
AUDIO = AQUI / "audio"
MODELOS = AQUI / "modelos"
TAXA = 16000
REPETICOES = 3


def normaliza(texto: str) -> str:
    """Deixa os dois lados comparaveis: sem acento, sem pontuacao, minusculo."""
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", sem_acento.lower())).strip()


def carrega_audios() -> tuple[dict, dict, dict]:
    from faster_whisper.audio import decode_audio

    referencias = json.loads((AUDIO / "referencias.json").read_text(encoding="utf-8"))
    falas, ativacoes = {}, {}
    for arquivo in sorted(AUDIO.glob("*.mp3")):
        onda = decode_audio(str(arquivo), sampling_rate=TAXA)
        nome = arquivo.stem
        if nome.startswith("fala_"):
            falas[nome.removeprefix("fala_")] = onda
        else:
            ativacoes[nome.removeprefix("ativ_")] = onda
    return falas, ativacoes, referencias


def memoria_mb() -> float:
    return psutil.Process().memory_info().rss / (1024 * 1024)


def mede(funcao, onda) -> tuple[str, float, list[float]]:
    """Roda a transcricao uma vez fria e REPETICOES vezes quentes."""
    inicio = time.perf_counter()
    texto = funcao(onda)
    frio = time.perf_counter() - inicio

    quentes = []
    for _ in range(REPETICOES):
        inicio = time.perf_counter()
        funcao(onda)
        quentes.append(time.perf_counter() - inicio)
    return texto, frio, quentes


def testa_whisper(tamanho: str, falas: dict, referencias: dict) -> dict:
    from faster_whisper import WhisperModel

    antes = memoria_mb()
    inicio = time.perf_counter()
    modelo = WhisperModel(tamanho, device="cpu", compute_type="int8")
    carga = time.perf_counter() - inicio

    def transcreve(onda: np.ndarray) -> str:
        segmentos, _ = modelo.transcribe(
            onda,
            language="pt",
            beam_size=1,
            vad_filter=False,
            condition_on_previous_text=False,
        )
        return " ".join(s.text for s in segmentos)

    resultado = roda_motor(f"faster-whisper {tamanho}", transcreve, falas, referencias)
    resultado["carga_s"] = carga
    resultado["memoria_mb"] = memoria_mb() - antes

    del modelo
    gc.collect()
    return resultado


def testa_vosk(falas: dict, referencias: dict) -> dict:
    from vosk import KaldiRecognizer, Model, SetLogLevel

    SetLogLevel(-1)
    caminho = MODELOS / "vosk-model-small-pt-0.3"

    antes = memoria_mb()
    inicio = time.perf_counter()
    modelo = Model(str(caminho))
    carga = time.perf_counter() - inicio

    def transcreve(onda: np.ndarray) -> str:
        pcm = (np.clip(onda, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
        reconhecedor = KaldiRecognizer(modelo, TAXA)
        reconhecedor.AcceptWaveform(pcm)
        return json.loads(reconhecedor.FinalResult()).get("text", "")

    resultado = roda_motor("vosk small pt", transcreve, falas, referencias)
    resultado["carga_s"] = carga
    resultado["memoria_mb"] = memoria_mb() - antes
    resultado["_modelo_vosk"] = modelo
    return resultado


def roda_motor(nome: str, transcreve, falas: dict, referencias: dict) -> dict:
    print(f"\n--- {nome} ---")
    linhas, latencias, rtfs = [], [], []
    refs, hips = [], []

    for chave, onda in falas.items():
        duracao = len(onda) / TAXA
        texto, frio, quentes = mede(transcreve, onda)
        mediana = statistics.median(quentes)
        latencias.append(mediana)
        rtfs.append(mediana / duracao)

        ref = normaliza(referencias[chave])
        hip = normaliza(texto)
        refs.append(ref)
        hips.append(hip)
        erro = jiwer.wer(ref, hip)

        print(f"  {chave:6} audio {duracao:4.1f}s | frio {frio:5.2f}s | quente {mediana:5.2f}s "
              f"| erro {erro * 100:5.1f}%")
        print(f"         -> {hip}")
        linhas.append({"amostra": chave, "duracao_s": duracao, "frio_s": frio,
                       "quente_s": mediana, "wer": erro, "texto": hip})

    return {
        "motor": nome,
        "latencia_mediana_s": statistics.median(latencias),
        "latencia_max_s": max(latencias),
        "rtf_mediano": statistics.median(rtfs),
        "wer_global": jiwer.wer(refs, hips),
        "amostras": linhas,
    }


def testa_ativacao_vosk(modelo, ativacoes: dict) -> dict:
    """Palavra de ativacao: gramatica travada em uma frase so."""
    from vosk import KaldiRecognizer

    print("\n--- palavra de ativacao: vosk com gramatica restrita ---")
    gramatica = json.dumps(["clarisse", "[unk]"])
    acertos, falsos, latencias = [], [], []

    for chave, onda in ativacoes.items():
        pcm = (np.clip(onda, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
        inicio = time.perf_counter()
        reconhecedor = KaldiRecognizer(modelo, TAXA, gramatica)
        reconhecedor.AcceptWaveform(pcm)
        texto = json.loads(reconhecedor.FinalResult()).get("text", "")
        latencias.append(time.perf_counter() - inicio)

        detectou = "clarisse" in texto
        esperado = chave.startswith("nome")
        veredito = "ok" if detectou == esperado else "ERRO"
        if esperado:
            acertos.append(detectou)
        else:
            falsos.append(detectou)
        print(f"  {chave:12} esperado {'acordar' if esperado else 'ignorar':8} "
              f"detectou {str(detectou):5} {veredito:5} | {latencias[-1] * 1000:6.0f} ms | '{texto}'")

    return {
        "acerto_no_nome": f"{sum(acertos)}/{len(acertos)}",
        "falso_positivo": f"{sum(falsos)}/{len(falsos)}",
        "latencia_mediana_ms": statistics.median(latencias) * 1000,
    }


def principal() -> None:
    print("Carregando amostras...")
    falas, ativacoes, referencias = carrega_audios()
    print(f"{len(falas)} frases, {len(ativacoes)} amostras de ativacao, "
          f"{REPETICOES} repeticoes quentes por frase")

    resultados = []

    vosk_res = testa_vosk(falas, referencias)
    modelo_vosk = vosk_res.pop("_modelo_vosk")
    resultados.append(vosk_res)
    ativacao = testa_ativacao_vosk(modelo_vosk, ativacoes)
    del modelo_vosk
    gc.collect()

    for tamanho in ("tiny", "base", "small"):
        resultados.append(testa_whisper(tamanho, falas, referencias))

    print("\n" + "=" * 92)
    print(f"{'motor':22} {'carga':>7} {'latencia':>10} {'pior':>7} {'x tempo real':>13} "
          f"{'erro palavra':>13} {'RAM':>8}")
    print("=" * 92)
    for r in resultados:
        print(f"{r['motor']:22} {r['carga_s']:6.1f}s {r['latencia_mediana_s']:9.2f}s "
              f"{r['latencia_max_s']:6.2f}s {r['rtf_mediano']:12.2f}x "
              f"{r['wer_global'] * 100:12.1f}% {r['memoria_mb']:7.0f}M")
    print("=" * 92)
    print("\nPalavra de ativacao (vosk, gramatica restrita):")
    for k, v in ativacao.items():
        print(f"  {k:22} {v}")

    saida = AQUI / "resultado.json"
    saida.write_text(json.dumps({"transcricao": resultados, "ativacao": ativacao},
                                ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nDetalhe salvo em {saida.name}")


if __name__ == "__main__":
    principal()
