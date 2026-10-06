"""Única porta para executar programas: lista de argumentos, sem shell, com tempo limite e ambiente mínimo."""
import asyncio
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import psutil

_PALAVRAS_DE_SEGREDO = ("KEY", "TOKEN", "SECRET", "PASSWORD", "PASSWD", "CREDENTIAL", "AUTH")
_VARIAVEIS_DA_SESSAO = (
    "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "SYSTEMDRIVE", "TEMP", "TMP",
    "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "USERNAME", "USERDOMAIN", "COMPUTERNAME",
    "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432",
    "COMMONPROGRAMFILES", "COMMONPROGRAMFILES(X86)", "OS", "PROCESSOR_ARCHITECTURE",
    "NUMBER_OF_PROCESSORS", "LANG",
)
# Num .cmd ou .bat o cmd.exe interpreta estes caracteres, mesmo vindo como argumento separado.
_CARACTERES_DO_CMD = set('&|<>^%"!')


def ambiente_minimo() -> dict[str, str]:
    return {
        k: v
        for k, v in os.environ.items()
        if k.upper() in _VARIAVEIS_DA_SESSAO and not any(p in k.upper() for p in _PALAVRAS_DE_SEGREDO)
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


def _resolver(argumentos: list[str], ambiente: dict[str, str]) -> list[str]:
    """O Windows só completa .exe: `code` é `code.cmd`, e quem acha é o PATH com o PATHEXT."""
    programa = shutil.which(argumentos[0], path=ambiente.get("PATH")) or argumentos[0]
    if programa.lower().endswith((".cmd", ".bat")) and any(_CARACTERES_DO_CMD & set(a) for a in argumentos[1:]):
        raise ValueError("argumento com caractere que o cmd.exe interpretaria")
    return [programa, *argumentos[1:]]


def _encerrar_arvore(pid: int) -> None:
    try:
        processo = psutil.Process(pid)
        for filho in processo.children(recursive=True):
            filho.kill()
        processo.kill()
    except psutil.NoSuchProcess:
        pass


class Executor:
    async def executar(
        self, argumentos: list[str], pasta: Path | None = None, timeout: float = 30,
        ambiente: dict[str, str] | None = None,
    ) -> Resultado:
        env = {**ambiente_minimo(), "PYTHONUTF8": "1", **(ambiente or {})}
        processo = await asyncio.create_subprocess_exec(
            *_resolver(_conferir(argumentos), env),
            cwd=pasta,
            env=env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        try:
            saida, erro = await asyncio.wait_for(processo.communicate(), timeout)
        except TimeoutError:
            _encerrar_arvore(processo.pid)
            await processo.wait()
            return Resultado(None, "", "", estourou_tempo=True)
        return Resultado(processo.returncode, saida.decode(errors="replace"), erro.decode(errors="replace"))

    async def iniciar(self, argumentos: list[str], pasta: Path | None = None) -> None:
        env = {**ambiente_minimo(), "PYTHONUTF8": "1"}
        await asyncio.create_subprocess_exec(
            *_resolver(_conferir(argumentos), env),
            cwd=pasta,
            env=env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )

    async def abrir(self, alvo: str) -> None:
        """Pasta, arquivo ou endereço no programa padrão do Windows."""
        os.startfile(alvo)

    async def encerrar(self, processo: str) -> int:
        """Fecha todo processo com esse nome (chrome.exe); devolve quantos fechou."""
        alvos = [p for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == processo.lower()]
        for alvo in alvos:
            try:
                alvo.terminate()
            except psutil.NoSuchProcess:
                pass
        psutil.wait_procs(alvos, timeout=5)
        return len(alvos)
