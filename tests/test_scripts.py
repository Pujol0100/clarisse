"""Os scripts de scripts/ são chamados direto (pelo menu Iniciar, pelo PowerShell)."""
import json
import subprocess
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _erros_de_sintaxe(script: Path) -> list[str]:
    analise = (
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; $erros = $null; "
        f"[void][System.Management.Automation.Language.Parser]::ParseFile('{script}', [ref]$null, [ref]$erros); "
        "ConvertTo-Json -InputObject @($erros | ForEach-Object { $_.Message })"
    )
    saida = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", analise], capture_output=True, encoding="utf-8", check=True,
    ).stdout
    return json.loads(saida or "[]")


def test_todo_script_e_powershell_sem_erro_de_sintaxe():
    scripts = sorted(SCRIPTS.glob("*.ps1"))

    assert scripts
    assert {s.name: _erros_de_sintaxe(s) for s in scripts} == {s.name: [] for s in scripts}
