"""Catálogo fechado do que a Clarisse pode fazer."""
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, ConfigDict


class Risco(str, Enum):
    SEGURO = "seguro"
    CONFIRMAR = "confirmar"
    BLOQUEADO = "bloqueado"


class Argumentos(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FerramentaDesconhecida(KeyError):
    pass


@dataclass
class Ferramenta:
    nome: str
    descricao: str
    argumentos: type[Argumentos]
    executar: Callable[[Argumentos], Awaitable[str]]
    risco: Risco | Callable[[Argumentos], Risco] = Risco.SEGURO
    descrever: Callable[[Argumentos], str] | None = None
    figura: str | None = None

    def risco_de(self, args: Argumentos) -> Risco:
        return self.risco(args) if callable(self.risco) else self.risco

    def frase_de_confirmacao(self, args: Argumentos) -> str:
        if self.descrever:
            return self.descrever(args)
        return f"Vou executar {self.nome}. Confirma?"


def _sem_titulos(esquema):
    if isinstance(esquema, dict):
        return {k: _sem_titulos(v) for k, v in esquema.items() if k != "title"}
    if isinstance(esquema, list):
        return [_sem_titulos(v) for v in esquema]
    return esquema


def _parametros(modelo: type[Argumentos]) -> dict:
    esquema = _sem_titulos(modelo.model_json_schema())
    return {
        "type": "object",
        "properties": esquema.get("properties", {}),
        "required": esquema.get("required", []),
        "additionalProperties": False,
    }


class Registro:
    def __init__(self):
        self._ferramentas: dict[str, Ferramenta] = {}

    def registrar(self, ferramenta: Ferramenta) -> None:
        if ferramenta.nome in self._ferramentas:
            raise ValueError(f"ferramenta repetida: {ferramenta.nome}")
        self._ferramentas[ferramenta.nome] = ferramenta

    def obter(self, nome: str) -> Ferramenta:
        try:
            return self._ferramentas[nome]
        except KeyError:
            raise FerramentaDesconhecida(nome) from None

    def nomes(self) -> list[str]:
        return list(self._ferramentas)

    def esquemas(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": f.nome,
                    "description": f.descricao,
                    "parameters": _parametros(f.argumentos),
                },
            }
            for f in self._ferramentas.values()
        ]
