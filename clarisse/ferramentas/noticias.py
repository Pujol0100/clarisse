"""Manchetes do dia a partir de uma lista fixa de feeds RSS, e a leitura da matéria escolhida.

O feed do g1 já traz a matéria inteira na descrição, um parágrafo por linha, misturada com o
título de vídeo relacionado, crédito de foto e etiquetas. Parágrafo de matéria é frase: termina
em ponto. O resto fica de fora."""
import re
import xml.etree.ElementTree as ET
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import httpx
from pydantic import Field

from clarisse.cartoes import Retorno, UltimaEscolha
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
_NS = {"atom": "http://www.w3.org/2005/Atom", "media": "http://search.yahoo.com/mrss/"}
_TAG = re.compile(r"<[^>]*>")
_FIM_DE_FRASE = ('.', '!', '?', '"', '”')
_MINIMO_DE_PALAVRAS = 6


@dataclass
class Noticia:
    titulo: str
    link: str
    subtitulo: str
    imagem: str | None
    paragrafos: list[str]


def paragrafos_da_materia(descricao: str) -> list[str]:
    linhas = (linha.strip() for linha in _TAG.sub("\n", descricao).splitlines())
    return [
        linha for linha in linhas
        if linha.endswith(_FIM_DE_FRASE) and not linha.startswith("*") and len(linha.split()) >= _MINIMO_DE_PALAVRAS
    ]


def _noticias_do_feed(conteudo: bytes) -> list[Noticia]:
    raiz = ET.fromstring(conteudo)
    noticias = []
    for item in raiz.iterfind("./channel/item"):
        titulo = (item.findtext("title") or "").strip()
        if not titulo:
            continue
        descricao = item.find("description")
        midia = item.find("media:content", _NS)
        noticias.append(Noticia(
            titulo=titulo,
            link=(item.findtext("link") or "").strip(),
            subtitulo=(item.findtext("atom:subtitle", "", _NS) or "").strip(),
            imagem=midia.get("url") if midia is not None else None,
            paragrafos=paragrafos_da_materia("".join(descricao.itertext())) if descricao is not None else [],
        ))
    return noticias[:_QUANTAS]


def _com_ponto(frase: str) -> str:
    return frase if frase.endswith(_FIM_DE_FRASE) else f"{frase}."


class ArgsNoticias(Argumentos):
    tema: str | None = Field(None, max_length=60, description="Tema opcional: " + ", ".join(FEEDS))


class ArgsLerNoticia(Argumentos):
    numero: int | None = Field(None, ge=1, le=20, description="Número da manchete na última lista, se o usuário disser")
    assunto: str | None = Field(None, max_length=80, description="Palavras do título, se o usuário disser o assunto")


def ferramentas_de_noticias(
    cliente: httpx.AsyncClient,
    abrir: Callable[[str], Awaitable[None]] | None = None,
    escolhas: UltimaEscolha | None = None,
) -> list[Ferramenta]:
    ultimas: dict = {"tema": None, "noticias": []}
    escolhas = escolhas or UltimaEscolha()

    async def buscar(tema_pedido: str | None) -> str | None:
        tema = normalizar(tema_pedido) if tema_pedido else "geral"
        if tema not in FEEDS:
            tema = "geral"
        try:
            resposta = await cliente.get(FEEDS[tema], timeout=10, follow_redirects=True)
            resposta.raise_for_status()
            noticias = _noticias_do_feed(resposta.content)
        except (httpx.HTTPError, ET.ParseError) as erro:
            return f"Não consegui buscar as notícias agora: {type(erro).__name__}."
        if not noticias:
            return "Não consegui ler manchetes no feed agora."
        ultimas["tema"], ultimas["noticias"] = tema, noticias
        return None

    async def noticias_do_dia(args: ArgsNoticias) -> Retorno | str:
        if falha := await buscar(args.tema):
            return falha
        tema, noticias = ultimas["tema"], ultimas["noticias"]
        texto = f"Separei {len(noticias)} manchetes de {tema} na tela. Qual você quer que eu leia? Diga o número."
        itens = []
        for i, n in enumerate(noticias, 1):
            item = {"numero": i, "titulo": n.titulo}
            if not n.paragrafos:
                item["detalhe"] = "sem texto · abre no site"
            itens.append(item)
        cartao = {"tipo": "escolha", "titulo": "Notícias", "canto": tema, "pedido": "lê a notícia", "itens": itens}
        escolhas.guardar(cartao)
        return Retorno(texto, cartao=cartao, na_integra=True)

    async def ler_noticia(args: ArgsLerNoticia) -> Retorno | str:
        if not ultimas["noticias"] and (falha := await buscar(None)):
            return falha
        noticias = ultimas["noticias"]
        if args.numero is not None:
            if args.numero > len(noticias):
                return f"Não tenho a notícia {args.numero}. A lista tem {len(noticias)}."
            noticia = noticias[args.numero - 1]
        elif args.assunto:
            palavras = normalizar(args.assunto).split("-")
            achadas = [n for n in noticias if all(p in normalizar(n.titulo) for p in palavras)]
            if not achadas:
                return f"Não achei notícia sobre {args.assunto} na lista."
            noticia = achadas[0]
        else:
            return "Diga o número ou o assunto da notícia."
        if not noticia.paragrafos:
            # Vídeo, galeria ou página de jogo: não há matéria escrita nem no feed nem na página.
            if abrir and noticia.link:
                await abrir(noticia.link)
                return "Essa notícia não tem texto para eu ler; é vídeo, fotos ou página de jogo. Abri no navegador."
            return "Essa notícia não tem texto para eu ler; é vídeo, fotos ou página de jogo."
        texto = "\n\n".join([_com_ponto(noticia.titulo), *noticia.paragrafos])
        cartao = {
            "tipo": "leitura", "rotulo": "Notícia", "titulo": noticia.titulo, "subtitulo": noticia.subtitulo, "imagem": noticia.imagem,
            "fonte": f"g1 · {ultimas['tema']}", "paragrafos": noticia.paragrafos,
        }
        return Retorno(texto, cartao=cartao, na_integra=True)

    return [
        Ferramenta(
            "noticias_do_dia",
            "Busca as manchetes de hoje no g1. Use sempre que o usuário pedir notícias; nunca invente notícias.",
            ArgsNoticias,
            noticias_do_dia,
            grupo="noticias",
        ),
        Ferramenta(
            "ler_noticia",
            "Lê em voz alta, na íntegra, uma notícia da última lista de manchetes: pelo número ('lê a segunda', "
            "'lê a notícia 3') ou pelo assunto ('lê a do WhatsApp').",
            ArgsLerNoticia,
            ler_noticia,
            grupo="noticias",
        ),
    ]
