"""Por que cortar a fala em pedacos piorou a espera em vez de melhorar.

A medicao em fluxo mostrou o trabalho de CPU quase triplicando quando o audio foi
cortado em tres. Se o custo fosse proporcional ao audio, cortar seria neutro.
Este script mede o custo de transcrever 1, 2, 3 e 4 segundos do MESMO audio.

Se a curva for quase horizontal, o custo e por chamada, nao por segundo — e
transcrever enquanto o usuario fala nao tem como ajudar.
"""

from __future__ import annotations

import statistics
import time
import wave
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

VOZ = Path.home() / ".claude" / "clarisse" / "medicoes" / "voz_real"
TAXA = 16000
THREADS = 8
REPETICOES = 3

DICA = ("Projetos: omni-api, compliance-app, voz-ao-claude, consultor-financeiro, "
        "conciliacao-bancaria, velocimetro-tokens, cadeia-sequencial. Clarisse.")


def le_wav(caminho: Path) -> np.ndarray:
    with wave.open(str(caminho), "rb") as w:
        bruto = w.readframes(w.getnframes())
    return np.frombuffer(bruto, dtype=np.int16).astype(np.float32) / 32768.0


def custo(modelo: WhisperModel, trecho: np.ndarray) -> float:
    marcas = []
    for _ in range(REPETICOES):
        inicio = time.perf_counter()
        list(modelo.transcribe(trecho, language="pt", beam_size=1, vad_filter=False,
                               condition_on_previous_text=False, initial_prompt=DICA)[0])
        marcas.append(time.perf_counter() - inicio)
    return statistics.median(marcas)


def principal() -> None:
    onda = le_wav(VOZ / "compliance.wav")
    print(f"audio de referencia: {len(onda) / TAXA:.1f}s\n")

    modelo = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=THREADS)
    custo(modelo, onda[:TAXA])  # passada fria descartada

    print(f"{'trecho':>10}{'custo mediano':>16}{'custo por segundo de audio':>30}")
    print("-" * 56)
    for segundos in (0.5, 1.0, 2.0, 3.0, 4.0, 5.0):
        amostras = int(segundos * TAXA)
        if amostras > len(onda):
            continue
        medido = custo(modelo, onda[:amostras])
        print(f"{segundos:9.1f}s{medido:15.2f}s{medido / segundos:29.2f}s")


if __name__ == "__main__":
    principal()
