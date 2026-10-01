"""Os scripts de scripts/ são chamados direto (pelo atalho do GNOME, pelo menu, pelo terminal)."""
import os
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def test_todo_script_pode_ser_executado_direto():
    sem_permissao = [s.name for s in sorted(SCRIPTS.glob("*.sh")) if not os.access(s, os.X_OK)]

    assert sem_permissao == []
