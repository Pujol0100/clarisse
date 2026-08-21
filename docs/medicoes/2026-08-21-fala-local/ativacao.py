"""Tenta separar o acerto do falso positivo na palavra de ativacao.

O teste anterior mostrou "clareza" acordando a Clarisse. Aqui testo tres defesas:
confianca por palavra, frase de ativacao mais longa, e as duas juntas.
"""

import asyncio
import json
import statistics
import time
from pathlib import Path

import edge_tts
import numpy as np
from faster_whisper.audio import decode_audio
from vosk import KaldiRecognizer, Model, SetLogLevel

SetLogLevel(-1)
AQUI = Path(__file__).parent
TAXA = 16000
VOZ = "pt-BR-ThalitaMultilingualNeural"

# Negativos de verdade: palavras e frases que colidem com "Clarisse" em portugues,
# mais fala corriqueira de trabalho. Se qualquer uma acordar, o desenho falhou.
NEGATIVOS = [
    "Preciso revisar a clareza desse texto.",
    "A clareza do contrato ficou boa.",
    "Vou pedir esclarecimento ao juridico.",
    "Ela esclareceu tudo na reuniao.",
    "O clima esta claro hoje.",
    "Chama a Alice para a reuniao.",
    "A analise do contrato ficou pronta.",
    "Vou almocar e volto depois.",
    "Roda os testes do projeto agora.",
    "Manda o relatorio para o financeiro.",
    "Precisa classificar essa despesa.",
    "O cliente pediu esclarecimentos.",
]

POSITIVOS = [
    "Clarisse.",
    "Clarisse, escuta.",
    "Clarisse, o que esta rolando?",
    "Ei Clarisse.",
    "Clarisse, me ajuda aqui.",
]


async def gera(textos: list[str], prefixo: str) -> list[Path]:
    destino = AQUI / "audio_ativacao"
    destino.mkdir(exist_ok=True)
    caminhos = []
    for i, texto in enumerate(textos):
        caminho = destino / f"{prefixo}_{i:02d}.mp3"
        if not caminho.exists():
            await edge_tts.Communicate(texto, VOZ).save(str(caminho))
        caminhos.append(caminho)
    return caminhos


def escuta(modelo, onda: np.ndarray, gramatica: str) -> tuple[bool, float, str]:
    """Devolve (detectou, confianca da palavra do gatilho, texto)."""
    pcm = (np.clip(onda, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
    rec = KaldiRecognizer(modelo, TAXA, gramatica)
    rec.SetWords(True)
    rec.AcceptWaveform(pcm)
    saida = json.loads(rec.FinalResult())
    texto = saida.get("text", "")
    palavras = saida.get("result", [])
    confianca = max(
        (p.get("conf", 0.0) for p in palavras if p.get("word") == "clarisse"), default=0.0
    )
    return "clarisse" in texto, confianca, texto


def avalia(nome: str, modelo, positivos, negativos, gramatica: str, limiar: float) -> None:
    acertos = falhas = 0
    detalhe_falso = []
    latencias = []

    for onda in positivos:
        inicio = time.perf_counter()
        detectou, conf, _ = escuta(modelo, onda, gramatica)
        latencias.append(time.perf_counter() - inicio)
        if detectou and conf >= limiar:
            acertos += 1

    for texto, onda in negativos:
        detectou, conf, saida = escuta(modelo, onda, gramatica)
        if detectou and conf >= limiar:
            falhas += 1
            detalhe_falso.append(f"{texto}  (conf {conf:.2f}, ouviu '{saida}')")

    print(f"\n{nome}")
    print(f"  acordou quando devia : {acertos}/{len(positivos)}")
    print(f"  acordou sem dever    : {falhas}/{len(negativos)}")
    print(f"  latencia mediana     : {statistics.median(latencias) * 1000:.0f} ms")
    for d in detalhe_falso:
        print(f"    falso -> {d}")


async def principal() -> None:
    print("Gerando amostras de ativacao...")
    caminhos_pos = await gera(POSITIVOS, "pos")
    caminhos_neg = await gera(NEGATIVOS, "neg")

    positivos = [decode_audio(str(p), sampling_rate=TAXA) for p in caminhos_pos]
    negativos = [(t, decode_audio(str(p), sampling_rate=TAXA))
                 for t, p in zip(NEGATIVOS, caminhos_neg)]

    print(f"{len(positivos)} positivos, {len(negativos)} negativos\n")
    modelo = Model(str(AQUI / "modelos" / "vosk-model-small-pt-0.3"))

    so_nome = json.dumps(["clarisse", "[unk]"])

    avalia("1) so a palavra, sem limiar de confianca", modelo,
           positivos, negativos, so_nome, limiar=0.0)

    for limiar in (0.5, 0.8, 0.9, 0.95):
        avalia(f"2) so a palavra, confianca minima {limiar}", modelo,
               positivos, negativos, so_nome, limiar=limiar)

    # Mostra a distribuicao das confiancas, para saber se existe corte possivel.
    print("\n--- confianca da palavra 'clarisse' em cada amostra ---")
    for rotulo, amostras in (("POSITIVO", [(t, o) for t, o in zip(POSITIVOS, positivos)]),
                             ("negativo", negativos)):
        for texto, onda in amostras:
            detectou, conf, saida = escuta(modelo, onda, so_nome)
            marca = "detectou" if detectou else "        "
            print(f"  {rotulo:8} conf {conf:5.2f} {marca}  {texto}")


if __name__ == "__main__":
    asyncio.run(principal())
