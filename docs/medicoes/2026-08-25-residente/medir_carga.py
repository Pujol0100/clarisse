"""Mede o que um servidor residente economiza por frase.

A pergunta: o desenho por tecla inicia o Python e carrega o modelo a cada frase.
Quanto isso custa, em cima dos ~3 s de transcricao que ja sao o piso medido?

Criterio de decisao, escrito antes de ver o numero: se o carregamento custar
menos de 0,5 s, o servidor residente nao se justifica.

Tudo na mesma execucao, porque esta maquina varia 40% entre execucoes.

Uso:
    venv\\Scripts\\python.exe medir_carga.py
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[2]
GRAVACOES = Path.home() / '.claude' / 'clarisse' / 'medicoes' / 'voz_real'
MODELO = 'small'
THREADS = 8
REPETICOES_INTERPRETADOR = 5

sys.path.insert(0, str(RAIZ))

from clarisse.ouvinte.dica import montar_dica  # noqa: E402

PROJETOS = [
    'omni-api', 'compliance-app', 'voz-ao-claude', 'consultor-financeiro',
    'conciliacao-bancaria', 'velocimetro-tokens', 'cadeia-sequencial',
]


def _medir_interpretador() -> float:
    """Quanto custa so subir o Python, sem importar nada pesado."""
    tempos = []
    for _ in range(REPETICOES_INTERPRETADOR):
        inicio = time.perf_counter()
        subprocess.run([sys.executable, '-c', 'pass'], check=True,
                       capture_output=True)
        tempos.append(time.perf_counter() - inicio)
    return statistics.median(tempos)


def _carregar(WhisperModel):
    inicio = time.perf_counter()
    modelo = WhisperModel(MODELO, device='cpu', compute_type='int8',
                          cpu_threads=THREADS)
    return modelo, time.perf_counter() - inicio


def main() -> int:
    if not GRAVACOES.is_dir():
        print(f'Gravacoes nao encontradas em {GRAVACOES}', file=sys.stderr)
        return 1

    dica = montar_dica(PROJETOS)
    print(f'Dica: {dica}\n')

    interpretador = _medir_interpretador()
    print(f'Interpretador Python sozinho: {interpretador:.2f} s (mediana de '
          f'{REPETICOES_INTERPRETADOR})')

    inicio = time.perf_counter()
    from faster_whisper import WhisperModel
    importacao = time.perf_counter() - inicio
    print(f'import faster_whisper:        {importacao:.2f} s')

    modelo, carga_fria = _carregar(WhisperModel)
    print(f'Carregar o modelo, 1a vez:    {carga_fria:.2f} s')

    _, carga_morna = _carregar(WhisperModel)
    print(f'Carregar o modelo, 2a vez:    {carga_morna:.2f} s\n')

    wavs = sorted(GRAVACOES.glob('*.wav'))
    transcricoes = []
    for wav in wavs:
        inicio = time.perf_counter()
        segmentos, _ = modelo.transcribe(
            str(wav), language='pt', beam_size=1, vad_filter=False,
            condition_on_previous_text=False, initial_prompt=dica)
        texto = ' '.join(s.text for s in segmentos).strip()
        gasto = time.perf_counter() - inicio
        transcricoes.append({'arquivo': wav.name, 'segundos': gasto,
                             'texto': texto})
        print(f'  {wav.name:20s} {gasto:5.2f} s  {texto}')

    tempos = [t['segundos'] for t in transcricoes]
    mediana = statistics.median(tempos)

    por_tecla = interpretador + importacao + carga_fria
    print(f'\nTranscricao com o modelo ja carregado: mediana {mediana:.2f} s')
    print(f'Custo fixo pago a cada tecla no desenho original: {por_tecla:.2f} s')
    print(f'  = interpretador {interpretador:.2f} + import {importacao:.2f} '
          f'+ carga {carga_fria:.2f}')
    print(f'\nPor frase: {por_tecla + mediana:.2f} s por tecla contra '
          f'{mediana:.2f} s residente')

    veredito = 'residente se justifica' if por_tecla >= 0.5 else 'residente NAO se justifica'
    print(f'Criterio (0,5 s): {veredito}')

    resultado = {
        'modelo': MODELO,
        'threads': THREADS,
        'interpretador_s': interpretador,
        'import_s': importacao,
        'carga_fria_s': carga_fria,
        'carga_morna_s': carga_morna,
        'custo_fixo_por_tecla_s': por_tecla,
        'transcricao_mediana_s': mediana,
        'transcricoes': transcricoes,
        'veredito': veredito,
    }
    (AQUI / 'resultado.json').write_text(
        json.dumps(resultado, indent=2, ensure_ascii=False), encoding='utf-8')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
