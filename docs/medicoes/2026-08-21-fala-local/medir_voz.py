"""Mede a transcricao da SUA voz, e responde a pergunta que decide o projeto:
quanto tempo voce espera depois de soltar a tecla?

Testa quatro configuracoes sobre as mesmas gravacoes:
  base  sem dica  |  base  com dica dos nomes de projeto
  small sem dica  |  small com dica dos nomes de projeto

A "dica" e o initial_prompt do whisper. Ela existe porque a medicao com voz
sintetica mostrou o motor rapido destruindo nome de projeto: omni-api virou
"homem in api" todas as vezes. Se a dica consertar isso, o motor rapido volta
para a mesa - e ele e tres vezes mais rapido.
"""

import json
import re
import statistics
import time
import unicodedata
import wave
from pathlib import Path

import jiwer
import numpy as np
from faster_whisper import WhisperModel

AQUI = Path(__file__).parent
VOZ = AQUI / "voz_real"
TAXA = 16000
THREADS = 8  # melhor caso medido na varredura de threads

DICA = ("Projetos: omni-api, compliance-app, voz-ao-claude, consultor-financeiro, "
        "conciliacao-bancaria, velocimetro-tokens, cadeia-sequencial. Clarisse.")

CONFIGS = [
    ("base  sem dica", "base", None),
    ("base  com dica", "base", DICA),
    ("small sem dica", "small", None),
    ("small com dica", "small", DICA),
]


def normaliza(texto: str) -> str:
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", sem_acento.lower())).strip()


def le_wav(caminho: Path) -> np.ndarray:
    with wave.open(str(caminho), "rb") as w:
        bruto = w.readframes(w.getnframes())
    return np.frombuffer(bruto, dtype=np.int16).astype(np.float32) / 32768.0


def principal() -> None:
    if not VOZ.exists():
        print("Nao achei as gravacoes. Rode o gravar.py primeiro.")
        return

    referencias = json.loads((VOZ / "referencias.json").read_text(encoding="utf-8"))
    arquivos = sorted(VOZ.glob("*.wav"))
    if not arquivos:
        print("Nenhum arquivo de voz encontrado.")
        return

    ondas = {p.stem: le_wav(p) for p in arquivos}
    duracoes = {k: len(o) / TAXA for k, o in ondas.items()}
    total = sum(duracoes.values())
    print(f"{len(ondas)} frases da sua voz, {total:.1f}s de audio no total")
    print(f"duracao por frase: {min(duracoes.values()):.1f}s a {max(duracoes.values()):.1f}s\n")

    resumo = []

    for rotulo, tamanho, dica in CONFIGS:
        modelo = WhisperModel(tamanho, device="cpu", compute_type="int8", cpu_threads=THREADS)
        # Passada fria descartada: mede-se o uso, nao a inicializacao.
        list(modelo.transcribe(next(iter(ondas.values())), language="pt", beam_size=1)[0])

        print(f"--- {rotulo} ---")
        esperas, refs, hips = [], [], []

        for chave, onda in ondas.items():
            inicio = time.perf_counter()
            segmentos, _ = modelo.transcribe(
                onda,
                language="pt",
                beam_size=1,
                vad_filter=False,
                condition_on_previous_text=False,
                initial_prompt=dica,
            )
            texto = " ".join(s.text for s in segmentos)
            espera = time.perf_counter() - inicio
            esperas.append(espera)

            ref = normaliza(referencias.get(chave, ""))
            hip = normaliza(texto)
            refs.append(ref)
            hips.append(hip)
            erro = jiwer.wer(ref, hip) if ref else float("nan")

            print(f"  {chave:12} falou {duracoes[chave]:4.1f}s | esperou {espera:5.2f}s "
                  f"| erro {erro * 100:5.1f}%")
            print(f"               -> {hip}")

        resumo.append({
            "config": rotulo,
            "espera_mediana": statistics.median(esperas),
            "espera_pior": max(esperas),
            "wer": jiwer.wer(refs, hips),
            "rtf": sum(esperas) / total,
        })
        print()
        del modelo

    print("=" * 78)
    print(f"{'configuracao':16} {'espera mediana':>15} {'pior espera':>13} "
          f"{'x tempo real':>13} {'erro palavra':>14}")
    print("=" * 78)
    for r in resumo:
        print(f"{r['config']:16} {r['espera_mediana']:14.2f}s {r['espera_pior']:12.2f}s "
              f"{r['rtf']:12.2f}x {r['wer'] * 100:13.1f}%")
    print("=" * 78)
    print("\n'espera' e o tempo entre voce soltar a tecla e o texto estar pronto.")

    (AQUI / "resultado_voz_real.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Detalhe salvo em resultado_voz_real.json")


if __name__ == "__main__":
    principal()
