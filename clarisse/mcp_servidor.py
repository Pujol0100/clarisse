"""Servidor MCP da Clarisse: dá ao Claude as ferramentas dela, sem executar nada aqui.

Cada chamada é repassada à Clarisse que está ligada (rotas /api/ferramentas e /api/ferramenta,
com a chave da sessão). Lá valem a mesma avaliação, a confirmação pela voz, a auditoria e as
figuras dos drones. Rode com: python -m clarisse.mcp_servidor
"""
import asyncio
import os
from pathlib import Path

import httpx
from mcp import types
from mcp.server.lowlevel import Server
from mcp.server.stdio import stdio_server

CAMINHO_DA_CHAVE = Path.home() / ".config" / "clarisse" / "chave"
# Confirmação pela voz (até 60 s) mais a ferramenta (até 180 s).
_ESPERA = 300


async def listar(http: httpx.AsyncClient) -> list[types.Tool]:
    resposta = await http.get("/api/ferramentas", timeout=30)
    resposta.raise_for_status()
    return [
        types.Tool(name=f["nome"], description=f["descricao"], input_schema=f["parametros"])
        for f in resposta.json()["ferramentas"]
    ]


async def chamar(http: httpx.AsyncClient, nome: str, argumentos: dict) -> types.CallToolResult:
    try:
        resposta = await http.post("/api/ferramenta", json={"nome": nome, "argumentos": argumentos}, timeout=_ESPERA)
        resposta.raise_for_status()
        texto, erro = resposta.json()["resultado"], False
    except httpx.HTTPError as falha:
        texto, erro = f"Não consegui falar com a Clarisse (ela está ligada?): {type(falha).__name__}.", True
    return types.CallToolResult(content=[types.TextContent(type="text", text=texto)], is_error=erro)


def _cliente() -> httpx.AsyncClient:
    porta = os.environ.get("CLARISSE_PORTA", "8765")
    return httpx.AsyncClient(
        base_url=f"http://127.0.0.1:{porta}", headers={"X-Clarisse-Chave": CAMINHO_DA_CHAVE.read_text().strip()},
    )


async def main() -> None:
    http = _cliente()

    async def ao_listar(contexto, parametros):
        return types.ListToolsResult(tools=await listar(http))

    async def ao_chamar(contexto, parametros):
        return await chamar(http, parametros.name, parametros.arguments or {})

    servidor = Server("clarisse", on_list_tools=ao_listar, on_call_tool=ao_chamar)
    async with stdio_server() as (leitura, escrita):
        await servidor.run(leitura, escrita, servidor.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
