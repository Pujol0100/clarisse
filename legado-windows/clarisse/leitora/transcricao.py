"""Traduz uma transcricao de sessao do Claude Code em eventos legiveis.

O Claude Code grava uma linha JSON por evento em
~/.claude/projects/<projeto>/<sessao>.jsonl.

Linha malformada e ignorada de proposito: o arquivo esta sendo escrito enquanto
lemos, e a ultima linha pode estar pela metade. Derrubar a leitura por causa
disso faria a Clarisse calar justamente quando o projeto esta em atividade.

O pensamento do Claude fica de fora do relato: e raciocinio interno, nao e o que
aconteceu, e carrega mais risco de vazar do que informa.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

USUARIO = 'usuario'
CLAUDE = 'claude'
FERRAMENTA = 'ferramenta'

_TIPOS_RELATAVEIS = ('user', 'assistant')


@dataclass(frozen=True)
class Evento:
    quem: str
    texto: str
    momento: str
    ferramenta: str = ''


def _eventos_da_lista_de_blocos(blocos, quem, momento):
    achados = []
    for bloco in blocos:
        if not isinstance(bloco, dict):
            continue
        tipo = bloco.get('type')
        if tipo == 'text':
            texto = (bloco.get('text') or '').strip()
            if texto:
                achados.append(Evento(quem, texto, momento))
        elif tipo == 'tool_use':
            nome = (bloco.get('name') or '').strip()
            if nome:
                achados.append(Evento(FERRAMENTA, '', momento, nome))
    return achados


def _eventos_do_registro(registro):
    if registro.get('isSidechain') or registro.get('isMeta'):
        return []
    if registro.get('type') not in _TIPOS_RELATAVEIS:
        return []

    quem = USUARIO if registro.get('type') == 'user' else CLAUDE
    momento = registro.get('timestamp') or ''
    conteudo = (registro.get('message') or {}).get('content')

    if isinstance(conteudo, str):
        texto = conteudo.strip()
        return [Evento(quem, texto, momento)] if texto else []
    if isinstance(conteudo, list):
        return _eventos_da_lista_de_blocos(conteudo, quem, momento)
    return []


def ler_eventos(caminho: str) -> list[Evento]:
    """Le a transcricao e devolve os eventos, na ordem em que aconteceram."""
    try:
        with open(caminho, encoding='utf-8', errors='replace') as arquivo:
            linhas = arquivo.read().splitlines()
    except OSError:
        return []

    eventos = []
    for linha in linhas:
        linha = linha.strip()
        if not linha:
            continue
        try:
            registro = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if isinstance(registro, dict):
            eventos.extend(_eventos_do_registro(registro))
    return eventos
