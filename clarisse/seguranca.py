"""Decide o destino de cada pedido de ferramenta e reconhece falas de controle sem passar pelo modelo."""
import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

from pydantic import ValidationError

from clarisse.ferramentas.registro import (
    Argumentos,
    Ferramenta,
    FerramentaDesconhecida,
    Registro,
    Risco,
)


@dataclass
class Decisao:
    acao: Literal["executar", "confirmar", "recusar"]
    ferramenta: Ferramenta | None = None
    args: Argumentos | None = None
    motivo: str = ""


def avaliar(registro: Registro, nome: str, argumentos: dict | None) -> Decisao:
    try:
        ferramenta = registro.obter(nome)
    except FerramentaDesconhecida:
        return Decisao("recusar", motivo=f"a ferramenta {nome} não existe")

    try:
        args = ferramenta.argumentos(**(argumentos or {}))
    except ValidationError as erro:
        campos = ", ".join(".".join(map(str, e["loc"])) or "argumentos" for e in erro.errors())
        return Decisao("recusar", ferramenta, motivo=f"argumentos inválidos para {nome}: {campos}")

    risco = ferramenta.risco_de(args)
    if risco is Risco.BLOQUEADO:
        return Decisao("recusar", ferramenta, args, motivo=f"{nome} está bloqueada")
    if risco is Risco.CONFIRMAR:
        return Decisao("confirmar", ferramenta, args)
    return Decisao("executar", ferramenta, args)


def _palavras(fala: str) -> list[str]:
    sem_acento = unicodedata.normalize("NFD", fala.lower())
    sem_acento = "".join(c for c in sem_acento if unicodedata.category(c) != "Mn")
    return re.findall(r"[a-z]+", sem_acento)


_SIM = {"sim", "pode", "confirmo", "confirma", "manda", "claro", "ok"}
_NAO = {"nao", "cancela", "cancelar", "espera", "para", "parar", "pare"}
_PARAR = {"para", "pare", "parar", "cancela", "cancelar", "chega", "silencio", "cala"}


def confirma(fala: str) -> bool:
    palavras = set(_palavras(fala))
    return bool(palavras & _SIM) and not palavras & _NAO


_RECUSA = {"nao", "cancela", "cancelar", "esquece", "deixa"}


def nega(fala: str) -> bool:
    return bool(set(_palavras(fala)) & _RECUSA)


def pede_para_parar(fala: str) -> bool:
    palavras = [p for p in _palavras(fala) if p != "clarisse"]
    return bool(palavras) and palavras[0] in _PARAR and len(palavras) <= 4
