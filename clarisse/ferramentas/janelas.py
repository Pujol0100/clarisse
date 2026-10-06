"""Mexe nas janelas que já estão abertas: traz para a frente, cola texto e aperta atalhos.

O texto entra pela área de transferência: digitado tecla a tecla, perderia acentos no teclado brasileiro.
"""
import asyncio
from typing import Literal

from pydantic import Field

from clarisse.config import Cadastros, normalizar
from clarisse.ferramentas.registro import Argumentos, Ferramenta, Risco

# Teclas no formato do pywinauto: ^ é Ctrl, % é Alt, + é Shift.
_ATALHOS: dict[str, str] = {
    "salvar": "^s",
    "desfazer": "^z",
    "copiar": "^c",
    "colar": "^v",
    "enter": "{ENTER}",
    "esc": "{ESC}",
    "trocar_janela": "%{TAB}",
    "nova_aba": "^t",
    "fechar_aba": "^w",
    "fechar_janela": "%{F4}",
}
_PERDEM_TRABALHO = {"fechar_aba", "fechar_janela"}


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


def ferramentas_de_janelas(cadastros: Cadastros, area, espera: float = 0.3) -> list[Ferramenta]:

    def _candidatas(janelas: list[dict], aplicativo: str, titulo: str | None) -> list[dict]:
        alvo = normalizar(aplicativo)
        chave = cadastros.achar_aplicativo(aplicativo)
        processo = cadastros.aplicativos[chave].processo.lower() if chave else None

        def combina(janela: dict) -> bool:
            if processo and processo == janela["processo"].lower():
                return True
            return alvo in normalizar(janela["titulo"]) or alvo in normalizar(janela["processo"])

        achadas = [j for j in janelas if combina(j)]
        if titulo:
            achadas = [j for j in achadas if normalizar(titulo) in normalizar(j["titulo"])]
        # Apps instalados pelo Chrome também são chrome.exe; o próprio Chrome tem o nome dele no título.
        nome = normalizar(chave) if chave else alvo
        return sorted(achadas, key=lambda j: nome not in normalizar(j["titulo"]))

    async def _trazer(aplicativo: str, titulo: str | None) -> tuple[dict | None, str]:
        janelas = area.listar()
        achadas = _candidatas(janelas, aplicativo, titulo)
        if not achadas:
            abertas = "; ".join(j["titulo"] for j in janelas) or "nenhuma"
            procurada = f"{aplicativo} ({titulo})" if titulo else aplicativo
            return None, f"Não achei janela aberta de {procurada}. Abertas agora: {abertas}."
        janela = achadas[0]
        area.ativar(janela["id"])
        await asyncio.sleep(espera)
        return janela, f"Trouxe para a frente: {janela['titulo']}."

    async def trazer_para_frente(args: ArgsJanela) -> str:
        _, resposta = await _trazer(args.aplicativo, args.titulo)
        return resposta

    async def digitar_texto(args: ArgsDigitar) -> str:
        janela, resposta = await _trazer(args.aplicativo, args.titulo)
        if janela is None:
            return resposta
        area.colar(args.texto)
        await asyncio.sleep(espera)
        area.apertar(_ATALHOS["colar"])
        return f"Colei o texto em {janela['titulo']}. Não apertei Enter."

    def confirmar_digitar(args: ArgsDigitar) -> str:
        onde = f"{args.aplicativo} ({args.titulo})" if args.titulo else args.aplicativo
        return f'Vou colar "{args.texto}" no {onde}. Confirma?'

    async def apertar_atalho(args: ArgsAtalho) -> str:
        onde = "na janela da frente"
        if args.aplicativo or args.titulo:
            janela, resposta = await _trazer(args.aplicativo or args.titulo, args.titulo)
            if janela is None:
                return resposta
            onde = f"em {janela['titulo']}"
        area.apertar(_ATALHOS[args.atalho])
        return f"Apertei {args.atalho.replace('_', ' ')} {onde}."

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
            ArgsJanela, trazer_para_frente, grupo="janelas",
        ),
        Ferramenta(
            "digitar_texto",
            "Escreve um texto em qualquer programa aberto (terminal, Sublime, WhatsApp, navegador, editor), "
            "onde o cursor estiver, como se o usuário digitasse. No terminal só escreve o comando, não executa. "
            "Não aperta Enter. Não serve para conversas do Claude Code: para elas há outra ferramenta.",
            ArgsDigitar, digitar_texto, risco=Risco.CONFIRMAR, descrever=confirmar_digitar, grupo="janelas",
        ),
        Ferramenta(
            "apertar_atalho",
            "Aperta um atalho de teclado: salvar, desfazer, copiar, colar, enter, esc, trocar de janela, "
            "abrir ou fechar aba, fechar janela. Se o usuário não disser o programa, vale para a janela da frente.",
            ArgsAtalho, apertar_atalho, risco=risco_do_atalho, descrever=confirmar_atalho, grupo="janelas",
        ),
    ]
