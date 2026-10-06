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
        self.ambientes: list[dict[str, str]] = []
        self.abertos: list[str] = []
        self.encerrados: list[str] = []
        self.quantos_encerrar = 1

    async def executar(self, argumentos, pasta=None, timeout=30, ambiente=None):
        self.executados.append((argumentos, pasta))
        self.ambientes.append(ambiente or {})
        return self.respostas.pop(0) if self.respostas else Resultado(0, "", "")

    async def iniciar(self, argumentos, pasta=None):
        self.iniciados.append((argumentos, pasta))

    async def abrir(self, alvo):
        self.abertos.append(alvo)

    async def encerrar(self, processo):
        self.encerrados.append(processo)
        return self.quantos_encerrar


class AreaFalsa:
    """Registra o que seria feito nas janelas, sem tocar na área de trabalho de verdade."""

    def __init__(self):
        self.janelas: list[dict] = []
        self.ativadas: list[int] = []
        self.coladas: list[str] = []
        self.apertadas: list[str] = []

    def listar(self):
        return list(self.janelas)

    def ativar(self, janela):
        self.ativadas.append(janela)

    def colar(self, texto):
        self.coladas.append(texto)

    def apertar(self, teclas):
        self.apertadas.append(teclas)


@pytest.fixture
def executor():
    return ExecutorFalso()


@pytest.fixture
def area():
    return AreaFalsa()


@pytest.fixture
def cadastros(tmp_path):
    projeto = tmp_path / "omni-api"
    projeto.mkdir()
    return Cadastros(
        projetos={"omni-api": projeto, "smart-cep": tmp_path / "smart-cep"},
        aplicativos={
            "vscode": Aplicativo(abrir=["code"], processo="Code.exe", apelidos=["vs code"]),
            "chrome": Aplicativo(abrir=["chrome"], processo="chrome.exe", apelidos=["navegador"]),
        },
        pastas={"downloads": Path.home() / "Downloads"},
    )
