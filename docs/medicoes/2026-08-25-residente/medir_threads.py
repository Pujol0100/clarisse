"""Mede o efeito de cpu_threads nesta maquina, e o quanto a carga de fundo custa.

Motivo: a medicao de 25/08 deu mediana de 11,97 s por frase, contra os 3,21 s
registrados em 22/08. A maquina e um i7-1355U (2 nucleos rapidos, 8 economicos,
1,7 GHz) e estava a 68% de carga, com o OneDrive sincronizando e varias sessoes
do Claude Code abertas.

A hipotese: com cpu_threads=8 o trabalho cai nos nucleos economicos, e a carga de
fundo piora isso. Se for verdade, o numero de threads certo nesta maquina e menor
que 8, e o Ouvinte precisa dizer isso no config.

Uso:
    venv\\Scripts\\python.exe medir_threads.py
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[2]
GRAVACOES = Path.home() / '.claude' / 'clarisse' / 'medicoes' / 'voz_real'
AMOSTRA = 'voz.wav'
MODELO = 'small'
CONFIGURACOES = (2, 4, 6, 8, 12)
REPETICOES = 3

sys.path.insert(0, str(RAIZ))

from clarisse.ouvinte.dica import montar_dica  # noqa: E402

PROJETOS = [
    'omni-api', 'compliance-app', 'voz-ao-claude', 'consultor-financeiro',
    'conciliacao-bancaria', 'velocimetro-tokens', 'cadeia-sequencial',
]


def main() -> int:
    wav = GRAVACOES / AMOSTRA
    if not wav.is_file():
        print(f'Amostra nao encontrada: {wav}', file=sys.stderr)
        return 1

    from faster_whisper import WhisperModel

    dica = montar_dica(PROJETOS)
    medidas = []

    for threads in CONFIGURACOES:
        inicio = time.perf_counter()
        modelo = WhisperModel(MODELO, device='cpu', compute_type='int8',
                              cpu_threads=threads)
        carga = time.perf_counter() - inicio

        tempos = []
        texto = ''
        for _ in range(REPETICOES):
            inicio = time.perf_counter()
            segmentos, _ = modelo.transcribe(
                str(wav), language='pt', beam_size=1, vad_filter=False,
                condition_on_previous_text=False, initial_prompt=dica)
            texto = ' '.join(s.text for s in segmentos).strip()
            tempos.append(time.perf_counter() - inicio)

        mediana = statistics.median(tempos)
        medidas.append({'threads': threads, 'carga_s': carga,
                        'mediana_s': mediana, 'tempos_s': tempos,
                        'texto': texto})
        print(f'threads={threads:2d}  carga {carga:5.2f} s  '
              f'transcricao mediana {mediana:5.2f} s  '
              f'({", ".join(f"{t:.2f}" for t in tempos)})')
        del modelo

    melhor = min(medidas, key=lambda m: m['mediana_s'])
    pior = max(medidas, key=lambda m: m['mediana_s'])
    print(f'\nMelhor: threads={melhor["threads"]} com {melhor["mediana_s"]:.2f} s')
    print(f'Pior:   threads={pior["threads"]} com {pior["mediana_s"]:.2f} s')
    print(f'Diferenca: {pior["mediana_s"] / melhor["mediana_s"]:.1f}x')
    print(f'\nTexto: {melhor["texto"]}')

    (AQUI / 'resultado_threads.json').write_text(
        json.dumps({'amostra': AMOSTRA, 'modelo': MODELO, 'medidas': medidas},
                   indent=2, ensure_ascii=False), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
