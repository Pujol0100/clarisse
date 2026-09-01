"""Le o diario do ditado e produz os numeros que decidem o desenho do Agente.

Roda sobre `~/.claude/clarisse/ouvinte/diario.jsonl`, que so existe se
`ouvinte.diario` estiver ligado no config. Nada aqui manda dado para lugar
nenhum: le arquivo local, imprime na tela, grava o resultado ao lado.

A taxa de correcao NAO e taxa de erro do motor. Ela mede quanto o usuario mexeu
no texto antes de enviar, e isso sobe com mudanca de ideia e desce com erro que
ele aceitou. Ler junto com o numero de laboratorio de 26/08: 10,6% de erro por
palavra nas oito gravacoes de voz real.

Uso:
    python docs/medicoes/2026-09-01-ditado-real/analisar.py
"""

from __future__ import annotations

import json
import statistics
import sys
import unicodedata
from collections import Counter
from pathlib import Path

DIARIO = Path.home() / '.claude' / 'clarisse' / 'ouvinte' / 'diario.jsonl'
SAIDA = Path(__file__).parent / 'resultado.json'
AMOSTRA_MINIMA = 40


def normaliza(texto: str) -> str:
    """Tira acento, pontuacao e caixa: erro de acento nao e erro de palavra."""
    sem_acento = ''.join(
        c
        for c in unicodedata.normalize('NFD', texto.lower())
        if unicodedata.category(c) != 'Mn'
    )
    return ''.join(c if c.isalnum() or c.isspace() else ' ' for c in sem_acento)


def script_de_edicao(ref: list[str], hip: list[str]) -> tuple[int, int, int]:
    """Devolve (trocadas, removidas, acrescentadas) entre as duas listas.

    Separar os tres importa mais que a distancia total: acrescentar uma frase
    digitada no fim nao e o motor ter errado, e somar tudo num numero so faria
    "digitei mais" parecer transcricao ruim.
    """
    n, m = len(ref), len(hip)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(
                d[i - 1][j] + 1,
                d[i][j - 1] + 1,
                d[i - 1][j - 1] + (ref[i - 1] != hip[j - 1]),
            )

    trocadas = removidas = acrescentadas = 0
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and ref[i - 1] == hip[j - 1] and d[i][j] == d[i - 1][j - 1]:
            i, j = i - 1, j - 1
        elif i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + 1:
            trocadas += 1
            i, j = i - 1, j - 1
        elif i > 0 and d[i][j] == d[i - 1][j] + 1:
            removidas += 1
            i -= 1
        else:
            acrescentadas += 1
            j -= 1
    return trocadas, removidas, acrescentadas


def palavras_trocadas(ref: list[str], hip: list[str]) -> list[tuple[str, str]]:
    """As duplas (o que o motor ouviu, o que o usuario pos no lugar).

    E o que realimenta a dica: saber que `omni` vira `homem` toda vez vale mais
    que a media, porque diz o que acrescentar ao vocabulario.
    """
    pares = []
    i = j = 0
    while i < len(ref) and j < len(hip):
        if ref[i] == hip[j]:
            i, j = i + 1, j + 1
        else:
            pares.append((ref[i], hip[j]))
            i, j = i + 1, j + 1
    return pares


def _quantil(valores: list[float], q: float) -> float:
    ordenado = sorted(valores)
    k = min(int(q * len(ordenado)), len(ordenado) - 1)
    return ordenado[k]


def resumir(ditados: dict, enviados: dict) -> dict | None:
    """Junta as duas metades e devolve os numeros. None se nao ha par nenhum."""
    pares = [(ditados[i], enviados[i]) for i in ditados if i in enviados]
    abandonados = [d for i, d in ditados.items() if i not in enviados]
    if not pares:
        return None

    correcoes, latencias, revisoes = [], [], []
    trocas: Counter = Counter()
    for ditado, enviado in pares:
        ref = normaliza(ditado.get('bruto', '')).split()
        hip = normaliza(enviado.get('enviado', '')).split()
        if not ref:
            continue
        trocadas, removidas, _acrescentadas = script_de_edicao(ref, hip)
        # Acrescimo fica de fora: digitar mais depois nao e o motor ter errado.
        correcoes.append((trocadas + removidas) / len(ref))
        latencias.append(float(ditado.get('segundos_transcricao', 0)))
        revisoes.append(float(enviado.get('segundos_ate_enviar', 0)))
        for ouvida, posta in palavras_trocadas(ref, hip):
            trocas[f'{ouvida} -> {posta}'] += 1

    if not correcoes:
        return None

    return {
        'amostra': len(correcoes),
        'abandonados': len(abandonados),
        'taxa_abandono': round(len(abandonados) / len(ditados), 3),
        'correcao_mediana': round(statistics.median(correcoes), 3),
        'correcao_media': round(statistics.fmean(correcoes), 3),
        'correcao_p95': round(_quantil(correcoes, 0.95), 3),
        'latencia_mediana_s': round(statistics.median(latencias), 2),
        'latencia_p95_s': round(_quantil(latencias, 0.95), 2),
        'revisao_mediana_s': round(statistics.median(revisoes), 1),
        'trocas_frequentes': trocas.most_common(10),
    }


def ler_diario(caminho: Path) -> tuple[dict, dict]:
    ditados: dict[str, dict] = {}
    enviados: dict[str, dict] = {}
    for linha in caminho.read_text(encoding='utf-8').splitlines():
        if not linha.strip():
            continue
        try:
            reg = json.loads(linha)
        except json.JSONDecodeError:
            # Linha truncada por queda no meio da escrita nao derruba a analise.
            continue
        if reg.get('tipo') == 'ditado' and reg.get('id'):
            ditados[reg['id']] = reg
        elif reg.get('tipo') == 'enviado' and reg.get('id'):
            enviados[reg['id']] = reg
    return ditados, enviados


def principal() -> None:
    if not DIARIO.exists():
        print(f'diario nao existe em {DIARIO}')
        print('ligue "diario": true no bloco "ouvinte" do config.json e dite algumas vezes')
        sys.exit(1)

    ditados, enviados = ler_diario(DIARIO)
    resultado = resumir(ditados, enviados)

    print(f'ditados registrados: {len(ditados)}')
    print(f'abandonados:         {len(ditados) - len(enviados)}')
    if resultado is None:
        print('nenhum par completo ainda - nada para medir')
        sys.exit(1)

    print()
    print(f"amostra            {resultado['amostra']} pares")
    print(f"correcao mediana   {resultado['correcao_mediana']:.1%}")
    print(f"correcao media     {resultado['correcao_media']:.1%}")
    print(f"correcao p95       {resultado['correcao_p95']:.1%}")
    print(f"abandono           {resultado['taxa_abandono']:.1%}")
    print(f"latencia mediana   {resultado['latencia_mediana_s']:.2f} s")
    print(f"latencia p95       {resultado['latencia_p95_s']:.2f} s")
    print(f"revisao mediana    {resultado['revisao_mediana_s']:.1f} s")
    print()
    print('palavras mais trocadas:')
    for troca, quantas in resultado['trocas_frequentes']:
        print(f'  {quantas:3d}x  {troca}')

    if resultado['amostra'] < AMOSTRA_MINIMA:
        print()
        print(
            f"AVISO: {resultado['amostra']} pares. O criterio pede "
            f'{AMOSTRA_MINIMA}. Continue coletando antes de decidir.'
        )

    SAIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\nresultado em {SAIDA}')


if __name__ == '__main__':
    principal()
