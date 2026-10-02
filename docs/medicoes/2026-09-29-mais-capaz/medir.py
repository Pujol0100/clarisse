"""Mede as ferramentas do plano "Clarisse mais capaz" com o registro e o prompt reais da Clarisse.

Uso, na raiz do projeto: uv run python docs/medicoes/2026-09-29-mais-capaz/medir.py
SEM=nome1,nome2 tira ferramentas do registro, para comparar.
"""
import asyncio
import json
import os
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

import httpx

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))

from clarisse.agente import prompt_do_sistema  # noqa: E402
from clarisse.config import Ajustes, carregar_cadastros  # noqa: E402
from clarisse.ferramentas.claude import Delegacoes  # noqa: E402
from clarisse.montagem import montar_registro  # noqa: E402

SEM = set(filter(None, os.environ.get("SEM", "").split(",")))

# (pedido, ferramenta esperada ou None, {argumento: trecho esperado no valor}); "participantes" junta a lista
CASOS = [
    ("lê a última resposta do Claude", "ler_resposta_do_claude", {}),
    ("lê o que o Claude acabou de responder", "ler_resposta_do_claude", {}),
    ("Clarisse, lê pra mim a resposta do Claude", "ler_resposta_do_claude", {}),
    ("lê a última resposta da conversa clarisse", "ler_resposta_do_claude", {"conversa": "clarisse"}),
    ("lê a resposta do Claude na conversa do omni", "ler_resposta_do_claude", {"conversa": "omni"}),
    ("pergunta pro Claude o que é REST", "pedir_ao_claude", {}),
    ("manda pra conversa omni do Claude: roda os testes de novo", "mandar_para_conversa_do_claude", {}),
    ("abre o Claude no omni api e pede pra ele corrigir o teste", "abrir_claude_na_tela", {}),
    ("que horas são?", "hora_e_data", {}),
    ("oi clarisse, tudo bem?", None, {}),
]


def _sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", str(texto).lower()) if unicodedata.category(c) != "Mn")


async def main():
    ajustes = Ajustes(_env_file=RAIZ / ".env", pasta_config=RAIZ / "config")
    cadastros = carregar_cadastros(ajustes.pasta_config)

    async def _avisar(*_):
        pass

    registro = montar_registro(ajustes, cadastros, None, httpx.AsyncClient(), Delegacoes(_avisar))
    from clarisse.sites import carregar_sites
    sistema = prompt_do_sistema(
        list(cadastros.projetos), datetime.now(), ajustes.cidade, [x.nome for x in carregar_sites(RAIZ / "config")]
    ) + os.environ.get("EXTRA", "")

    ferramentas = [e for e in registro.esquemas() if e["function"]["name"] not in SEM]
    if os.environ.get("VSCODE"):
        for e in ferramentas:
            if e["function"]["name"] == "abrir_projeto_vscode":
                e["function"]["description"] = "Abre um projeto no editor VS Code. Só quando o usuário falar em VS Code, code ou editor."
    acertos = 0
    async with httpx.AsyncClient(timeout=300) as http:
        for pedido, esperada, args in CASOS:
            corpo = {
                "model": ajustes.modelo, "stream": False, "think": False,
                "messages": [{"role": "system", "content": sistema}, {"role": "user", "content": pedido}],
                "tools": ferramentas, "options": {"temperature": 0, "num_ctx": 8192},
            }
            msg = (await http.post(f"{ajustes.ollama_url}/api/chat", json=corpo)).json()["message"]
            chamadas = msg.get("tool_calls") or []
            nome = chamadas[0]["function"]["name"] if chamadas else None
            recebidos = chamadas[0]["function"].get("arguments", {}) if chamadas else {}
            # "alvo": o programa citado pode vir no aplicativo ou no título; os dois levam à janela.
            recebidos = {**recebidos, "participantes": " ".join(recebidos.get("participantes") or [])}
            recebidos_com_alvo = {**recebidos, "alvo": f"{recebidos.get('aplicativo') or ''} {recebidos.get('titulo') or ''}"}
            ok = nome == esperada and all(
                not recebidos.get(k) if v is None else _sem_acento(v) in _sem_acento(recebidos_com_alvo.get(k, ""))
                for k, v in args.items()
            )
            acertos += ok
            texto = "" if chamadas else msg.get("content", "")[:80]
            print(f"{'OK ' if ok else 'ERR'} {pedido!r} -> {nome} {json.dumps(recebidos, ensure_ascii=False)} {texto}", flush=True)
    print(f"{acertos}/{len(CASOS)}")


asyncio.run(main())
