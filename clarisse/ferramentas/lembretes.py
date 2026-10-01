"""Lembretes guardados num arquivo da máquina e falados na hora certa, com cartão na tela.

O arquivo é lido e gravado a cada operação: a tarefa que dispara e as ferramentas podem usar
objetos diferentes apontando para o mesmo arquivo."""
import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from pathlib import Path

from pydantic import Field

from clarisse.cartoes import Retorno
from clarisse.ferramentas.registro import Argumentos, Ferramenta

_HORARIO = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")


class Lembretes:
    def __init__(self, arquivo: Path):
        self._arquivo = arquivo

    def todos(self) -> list[dict]:
        if not self._arquivo.is_file():
            return []
        return sorted(json.loads(self._arquivo.read_text(encoding="utf-8")), key=lambda l: l["quando"])

    def _gravar(self, lembretes: list[dict]) -> None:
        self._arquivo.parent.mkdir(parents=True, exist_ok=True)
        self._arquivo.write_text(json.dumps(lembretes, ensure_ascii=False, indent=1), encoding="utf-8")

    def adicionar(self, quando: datetime, texto: str) -> None:
        self._gravar([*self.todos(), {"quando": quando.isoformat(timespec="seconds"), "texto": texto}])

    def remover(self, indice: int) -> dict:
        lembretes = self.todos()
        removido = lembretes.pop(indice)
        self._gravar(lembretes)
        return removido

    def vencidos(self, agora: datetime) -> list[dict]:
        lembretes = self.todos()
        vencidos = [l for l in lembretes if datetime.fromisoformat(l["quando"]) <= agora]
        if vencidos:
            self._gravar([l for l in lembretes if l not in vencidos])
        return vencidos


async def disparar_vencidos(lembretes: Lembretes, avisar: Callable[..., Awaitable[None]], agora: datetime) -> None:
    for lembrete in lembretes.vencidos(agora):
        await avisar("Lembrete", lembrete["texto"], falar=f"Lembrete: {lembrete['texto']}.")


async def manter_lembretes(lembretes: Lembretes, avisar, agora: Callable[[], datetime] = datetime.now, intervalo: float = 15) -> None:
    while True:
        await disparar_vencidos(lembretes, avisar, agora())
        await asyncio.sleep(intervalo)


class ArgsLembrar(Argumentos):
    texto: str = Field(min_length=1, max_length=200, description="Do que lembrar, com as palavras do usuário")
    em_minutos: int | None = Field(None, ge=1, le=24 * 60, description="Daqui a quantos minutos, se o usuário disser")
    horario: str | None = Field(None, pattern=_HORARIO.pattern, description="Hora no formato HH:MM, se o usuário disser")


class ArgsCancelar(Argumentos):
    numero: int = Field(ge=1, le=50, description="Número do lembrete na lista")


def ferramentas_de_lembretes(lembretes: Lembretes, agora: Callable[[], datetime] = datetime.now) -> list[Ferramenta]:
    async def lembrar(args: ArgsLembrar) -> Retorno | str:
        momento = agora().replace(second=0, microsecond=0)
        if args.em_minutos:
            quando = momento + timedelta(minutes=args.em_minutos)
        elif args.horario:
            hora, minuto = map(int, args.horario.split(":"))
            quando = momento.replace(hour=hora, minute=minuto)
            if quando <= momento:
                quando += timedelta(days=1)
        else:
            return "Diga quando: daqui a quantos minutos ou a que horas."
        lembretes.adicionar(quando, args.texto)
        dia = "hoje" if quando.date() == momento.date() else "amanhã" if quando.date() == momento.date() + timedelta(days=1) else quando.strftime("%d/%m")
        texto = f"Combinado: {dia} às {quando:%H:%M} eu lembro de {args.texto}."
        return Retorno(texto, cartao={"tipo": "lista", "titulo": "Lembretes", "canto": dia,
                                      "itens": [[f"{quando:%H:%M}", args.texto]]}, na_integra=True)

    async def listar_lembretes(args: Argumentos) -> Retorno:
        todos = lembretes.todos()
        if not todos:
            return Retorno("Nenhum lembrete marcado.", na_integra=True)
        itens = [[datetime.fromisoformat(l["quando"]).strftime("%H:%M"), l["texto"]] for l in todos]
        falados = " ".join(f"{i}, às {hora}, {texto}." for i, (hora, texto) in enumerate(itens, 1))
        return Retorno(
            f"{len(todos)} lembrete{'s' if len(todos) > 1 else ''}: {falados}",
            cartao={"tipo": "lista", "titulo": "Lembretes", "canto": f"{len(todos)} marcados", "itens": itens},
            na_integra=True,
        )

    async def cancelar_lembrete(args: ArgsCancelar) -> str:
        todos = lembretes.todos()
        if args.numero > len(todos):
            return f"Não tenho o lembrete {args.numero}. São {len(todos)}."
        return f"Cancelei o lembrete de {lembretes.remover(args.numero - 1)['texto']}."

    return [
        Ferramenta(
            "lembrar",
            "Marca um lembrete falado: daqui a X minutos ou num horário. Use para 'me lembra de…'.",
            ArgsLembrar, lembrar, grupo="lembretes",
        ),
        Ferramenta("listar_lembretes", "Diz os lembretes marcados.", Argumentos, listar_lembretes, grupo="lembretes"),
        Ferramenta(
            "cancelar_lembrete", "Cancela um lembrete pelo número da lista.", ArgsCancelar, cancelar_lembrete, grupo="lembretes",
        ),
    ]
