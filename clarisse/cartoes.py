"""O que a tela mostra de cada ferramenta: o nó da constelação que acende e o cartão com o dado.
Quem monta o cartão é a ferramenta, a partir do dado de verdade; o modelo nunca escolhe."""
from dataclasses import dataclass

# Nós da constelação e o título do cartão de texto de cada um.
GRUPOS = {
    "agenda": "Agenda",
    "clima": "Clima",
    "noticias": "Notícias",
    "email": "E-mail",
    "github": "GitHub",
    "notas": "Notas",
    "servidores": "Servidores",
    "lembretes": "Lembretes",
    "claude": "Claude",
    "codigo": "Código",
    "navegador": "Navegador",
    "janelas": "Janelas",
    "sistema": "Sistema",
}


@dataclass
class Retorno:
    """Resultado de ferramenta que traz, além do texto que vai ao modelo, o cartão para a tela."""

    texto: str
    cartao: dict | None = None
    # Texto para a Clarisse falar inteiro, sem o modelo resumir (ex.: ler a resposta do Claude).
    na_integra: bool = False


def cartao_de_texto(grupo: str, texto: str) -> dict:
    return {"tipo": "texto", "titulo": GRUPOS.get(grupo, "Clarisse"), "texto": texto}
