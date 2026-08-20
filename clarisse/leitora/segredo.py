"""Mascara formatos evidentes de segredo antes de um texto virar voz.

A sintese neural manda o texto para servidores da Microsoft. Transcricao de
sessao contem tudo que passou por um terminal, inclusive credencial colada.

Este filtro pega formato, nao sentido: ele barra uma chave, um token e uma
atribuicao de senha. Nome de cliente dito em texto corrido passa. A defesa
contra isso e a instrucao dada ao Claude que compoe o resumo, e ela e
instrucao, nao garantia.
"""

from __future__ import annotations

import re

OCULTO = '[oculto]'

# O valor de uma atribuicao nunca pode ser a palavra Bearer nem uma marca ja
# aplicada. Sem essa restricao, "Authorization: Bearer <token>" mascara a
# palavra Bearer e deixa o token inteiro exposto - com [oculto] na saida
# fingindo que o filtro funcionou.
_ATRIBUICAO = re.compile(
    r'(?i)\b(senha|password|secret|token|api[_-]?key|chave[_-]?api|authorization)'
    r'(\s*[:=]\s*)("?)((?!Bearer\b)(?!\[oculto\])[^\s"\']+)\3'
)
_BEARER = re.compile(r'(?i)\bBearer\s+[A-Za-z0-9._\-]{8,}')
_CHAVE_ANTHROPIC = re.compile(r'\bsk-ant-[A-Za-z0-9._\-]+')
_CHAVE_AWS = re.compile(r'\bAKIA[0-9A-Z]{16}\b')
_CHAVE_PRIVADA = re.compile(
    r'-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----',
    re.DOTALL,
)


def mascarar(texto: str) -> str:
    """Devolve o texto com os segredos reconhecidos trocados por [oculto].

    A ordem importa: o cabecalho Bearer e resolvido antes da atribuicao, para o
    token nao sobreviver escondido atras da palavra mascarada.
    """
    if not texto:
        return texto
    limpo = _CHAVE_PRIVADA.sub(OCULTO, texto)
    limpo = _BEARER.sub(f'Bearer {OCULTO}', limpo)
    limpo = _ATRIBUICAO.sub(lambda m: f'{m.group(1)}{m.group(2)}{OCULTO}', limpo)
    limpo = _CHAVE_ANTHROPIC.sub(OCULTO, limpo)
    limpo = _CHAVE_AWS.sub(OCULTO, limpo)
    return limpo


def contem_segredo(texto: str) -> bool:
    """Verdadeiro quando mascarar mudaria o texto."""
    return mascarar(texto) != texto
