"""Separa o efeito das threads da deriva da maquina, intercalando as medidas.

A medicao sequencial de 25/08 nao serve: a variacao dentro de uma configuracao
(23 s a 116 s em threads=12) foi quase tao grande quanto entre configuracoes.
Medir 2 e depois 12 confunde o efeito das threads com o que a maquina estava
fazendo naquele minuto.

Aqui as duas configuracoes se alternam a cada rodada. Se a diferenca sobreviver
a intercalacao, e efeito das threads. Se sumir, era deriva.

Uso:
    venv\\Scripts\\python.exe medir_intercalado.py
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
CONFIGURACOES = (2, 8)
RODADAS = 5

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

    print('Carregando os dois modelos antes de medir...', flush=True)
    modelos = {}
    for threads in CONFIGURACOES:
        modelos[threads] = WhisperModel(MODELO, device='cpu',
                                        compute_type='int8',
                                        cpu_threads=threads)
    print('Prontos. Intercalando.\n', flush=True)

    tempos = {t: [] for t in CONFIGURACOES}
    for rodada in range(1, RODADAS + 1):
        linha = [f'rodada {rodada}:']
        for threads in CONFIGURACOES:
            inicio = time.perf_counter()
            segmentos, _ = modelos[threads].transcribe(
                str(wav), language='pt', beam_size=1, vad_filter=False,
                condition_on_previous_text=False, initial_prompt=dica)
            ''.join(s.text for s in segmentos)
            gasto = time.perf_counter() - inicio
            tempos[threads].append(gasto)
            linha.append(f'threads={threads} {gasto:6.2f} s')
        print('  '.join(linha), flush=True)

    print()
    medianas = {}
    for threads in CONFIGURACOES:
        serie = tempos[threads]
        medianas[threads] = statistics.median(serie)
        espalhamento = max(serie) / min(serie)
        print(f'threads={threads:2d}  mediana {medianas[threads]:6.2f} s  '
              f'menor {min(serie):6.2f}  maior {max(serie):6.2f}  '
              f'espalhamento {espalhamento:.1f}x')

    razao = medianas[CONFIGURACOES[1]] / medianas[CONFIGURACOES[0]]
    espalhamento_maximo = max(
        max(tempos[t]) / min(tempos[t]) for t in CONFIGURACOES)

    print(f'\nEfeito das threads (mediana 8 / mediana 2): {razao:.1f}x')
    print(f'Ruido da maquina (maior espalhamento interno): '
          f'{espalhamento_maximo:.1f}x')

    if razao > espalhamento_maximo:
        print('Veredito: o efeito das threads e maior que o ruido. Sinal real.')
    else:
        print('Veredito: o ruido da maquina engole o efeito das threads. '
              'Esta medicao nao decide o numero de threads.')

    (AQUI / 'resultado_intercalado.json').write_text(
        json.dumps({'amostra': AMOSTRA, 'modelo': MODELO, 'rodadas': RODADAS,
                    'tempos_s': tempos, 'medianas_s': medianas,
                    'razao': razao, 'espalhamento_maximo': espalhamento_maximo},
                   indent=2, ensure_ascii=False), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
