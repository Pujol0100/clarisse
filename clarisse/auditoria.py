"""Registro de cada ferramenta executada, uma linha JSON por execução, só na máquina."""
import json
from datetime import datetime
from pathlib import Path


class Auditoria:
    def __init__(self, caminho: Path):
        self._caminho = caminho

    def registrar(self, **campos) -> None:
        self._caminho.parent.mkdir(parents=True, exist_ok=True)
        linha = {"quando": datetime.now().isoformat(timespec="seconds"), **campos}
        with self._caminho.open("a", encoding="utf-8") as arquivo:
            arquivo.write(json.dumps(linha, ensure_ascii=False, default=str) + "\n")
