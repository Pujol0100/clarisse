"""A gramatica restrita falhou. Testa o Vosk com vocabulario livre.

Hipotese: com o vocabulario inteiro disponivel, "clareza" e reconhecido como
"clareza" em vez de ser forcado a virar "clarisse". A troca e latencia: o
reconhecimento livre e mais caro que a gramatica de duas palavras.
"""

import json
import statistics
import time
from pathlib import Path

import numpy as np
from faster_whisper.audio import decode_audio
from vosk import KaldiRecognizer, Model, SetLogLevel

SetLogLevel(-1)
AQUI = Path(__file__).parent
TAXA = 16000

# O modelo de portugues pode escrever o nome de varias formas. Todas contam.
GATILHOS = ("clarisse", "clarice", "clarisses", "claris")

POSITIVOS = ["Clarisse.", "Clarisse, escuta.", "Clarisse, o que esta rolando?",
             "Ei Clarisse.", "Clarisse, me ajuda aqui."]
NEGATIVOS = ["Preciso revisar a clareza desse texto.", "A clareza do contrato ficou boa.",
             "Vou pedir esclarecimento ao juridico.", "Ela esclareceu tudo na reuniao.",
             "O clima esta claro hoje.", "Chama a Alice para a reuniao.",
             "A analise do contrato ficou pronta.", "Vou almocar e volto depois.",
             "Roda os testes do projeto agora.", "Manda o relatorio para o financeiro.",
             "Precisa classificar essa despesa.", "O cliente pediu esclarecimentos."]


def escuta_livre(modelo, onda: np.ndarray) -> tuple[bool, str, float]:
    pcm = (np.clip(onda, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
    inicio = time.perf_counter()
    rec = KaldiRecognizer(modelo, TAXA)
    rec.AcceptWaveform(pcm)
    texto = json.loads(rec.FinalResult()).get("text", "")
    decorrido = time.perf_counter() - inicio
    achou = any(g in texto.split() for g in GATILHOS)
    return achou, texto, decorrido


def principal() -> None:
    pasta = AQUI / "audio_ativacao"
    modelo = Model(str(AQUI / "modelos" / "vosk-model-small-pt-0.3"))

    pos = [decode_audio(str(pasta / f"pos_{i:02d}.mp3"), sampling_rate=TAXA)
           for i in range(len(POSITIVOS))]
    neg = [decode_audio(str(pasta / f"neg_{i:02d}.mp3"), sampling_rate=TAXA)
           for i in range(len(NEGATIVOS))]

    print("--- vocabulario livre: deve acordar ---")
    acertos, latencias = 0, []
    for texto, onda in zip(POSITIVOS, pos):
        achou, saida, t = escuta_livre(modelo, onda)
        latencias.append(t)
        acertos += achou
        print(f"  {'OK ' if achou else 'PERDEU'} {t * 1000:5.0f} ms  '{saida}'   <- {texto}")

    print("\n--- vocabulario livre: NAO deve acordar ---")
    falsos = 0
    for texto, onda in zip(NEGATIVOS, neg):
        achou, saida, t = escuta_livre(modelo, onda)
        latencias.append(t)
        falsos += achou
        print(f"  {'FALSO' if achou else 'ok   '} {t * 1000:5.0f} ms  '{saida}'   <- {texto}")

    print(f"\nacordou quando devia : {acertos}/{len(pos)}")
    print(f"acordou sem dever    : {falsos}/{len(neg)}")
    print(f"latencia mediana     : {statistics.median(latencias) * 1000:.0f} ms")
    print(f"latencia pior caso   : {max(latencias) * 1000:.0f} ms")


if __name__ == "__main__":
    principal()
