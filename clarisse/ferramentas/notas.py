"""Busca e leitura das notas do cofre do Obsidian, tudo na máquina. A nota é lida sem a marcação do
Markdown: título, item de lista e parágrafo viram frases; link vira só o nome; código vira um aviso."""
import re
from pathlib import Path

from pydantic import Field

from clarisse.cartoes import Retorno
from clarisse.config import normalizar
from clarisse.ferramentas.registro import Argumentos, Ferramenta

_ACHADAS = 5
_LIMITE_DA_LEITURA = 6000
_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)
_CODIGO = re.compile(r"^```.*?^```[^\n]*$", re.DOTALL | re.MULTILINE)
_TITULO = re.compile(r"^#{1,6}\s+")
_ITEM = re.compile(r"^(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s+)?")
_INTERNO = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_ENFASE = re.compile(r"(\*\*|__|\*|`)(.+?)\1")


def _sem_marcacao(linha: str) -> str:
    linha = _INTERNO.sub(lambda m: m.group(2) or m.group(1), linha)
    linha = _LINK.sub(r"\1", linha)
    return _ENFASE.sub(r"\2", linha).strip()


def paragrafos_da_nota(texto: str) -> list[str]:
    texto = _CODIGO.sub("\n\nTRECHO_DE_CODIGO\n\n", _FRONTMATTER.sub("", texto))
    paragrafos, atual = [], []

    def fechar():
        if atual:
            paragrafos.append(" ".join(atual))
            atual.clear()

    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha:
            fechar()
        elif linha == "TRECHO_DE_CODIGO":
            fechar()
            paragrafos.append("Trecho de código.")
        elif _TITULO.match(linha) or _ITEM.match(linha):
            fechar()
            paragrafos.append(_sem_marcacao(_ITEM.sub("", _TITULO.sub("", linha))))
        else:
            atual.append(_sem_marcacao(linha))
    fechar()
    cabem, total = [], 0
    for paragrafo in filter(None, paragrafos):
        total += len(paragrafo)
        if total > _LIMITE_DA_LEITURA:
            cabem.append("A nota continua; o resto está no Obsidian.")
            break
        cabem.append(paragrafo)
    return cabem


def _notas(cofre: Path) -> list[Path]:
    return [p for p in cofre.rglob("*.md") if not any(parte.startswith(".") for parte in p.relative_to(cofre).parts)]


class ArgsBusca(Argumentos):
    termo: str = Field(min_length=2, max_length=80, description="O que procurar nas notas, como o usuário falou")


class ArgsLerNota(Argumentos):
    numero: int = Field(ge=1, le=_ACHADAS, description="Número da nota na última busca")


def ferramentas_de_notas(cofre: Path) -> list[Ferramenta]:
    ultimas: list[Path] = []

    async def buscar_nas_notas(args: ArgsBusca) -> Retorno | str:
        palavras = [p for p in normalizar(args.termo).split("-") if p]
        pontuadas = []
        for nota in _notas(cofre):
            titulo = normalizar(nota.stem)
            conteudo = normalizar(nota.read_text(encoding="utf-8", errors="ignore"))
            if not all(p in titulo or p in conteudo for p in palavras):
                continue
            # O termo inteiro no nome ou no texto pesa mais; palavra solta conta pouco, para "smart" de
            # "Smart Compass" repetido não ganhar de uma nota que fala de "smart anchor".
            termo = "-".join(palavras)
            pontos = (
                10 * sum(p in titulo for p in palavras) + 20 * (termo in titulo)
                + 5 * min(conteudo.count(termo), 10) + sum(min(conteudo.count(p), 3) for p in palavras)
            )
            pontuadas.append((pontos, nota.stat().st_mtime, nota))
        pontuadas.sort(key=lambda t: (t[0], t[1]), reverse=True)
        ultimas[:] = [nota for _, _, nota in pontuadas[:_ACHADAS]]
        if not ultimas:
            return f"Não achei nada sobre {args.termo} nas notas."
        lista = " ".join(f"{i}, {n.stem}." for i, n in enumerate(ultimas, 1))
        texto = f"Achei {len(ultimas)} nota{'s' if len(ultimas) > 1 else ''}: {lista} Para eu ler uma, diga o número."
        cartao = {
            "tipo": "escolha", "titulo": "Notas", "canto": args.termo, "pedido": "lê a nota",
            "itens": [{"numero": i, "titulo": n.stem, "detalhe": str(n.parent.relative_to(cofre))}
                      for i, n in enumerate(ultimas, 1)],
        }
        return Retorno(texto, cartao=cartao, na_integra=True)

    async def ler_nota(args: ArgsLerNota) -> Retorno | str:
        if args.numero > len(ultimas):
            return f"Não tenho a nota {args.numero}. A lista tem {len(ultimas)}."
        nota = ultimas[args.numero - 1]
        paragrafos = paragrafos_da_nota(nota.read_text(encoding="utf-8", errors="ignore"))
        texto = "\n\n".join([f"Nota {nota.stem}.", *paragrafos])
        cartao = {"tipo": "leitura", "rotulo": "Nota", "titulo": nota.stem, "subtitulo": str(nota.parent.relative_to(cofre)),
                  "imagem": None, "fonte": "Obsidian", "paragrafos": paragrafos}
        return Retorno(texto, cartao=cartao, na_integra=True)

    return [
        Ferramenta(
            "buscar_nas_notas",
            "Procura nas notas do Obsidian do usuário. Use para 'o que eu anotei sobre X', 'procura nas notas'.",
            ArgsBusca, buscar_nas_notas, grupo="notas",
        ),
        Ferramenta(
            "ler_nota",
            "Lê na íntegra uma nota da última busca, pelo número ('lê a nota 2').",
            ArgsLerNota, ler_nota, grupo="notas",
        ),
    ]
