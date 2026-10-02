"""Figuras que os drones formam enquanto a Clarisse fala. Quem escolhe é o sistema, nunca o modelo."""
from dataclasses import dataclass

SOL, NUVEM, CHUVA, TROVOADA = "sol", "nuvem", "chuva", "trovoada"
CALENDARIO, RELOGIO, JORNAL, CODIGO, MENSAGEM = "calendario", "relogio", "jornal", "codigo", "mensagem"


@dataclass
class Retorno:
    """Resultado de ferramenta que traz, além do texto, a figura calculada a partir do dado."""

    texto: str
    figura: str | None = None
    # Texto para a Clarisse falar inteiro, sem o modelo resumir (ex.: ler a resposta do Claude).
    na_integra: bool = False


def figura_do_tempo(codigo: int) -> str:
    """Código de tempo da Organização Meteorológica Mundial, como o Open-Meteo devolve."""
    if codigo in (0, 1):
        return SOL
    if 95 <= codigo <= 99:
        return TROVOADA
    if 51 <= codigo <= 67 or 80 <= codigo <= 82:
        return CHUVA
    return NUVEM
