from pathlib import Path

import pytest

from clarisse.config import Aplicativo, Cadastros
from clarisse.ferramentas.processos import Resultado


class ExecutorFalso:
    """Registra o que seria executado, sem abrir nada de verdade."""

    def __init__(self):
        self.executados: list[tuple[list[str], Path | None]] = []
        self.iniciados: list[tuple[list[str], Path | None]] = []
        self.respostas: list[Resultado] = []

    async def executar(self, argumentos, pasta=None, timeout=30):
        self.executados.append((argumentos, pasta))
        return self.respostas.pop(0) if self.respostas else Resultado(0, "", "")

    async def iniciar(self, argumentos, pasta=None):
        self.iniciados.append((argumentos, pasta))


@pytest.fixture
def executor():
    return ExecutorFalso()


@pytest.fixture
def cadastros(tmp_path):
    projeto = tmp_path / "omni-api"
    projeto.mkdir()
    return Cadastros(
        projetos={"omni-api": projeto, "smart-cep": tmp_path / "smart-cep"},
        aplicativos={
            "vscode": Aplicativo(abrir=["code"], processo="code", apelidos=["vs code"]),
            "chrome": Aplicativo(abrir=["google-chrome"], processo="chrome", apelidos=["navegador"]),
        },
        pastas={"downloads": Path.home() / "Downloads"},
    )
