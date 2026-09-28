"""Manchetes do dia a partir de uma lista fixa de feeds RSS."""
import xml.etree.ElementTree as ET

import httpx
from pydantic import Field

from clarisse.config import normalizar
from clarisse.ferramentas.registro import Argumentos, Ferramenta

FEEDS = {
    "geral": "https://g1.globo.com/rss/g1/",
    "economia": "https://g1.globo.com/rss/g1/economia/",
    "tecnologia": "https://g1.globo.com/rss/g1/tecnologia/",
    "politica": "https://g1.globo.com/rss/g1/politica/",
    "mundo": "https://g1.globo.com/rss/g1/mundo/",
    "esportes": "https://ge.globo.com/rss/ge/",
}
_QUANTAS = 5


class ArgsNoticias(Argumentos):
    tema: str | None = Field(None, max_length=60, description="Tema opcional: " + ", ".join(FEEDS))


def ferramentas_de_noticias(cliente: httpx.AsyncClient) -> list[Ferramenta]:
    async def noticias_do_dia(args: ArgsNoticias) -> str:
        tema = normalizar(args.tema) if args.tema else "geral"
        if tema not in FEEDS:
            tema = "geral"
        try:
            resposta = await cliente.get(FEEDS[tema], timeout=10, follow_redirects=True)
            resposta.raise_for_status()
            raiz = ET.fromstring(resposta.content)
        except (httpx.HTTPError, ET.ParseError) as erro:
            return f"Não consegui buscar as notícias agora: {type(erro).__name__}."
        titulos = [t.text.strip() for t in raiz.iterfind("./channel/item/title") if t.text][:_QUANTAS]
        if not titulos:
            return "Não consegui ler manchetes no feed agora."
        return f"Manchetes de {tema} no g1: " + " | ".join(titulos)

    return [
        Ferramenta(
            "noticias_do_dia",
            "Busca as manchetes de hoje no g1. Use sempre que o usuário pedir notícias; nunca invente notícias.",
            ArgsNoticias,
            noticias_do_dia,
        )
    ]
