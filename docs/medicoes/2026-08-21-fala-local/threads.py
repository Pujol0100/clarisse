"""Verifica se dar mais threads ao faster-whisper derruba a latencia.

O i7-1355U tem 2 nucleos rapidos e 8 economicos. Mais threads pode ajudar ou
piorar, porque os nucleos economicos sao lentos e a sincronizacao custa.
"""

import statistics
import time
from pathlib import Path

from faster_whisper import WhisperModel
from faster_whisper.audio import decode_audio

AQUI = Path(__file__).parent
TAXA = 16000

ondas = [decode_audio(str(p), sampling_rate=TAXA) for p in sorted((AQUI / "audio").glob("fala_*.mp3"))]
duracao_total = sum(len(o) for o in ondas) / TAXA

print(f"{len(ondas)} frases, {duracao_total:.1f}s de audio no total\n")
print(f"{'modelo':10} {'threads':>8} {'latencia mediana':>18} {'x tempo real':>14}")
print("-" * 54)

for tamanho in ("base", "small"):
    for threads in (0, 2, 4, 8, 12):
        modelo = WhisperModel(tamanho, device="cpu", compute_type="int8", cpu_threads=threads)
        # Uma passada fria descartada, para nao medir a inicializacao.
        list(modelo.transcribe(ondas[0], language="pt", beam_size=1, vad_filter=False)[0])

        tempos = []
        for onda in ondas:
            inicio = time.perf_counter()
            list(modelo.transcribe(onda, language="pt", beam_size=1, vad_filter=False,
                                   condition_on_previous_text=False)[0])
            tempos.append(time.perf_counter() - inicio)

        mediana = statistics.median(tempos)
        rtf = sum(tempos) / duracao_total
        etiqueta = "auto" if threads == 0 else str(threads)
        print(f"{tamanho:10} {etiqueta:>8} {mediana:16.2f}s {rtf:13.2f}x")
        del modelo
