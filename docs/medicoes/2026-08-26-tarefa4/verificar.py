"""Verificacao de fronteira da Tarefa 4: o codigo que vai rodar de verdade.

As medicoes anteriores chamaram o `faster_whisper` na mao, com a dica escrita
literalmente no script. Isto aqui chama `clarisse.ouvinte.motor.transcrever` e
monta a dica com `clarisse.ouvinte.dica`, a partir dos projetos que existem
nesta maquina. E o unico jeito de saber que o caminho instalado funciona.

Reaproveita as oito gravacoes da voz real de 21/08. Nao pedir gravacao nova.

Rodar:
    python docs\\medicoes\\2026-08-26-tarefa4\\verificar.py
"""

import json
import re
import sys
import time
import unicodedata
import wave
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))

from clarisse.ouvinte.dica import montar_dica, projetos_da_maquina  # noqa: E402
from clarisse.ouvinte.motor import abrir_motor, transcrever  # noqa: E402

VOZ = Path.home() / '.claude' / 'clarisse' / 'medicoes' / 'voz_real'
PROJETOS = Path.home() / '.claude' / 'projects'
TAXA = 16000


def normaliza(texto: str) -> str:
    sem_acento = ''.join(
        c for c in unicodedata.normalize('NFKD', texto) if not unicodedata.combining(c)
    )
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9]+', ' ', sem_acento.lower())).strip()


def erro_de_palavras(referencia: str, saida: str) -> float:
    """Distancia de edicao por palavra, dividida pelo tamanho da referencia."""
    ref = normaliza(referencia).split()
    hip = normaliza(saida).split()
    if not ref:
        return 0.0

    anterior = list(range(len(hip) + 1))
    for i, palavra in enumerate(ref, 1):
        atual = [i]
        for j, outra in enumerate(hip, 1):
            atual.append(
                min(anterior[j] + 1, atual[j - 1] + 1, anterior[j - 1] + (palavra != outra))
            )
        anterior = atual
    return anterior[-1] / len(ref)


def le_wav(caminho: Path) -> np.ndarray:
    with wave.open(str(caminho), 'rb') as arquivo:
        bruto = arquivo.readframes(arquivo.getnframes())
    return np.frombuffer(bruto, dtype=np.int16).astype(np.float32) / 32768.0


def principal() -> None:
    if not VOZ.exists():
        print('Nao achei as gravacoes da voz real.')
        return

    dica = montar_dica(projetos_da_maquina(PROJETOS))
    print(f'dica: {dica}\n')

    referencias = json.loads((VOZ / 'referencias.json').read_text(encoding='utf-8'))
    ondas = {p.stem: le_wav(p) for p in sorted(VOZ.glob('*.wav'))}

    inicio = time.perf_counter()
    motor = abrir_motor()
    carga = time.perf_counter() - inicio
    print(f'carga do modelo: {carga:.2f}s\n')

    linhas, esperas, erros = [], [], []
    for nome, onda in ondas.items():
        marca = time.perf_counter()
        saida = transcrever(motor, onda, dica=dica)
        espera = time.perf_counter() - marca

        referencia = referencias.get(nome, '')
        erro = erro_de_palavras(referencia, saida)
        esperas.append(espera)
        erros.append(erro)
        linhas.append(
            {
                'frase': nome,
                'duracao_s': round(len(onda) / TAXA, 2),
                'espera_s': round(espera, 2),
                'erro': round(erro, 3),
                'referencia': referencia,
                'saida': saida,
            }
        )
        print(f'{nome:12s} {espera:6.2f}s  erro {erro:5.1%}  {saida}')

    esperas.sort()
    meio = esperas[len(esperas) // 2]
    total_erro = sum(erros) / len(erros)
    print(f'\nespera mediana: {meio:.2f}s   erro medio: {total_erro:.1%}')

    (Path(__file__).parent / 'resultado.json').write_text(
        json.dumps(
            {
                'dica': dica,
                'carga_s': round(carga, 2),
                'espera_mediana_s': round(meio, 2),
                'erro_medio': round(total_erro, 3),
                'frases': linhas,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )


if __name__ == '__main__':
    principal()
