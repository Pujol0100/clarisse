"""Decide qual trecho da fala ja pode ser transcrito antes de a tecla ser solta.

Cada corte carrega o `fechado_em`: o instante, contado do inicio da fala, em que
aquele trecho ficou disponivel. Um corte que so fecha no fim do audio nao adianta
nada — e o que a transcricao em bloco ja fazia.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

BLOCO = 512  # 32 ms a 16 kHz


@dataclass(frozen=True)
class Corte:
    inicio: int
    fim: int
    fechado_em: float


def cortes_por_tempo(
    onda: np.ndarray,
    taxa: int,
    *,
    janela_s: float = 2.0,
    minimo_s: float = 0.5,
) -> list[Corte]:
    """Fecha um trecho a cada `janela_s`, sem olhar o conteudo do audio."""
    total = len(onda)
    if total == 0:
        return []

    passo = int(janela_s * taxa)
    minimo = int(minimo_s * taxa)

    limites = list(range(passo, total, passo))
    if limites and total - limites[-1] < minimo:
        limites.pop()
    limites.append(total)

    cortes = []
    inicio = 0
    for fim in limites:
        cortes.append(Corte(inicio, fim, fim / taxa))
        inicio = fim
    return cortes


def cortes_por_silencio(
    onda: np.ndarray,
    taxa: int,
    *,
    limiar: float = 0.01,
    silencio_ms: int = 400,
    minimo_s: float = 1.0,
) -> list[Corte]:
    """Fecha um trecho quando a pausa passa de `silencio_ms`.

    Trecho mais curto que `minimo_s` nao fecha sozinho: ele continua acumulando
    ate a pausa seguinte, porque transcrever um fragmento de meio segundo custa
    uma ida ao motor e devolve pouco.
    """
    total = len(onda)
    if total == 0:
        return []

    blocos = _energia_por_bloco(onda)
    tem_fala = blocos > limiar
    blocos_de_silencio = max(1, round(silencio_ms / 1000 * taxa / BLOCO))
    minimo = int(minimo_s * taxa)

    cortes: list[Corte] = []
    inicio: int | None = None
    silencio_desde: int | None = None

    for indice, audivel in enumerate(tem_fala):
        if audivel:
            if inicio is None:
                inicio = indice * BLOCO
            silencio_desde = None
            continue

        if inicio is None:
            continue

        if silencio_desde is None:
            silencio_desde = indice

        if indice - silencio_desde + 1 < blocos_de_silencio:
            continue

        fim = min(silencio_desde * BLOCO, total)
        if fim - inicio >= minimo:
            cortes.append(Corte(inicio, fim, (indice + 1) * BLOCO / taxa))
            inicio = None
        silencio_desde = None

    if inicio is not None:
        cortes.append(Corte(inicio, total, total / taxa))
    return cortes


def _energia_por_bloco(onda: np.ndarray) -> np.ndarray:
    sobra = len(onda) % BLOCO
    inteiro = onda[: len(onda) - sobra].reshape(-1, BLOCO)
    energia = np.sqrt(np.mean(np.square(inteiro, dtype=np.float64), axis=1))
    if sobra:
        cauda = np.sqrt(np.mean(np.square(onda[-sobra:], dtype=np.float64)))
        energia = np.append(energia, cauda)
    return energia
