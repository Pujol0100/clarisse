"""Terminal visível: uma janela nova do Windows Terminal com PowerShell, que fica aberta mostrando o erro."""
import base64
from pathlib import Path


def em_aspas(texto: str) -> str:
    """Texto literal para o PowerShell: entre aspas simples nada é expandido."""
    return "'" + texto.replace("'", "''") + "'"


def terminal(pasta: Path, comando: str) -> list[str]:
    # Codificado, o comando passa inteiro: o wt.exe partiria a linha em cada ponto e vírgula.
    codificado = base64.b64encode(comando.encode("utf-16-le")).decode("ascii")
    return ["wt.exe", "-w", "new", "-d", str(pasta), "powershell.exe", "-NoExit", "-EncodedCommand", codificado]
