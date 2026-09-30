"""Mede onde vai o tempo de `pedir_ao_claude`: o mesmo comando da Clarisse e variações.

Rode da raiz do repositório:  uv run python docs/medicoes/2026-09-30-claude-lento/medir.py
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from clarisse.ferramentas.claude import _PARA_VOZ, _PESQUISE, FERRAMENTAS_DE_LEITURA  # noqa: E402

PASTA = Path.home() / ".local" / "share" / "clarisse" / "claude"
PERGUNTAS = ["Qual é a capital do Canadá?", "O que faz a empresa Smart Compass, de Campinas?"]


def comando(pedido: str, modelo: str, sem_conectores: bool) -> list[str]:
    args = [
        "claude", "-p", f"{pedido}\n\n{_PESQUISE}",
        "--output-format", "json", "--setting-sources", "project", "--no-session-persistence",
        "--model", modelo, "--max-budget-usd", "0.5", "--append-system-prompt", _PARA_VOZ,
        "--allowedTools", ",".join(FERRAMENTAS_DE_LEITURA), "--tools", ",".join(FERRAMENTAS_DE_LEITURA),
    ]
    if sem_conectores:
        args += ["--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}']
    return args


def medir(nome: str, pedido: str, modelo: str, sem_conectores: bool, esperar_conectores: bool) -> None:
    ambiente = {**os.environ}
    if esperar_conectores:
        ambiente["MCP_CONNECTION_NONBLOCKING"] = "false"
    inicio = time.monotonic()
    saida = subprocess.run(comando(pedido, modelo, sem_conectores), cwd=PASTA, env=ambiente,
                           capture_output=True, text=True, timeout=300)
    total = time.monotonic() - inicio
    dados = json.loads(saida.stdout)
    print(f"{nome:<34} | {pedido[:28]:<28} | total {total:5.1f}s | api {dados['duration_api_ms'] / 1000:5.1f}s"
          f" | voltas {dados['num_turns']} | US$ {dados['total_cost_usd']:.3f}")


if __name__ == "__main__":
    for pedido in PERGUNTAS:
        medir("atual (sonnet, espera conectores)", pedido, "sonnet", False, True)
        medir("sonnet sem conectores", pedido, "sonnet", True, False)
        medir("haiku sem conectores", pedido, "haiku", True, False)
