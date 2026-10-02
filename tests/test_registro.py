import pytest
from pydantic import Field

from clarisse.ferramentas.registro import (
    Argumentos,
    Ferramenta,
    Registro,
    Risco,
)


class ArgsAbrir(Argumentos):
    nome: str = Field(description="Nome do aplicativo")


async def _abrir(args: ArgsAbrir) -> str:
    return f"abri {args.nome}"


def _ferramenta(nome="abrir_aplicativo", risco=Risco.SEGURO):
    return Ferramenta(nome=nome, descricao="Abre um aplicativo.", argumentos=ArgsAbrir, executar=_abrir, risco=risco)


def test_esquema_no_formato_do_ollama():
    registro = Registro()
    registro.registrar(_ferramenta())

    [esquema] = registro.esquemas()

    assert esquema == {
        "type": "function",
        "function": {
            "name": "abrir_aplicativo",
            "description": "Abre um aplicativo.",
            "parameters": {
                "type": "object",
                "properties": {"nome": {"type": "string", "description": "Nome do aplicativo"}},
                "required": ["nome"],
                "additionalProperties": False,
            },
        },
    }


def test_ferramenta_sem_argumentos_tem_objeto_vazio():
    registro = Registro()
    registro.registrar(
        Ferramenta(nome="hora_e_data", descricao="Hora.", argumentos=Argumentos, executar=_abrir)
    )

    [esquema] = registro.esquemas()

    assert esquema["function"]["parameters"]["properties"] == {}


def test_nome_duplicado_e_recusado():
    registro = Registro()
    registro.registrar(_ferramenta())

    with pytest.raises(ValueError):
        registro.registrar(_ferramenta())
