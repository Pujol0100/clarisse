"""Única porta para executar programas: lista de argumentos, sem shell, com tempo limite e ambiente mínimo."""
import asyncio
import os
from dataclasses import dataclass
from pathlib import Path

_PALAVRAS_DE_SEGREDO = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL", "AUTH")
_VARIAVEIS_DA_SESSAO = (
    "HOME", "PATH", "USER", "LOGNAME", "LANG", "LANGUAGE", "LC_ALL", "SHELL", "TERM",
    "DISPLAY", "WAYLAND_DISPLAY", "XDG_RUNTIME_DIR", "XDG_SESSION_TYPE", "XDG_CURRENT_DESKTOP",
    "XDG_DATA_DIRS", "XDG_CONFIG_DIRS", "DBUS_SESSION_BUS_ADDRESS", "PULSE_SERVER",
)


def ambiente_minimo() -> dict[str, str]:
    return {
        k: v
        for k, v in os.environ.items()
        if k in _VARIAVEIS_DA_SESSAO and not any(p in k.upper() for p in _PALAVRAS_DE_SEGREDO)
    }


@dataclass
class Resultado:
    codigo: int | None
    saida: str
    erro: str
    estourou_tempo: bool = False


def _conferir(argumentos) -> list[str]:
    if not isinstance(argumentos, list) or not all(isinstance(a, str) for a in argumentos):
        raise TypeError("argumentos devem ser uma lista de strings; shell não é permitido")
    return argumentos


class Executor:
    async def executar(self, argumentos: list[str], pasta: Path | None = None, timeout: float = 30) -> Resultado:
        processo = await asyncio.create_subprocess_exec(
            *_conferir(argumentos),
            cwd=pasta,
            env=ambiente_minimo(),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            start_new_session=True,
        )
        try:
            saida, erro = await asyncio.wait_for(processo.communicate(), timeout)
        except TimeoutError:
            os.killpg(processo.pid, 9)
            await processo.wait()
            return Resultado(None, "", "", estourou_tempo=True)
        return Resultado(processo.returncode, saida.decode(errors="replace"), erro.decode(errors="replace"))

    async def iniciar(self, argumentos: list[str], pasta: Path | None = None) -> None:
        await asyncio.create_subprocess_exec(
            *_conferir(argumentos),
            cwd=pasta,
            env=ambiente_minimo(),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
        )
