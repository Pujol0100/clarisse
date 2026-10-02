"""Mexe nas janelas que já estão abertas: traz para a frente, cola texto e aperta atalhos.

As janelas vêm da extensão Window Calls do GNOME, o teclado é o virtual do ydotool.
O texto entra pela área de transferência: o ydotool digita como teclado americano e,
no teclado brasileiro, perderia acentos e trocaria símbolos.
"""
import asyncio
import ast
import json
from typing import Literal

from pydantic import Field

from clarisse.config import Cadastros, normalizar
from clarisse.ferramentas.registro import Argumentos, Ferramenta, Risco

_JANELAS = [
    "gdbus", "call", "--session", "--dest", "org.gnome.Shell",
    "--object-path", "/org/gnome/Shell/Extensions/Windows",
]
_SEM_EXTENSAO = (
    "Não consigo mexer nas janelas: falta a extensão Window Calls do GNOME. "
    "Instale e ative em extensions.gnome.org/extension/4724/window-calls."
)
_SEM_TECLADO = (
    "O teclado virtual não está ligado. Rode o scripts/instalar-teclado-virtual.sh e tente de novo."
)
_TERMINAIS = ("ptyxis", "terminal", "konsole")

# Códigos de tecla do Linux (input-event-codes.h); as letras usadas estão no mesmo lugar no ABNT2.
_CTRL, _SHIFT, _ALT = 29, 42, 56
_ATALHOS: dict[str, list[int]] = {
    "salvar": [_CTRL, 31],
    "desfazer": [_CTRL, 44],
    "copiar": [_CTRL, 46],
    "colar": [_CTRL, 47],
    "enter": [28],
    "esc": [1],
    "trocar_janela": [_ALT, 15],
    "nova_aba": [_CTRL, 20],
    "fechar_aba": [_CTRL, 17],
    "fechar_janela": [_ALT, 62],
}
_PERDEM_TRABALHO = {"fechar_aba", "fechar_janela"}


def ler_janelas(saida_do_gdbus: str) -> list[dict]:
    return json.loads(ast.literal_eval(saida_do_gdbus.strip())[0])


def _combinacao(teclas: list[int]) -> list[str]:
    return ["ydotool", "key", *(f"{t}:1" for t in teclas), *(f"{t}:0" for t in reversed(teclas))]


class ArgsJanela(Argumentos):
    aplicativo: str = Field(max_length=80, description="Programa ou janela como o usuário falou: vs code, chrome, whatsapp")
    titulo: str | None = Field(
        default=None, max_length=120,
        description="Pedaço do título da janela, quando há várias do mesmo programa (nome do projeto, do site)",
    )


class ArgsDigitar(ArgsJanela):
    texto: str = Field(max_length=2000, description="Texto exato a colar")


class ArgsAtalho(Argumentos):
    atalho: Literal[
        "salvar", "desfazer", "copiar", "colar", "enter", "esc",
        "trocar_janela", "nova_aba", "fechar_aba", "fechar_janela",
    ]
    aplicativo: str | None = Field(
        default=None, max_length=80,
        description="Programa ou janela que o usuário citou; vazio só quando ele não citou nenhum (vale a janela da frente)",
    )
    titulo: str | None = Field(default=None, max_length=120, description="Pedaço do título da janela")


def ferramentas_de_janelas(cadastros: Cadastros, executor, espera: float = 0.3) -> list[Ferramenta]:

    def _candidatas(janelas: list[dict], aplicativo: str, titulo: str | None) -> list[dict]:
        alvo = normalizar(aplicativo)
        chave = cadastros.achar_aplicativo(aplicativo)
        processo = cadastros.aplicativos[chave].processo.lower() if chave else None

        def combina(janela: dict) -> bool:
            if processo and processo in janela["wm_class"].lower():
                return True
            return alvo in normalizar(janela["title"]) or alvo in normalizar(janela["wm_class"])

        achadas = [j for j in janelas if combina(j)]
        if titulo:
            achadas = [j for j in achadas if normalizar(titulo) in normalizar(j["title"])]
        # Apps instalados pelo Chrome têm wm_class longa (chrome-<id>-Default); o próprio programa vem antes.
        return sorted(achadas, key=lambda j: len(j["wm_class"]))

    async def _trazer(aplicativo: str, titulo: str | None) -> tuple[dict | None, str]:
        lista = await executor.executar([*_JANELAS, "--method", "org.gnome.Shell.Extensions.Windows.List"])
        if lista.codigo != 0:
            return None, _SEM_EXTENSAO
        janelas = ler_janelas(lista.saida)
        achadas = _candidatas(janelas, aplicativo, titulo)
        if not achadas:
            abertas = "; ".join(j["title"] for j in janelas) or "nenhuma"
            procurada = f"{aplicativo} ({titulo})" if titulo else aplicativo
            return None, f"Não achei janela aberta de {procurada}. Abertas agora: {abertas}."
        janela = achadas[0]
        await executor.executar([*_JANELAS, "--method", "org.gnome.Shell.Extensions.Windows.Activate", str(janela["id"])])
        await asyncio.sleep(espera)
        return janela, f"Trouxe para a frente: {janela['title']}."

    async def _apertar(teclas: list[int]) -> str | None:
        resultado = await executor.executar(_combinacao(teclas))
        if resultado.codigo != 0:
            return _SEM_TECLADO
        return None

    async def trazer_para_frente(args: ArgsJanela) -> str:
        _, resposta = await _trazer(args.aplicativo, args.titulo)
        return resposta

    async def digitar_texto(args: ArgsDigitar) -> str:
        janela, resposta = await _trazer(args.aplicativo, args.titulo)
        if janela is None:
            return resposta
        await executor.iniciar(["wl-copy", "--", args.texto])
        await asyncio.sleep(espera)
        terminal = any(t in janela["wm_class"].lower() for t in _TERMINAIS)
        falha = await _apertar([_CTRL, _SHIFT, 47] if terminal else [_CTRL, 47])
        return falha or f"Colei o texto em {janela['title']}. Não apertei Enter."

    def confirmar_digitar(args: ArgsDigitar) -> str:
        onde = f"{args.aplicativo} ({args.titulo})" if args.titulo else args.aplicativo
        return f'Vou colar "{args.texto}" no {onde}. Confirma?'

    async def apertar_atalho(args: ArgsAtalho) -> str:
        onde = "na janela da frente"
        if args.aplicativo or args.titulo:
            janela, resposta = await _trazer(args.aplicativo or args.titulo, args.titulo)
            if janela is None:
                return resposta
            onde = f"em {janela['title']}"
        falha = await _apertar(_ATALHOS[args.atalho])
        return falha or f"Apertei {args.atalho.replace('_', ' ')} {onde}."

    def risco_do_atalho(args: ArgsAtalho) -> Risco:
        return Risco.CONFIRMAR if args.atalho in _PERDEM_TRABALHO else Risco.SEGURO

    def confirmar_atalho(args: ArgsAtalho) -> str:
        onde = args.aplicativo or args.titulo or "a janela da frente"
        perda = ", e o que não estiver salvo se perde" if args.atalho in _PERDEM_TRABALHO else ""
        return f"Vou apertar {args.atalho.replace('_', ' ')} em {onde}{perda}. Confirma?"

    return [
        Ferramenta(
            "trazer_para_frente",
            "Traz para a frente uma janela que JÁ ESTÁ ABERTA (VS Code, Chrome, terminal, WhatsApp), sem abrir outra.",
            ArgsJanela, trazer_para_frente,
        ),
        Ferramenta(
            "digitar_texto",
            "Escreve um texto em qualquer programa aberto (terminal, Sublime, WhatsApp, navegador, editor), "
            "onde o cursor estiver, como se o usuário digitasse. No terminal só escreve o comando, não executa. "
            "Não aperta Enter. Não serve para conversas do Claude Code: para elas há outra ferramenta.",
            ArgsDigitar, digitar_texto, risco=Risco.CONFIRMAR, descrever=confirmar_digitar,
        ),
        Ferramenta(
            "apertar_atalho",
            "Aperta um atalho de teclado: salvar, desfazer, copiar, colar, enter, esc, trocar de janela, "
            "abrir ou fechar aba, fechar janela. Se o usuário não disser o programa, vale para a janela da frente.",
            ArgsAtalho, apertar_atalho, risco=risco_do_atalho, descrever=confirmar_atalho,
        ),
    ]
