"""Ameaca a validade das duas medicoes anteriores: esta maquina e um i7 de 15 W.

Se o processador afunila por calor, uma estrategia medida depois de outra parece
pior sem ser pior, e a comparacao inteira desanda. Este script transcreve a mesma
frase inteira antes e depois de moer trabalho, sem mudar mais nada.

Se o custo do fim for parecido com o do inicio, a comparacao das estrategias vale.
Se subir muito, os numeros das estrategias medidas por ultimo estao inflados.
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

DICA = ("Projetos: omni-api, compliance-app, voz-ao-claude, consultor-financeiro, "
        "conciliacao-bancaria, velocimetro-tokens, cadeia-sequencial. Clarisse.")


def le_wav(caminho: Path) -> np.ndarray:
    with wave.open(str(caminho), "rb") as w:
        bruto = w.readframes(w.getnframes())
    return np.frombuffer(bruto, dtype=np.int16).astype(np.float32) / 32768.0


def uma_passada(modelo: WhisperModel, onda: np.ndarray) -> float:
    inicio = time.perf_counter()
    list(modelo.transcribe(onda, language="pt", beam_size=1, vad_filter=False,
                           condition_on_previous_text=False, initial_prompt=DICA)[0])
    return time.perf_counter() - inicio


def principal() -> None:
    onda = le_wav(VOZ / "compliance.wav")
    modelo = WhisperModel("small", device="cpu", compute_type="int8", cpu_threads=THREADS)
    uma_passada(modelo, onda)  # passada fria descartada

    frio = statistics.median([uma_passada(modelo, onda) for _ in range(3)])
    print(f"frio  (3 passadas): {frio:.2f}s")

    for volta in range(1, 5):
        for _ in range(8):
            uma_passada(modelo, onda)
        agora = statistics.median([uma_passada(modelo, onda) for _ in range(3)])
        print(f"depois de {volta * 8:2d} passadas: {agora:.2f}s  "
              f"({(agora / frio - 1) * 100:+.0f}% sobre o frio)")


if __name__ == "__main__":
    principal()
