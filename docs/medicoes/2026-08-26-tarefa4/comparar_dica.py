"""A dica montada da maquina ajuda, ou atrapalha?

A verificacao da Tarefa 4 deu 26,3% de erro, contra os 9,2% de 21/08. A diferenca
nao esta no motor: esta na dica. Em 21/08 ela era uma lista escrita a mao com os
sete nomes que aparecem nas frases; hoje ela vem dos projetos que existem na
maquina, e esses sao outros.

Isto responde a unica pergunta que decide a Tarefa 1: com a dica de hoje, o erro
e menor ou maior do que sem dica nenhuma?

As duas configuracoes andam intercaladas e a ordem inverte a cada frase. E a
regra que 25/08 deixou: nesta maquina, configuracao medida em sequencia nao se
compara, porque a capacidade sobrando varia 6x ao longo de meia hora.

Rodar:
    python docs\\medicoes\\2026-08-26-tarefa4\\comparar_dica.py
"""

import json
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))

from clarisse.ouvinte.dica import montar_dica  # noqa: E402
from clarisse.ouvinte.motor import abrir_motor, transcrever  # noqa: E402
from verificar import VOZ, erro_de_palavras, le_wav, projetos_da_maquina  # noqa: E402

MAO = (
    'Projetos: omni-api, compliance-app, voz-ao-claude, consultor-financeiro, '
    'conciliacao-bancaria, velocimetro-tokens, cadeia-sequencial. Clarisse.'
)


def principal() -> None:
    referencias = json.loads((VOZ / 'referencias.json').read_text(encoding='utf-8'))
    ondas = {p.stem: le_wav(p) for p in sorted(VOZ.glob('*.wav'))}

    configs = {
        'sem dica': '',
        'da maquina': montar_dica(projetos_da_maquina()),
        'escrita a mao': MAO,
    }

    motor = abrir_motor()
    # Passada fria descartada: mede-se o uso, nao a inicializacao.
    transcrever(motor, next(iter(ondas.values())), dica='')

    erros = {nome: [] for nome in configs}
    esperas = {nome: [] for nome in configs}
    detalhe = []

    for indice, (frase, onda) in enumerate(ondas.items()):
        # A ordem inverte a cada frase para nenhuma configuracao ficar sempre com
        # o custo frio da rodada. E a falha que o script de 25/08 teve.
        ordem = list(configs.items())
        if indice % 2:
            ordem.reverse()

        for nome, dica in ordem:
            marca = time.perf_counter()
            saida = transcrever(motor, onda, dica=dica)
            espera = time.perf_counter() - marca
            erro = erro_de_palavras(referencias.get(frase, ''), saida)

            erros[nome].append(erro)
            esperas[nome].append(espera)
            detalhe.append(
                {'frase': frase, 'config': nome, 'erro': round(erro, 3),
                 'espera_s': round(espera, 2), 'saida': saida}
            )
            print(f'{frase:12s} {nome:14s} {espera:6.2f}s  erro {erro:5.1%}  {saida}')
        print()

    print('resumo:')
    resumo = {}
    for nome in configs:
        medio = sum(erros[nome]) / len(erros[nome])
        pior = max(erros[nome])
        espera = sorted(esperas[nome])[len(esperas[nome]) // 2]
        resumo[nome] = {
            'erro_medio': round(medio, 3),
            'erro_pior': round(pior, 3),
            'espera_mediana_s': round(espera, 2),
        }
        print(f'  {nome:14s} erro medio {medio:5.1%}   pior {pior:5.1%}   espera {espera:.2f}s')

    (Path(__file__).parent / 'resultado_dica.json').write_text(
        json.dumps(
            {'dicas': configs, 'resumo': resumo, 'detalhe': detalhe},
            ensure_ascii=False,
            indent=2,
        ),
        encoding='utf-8',
    )


if __name__ == '__main__':
    principal()
