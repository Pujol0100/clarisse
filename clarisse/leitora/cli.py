"""Fronteira de linha de comando da Leitora: recebe argumentos, devolve JSON.

Uso:
    python <caminho>/leitora/cli.py projetos
    python <caminho>/leitora/cli.py relatar --projeto omni-api --maximo 40

O mascaramento de segredo e aplicado aqui, num lugar so, para nao existir
caminho de saida que devolva texto sem passar por ele.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from clarisse.leitora.segredo import mascarar  # noqa: E402
from clarisse.leitora.sessoes import (  # noqa: E402
    listar_sessoes,
    projetos_que_casam,
    sessao_mais_recente,
)
from clarisse.leitora.transcricao import ler_eventos  # noqa: E402

RAIZ_PADRAO = str(Path.home() / '.claude' / 'projects')
MAXIMO_PADRAO = 40


def _montar_analisador():
    analisador = argparse.ArgumentParser(add_help=False)
    analisador.add_argument('comando', choices=('projetos', 'relatar'))
    analisador.add_argument('--projeto', default='')
    analisador.add_argument('--maximo', type=int, default=MAXIMO_PADRAO)
    analisador.add_argument('--raiz', default=RAIZ_PADRAO)
    return analisador


def _evento_em_dicionario(evento):
    return {
        'quem': evento.quem,
        'texto': mascarar(evento.texto),
        'momento': evento.momento,
        'ferramenta': evento.ferramenta,
    }


def _um_por_projeto(sessoes):
    """Uma entrada por projeto, com a sessao que se moveu por ultimo.

    Agrupa ignorando a caixa porque no Windows omni-api e OMNI-API sao a mesma
    pasta. Listar as duas anunciaria um projeto que nao existe.
    """
    resumo = []
    vistos = set()
    for sessao in sessoes:
        chave = sessao.projeto.lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        resumo.append({
            'projeto': sessao.projeto,
            'sessao_id': sessao.sessao_id,
            'modificado_em': sessao.modificado_em,
        })
    return resumo


def _relatar(sessoes, termo, maximo):
    if termo:
        candidatos = projetos_que_casam(sessoes, termo)
        if not candidatos:
            return {'erro': 'nao_encontrado', 'procurado': termo}
        if len(candidatos) > 1:
            return {'erro': 'ambiguo', 'candidatos': candidatos}
        projeto = candidatos[0]
    else:
        if not sessoes:
            return {'erro': 'nao_encontrado', 'procurado': ''}
        projeto = sessoes[0].projeto

    sessao = sessao_mais_recente(sessoes, projeto)
    if sessao is None:
        return {'erro': 'nao_encontrado', 'procurado': termo}

    eventos = ler_eventos(sessao.caminho)
    if maximo > 0:
        eventos = eventos[-maximo:]

    return {
        'projeto': projeto,
        'sessao_id': sessao.sessao_id,
        'eventos': [_evento_em_dicionario(e) for e in eventos],
    }


def executar(argumentos: list[str]) -> dict:
    """Roda um comando da Leitora e devolve o resultado como dicionario."""
    opcoes = _montar_analisador().parse_args(argumentos)
    sessoes = listar_sessoes(opcoes.raiz)

    if opcoes.comando == 'projetos':
        return {'projetos': _um_por_projeto(sessoes)}

    return _relatar(sessoes, opcoes.projeto, opcoes.maximo)


def main() -> int:
    # A saida e forcada para UTF-8 porque o console do Windows costuma abrir em
    # cp1252 e transformar acento em lixo. Quem le esta saida compoe o texto
    # falado: acento corrompido aqui vira palavra errada na voz.
    sys.stdout.reconfigure(encoding='utf-8')
    resultado = executar(sys.argv[1:])
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 1 if 'erro' in resultado else 0


if __name__ == '__main__':
    raise SystemExit(main())
