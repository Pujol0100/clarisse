"""Monta o `initial_prompt` que ensina ao motor o vocabulario desta maquina.

A dica orienta o que o motor procura antes de ele ouvir, e nao custa latencia:
ela muda o alvo da busca, nao o tamanho do trabalho. E ela e para vocabulario
**fixo** — nome de projeto. Texto recem-transcrito no mesmo lugar leva o modelo a
repetir em laco; medido em 22/08/2026.
"""

from __future__ import annotations

from collections.abc import Iterable

TETO = 12
ASSINATURA = "Clarisse."


def montar_dica(projetos: Iterable[str], *, limite: int = TETO) -> str:
    """Devolve a dica com os nomes dos projetos, na ordem recebida.

    O teto existe porque a dica compete com o audio pela janela de contexto do
    modelo. Quem chama passa os projetos do mais recente para o mais antigo.
    """
    nomes: list[str] = []
    for projeto in projetos:
        nome = projeto.strip()
        if nome and nome not in nomes:
            nomes.append(nome)
        if len(nomes) == limite:
            break

    if not nomes:
        return ASSINATURA
    return f"Projetos: {', '.join(nomes)}. {ASSINATURA}"
