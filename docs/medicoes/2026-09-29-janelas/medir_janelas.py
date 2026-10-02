"""Mede se o modelo escolhe as ferramentas de janela, com o registro e o prompt reais da Clarisse.

Uso, na raiz do projeto: uv run python docs/medicoes/2026-09-29-janelas/medir_janelas.py
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

# (pedido, ferramenta esperada ou None, {argumento: trecho esperado no valor}); "alvo" junta aplicativo e título
CASOS = [
    ("traz o vs code pra frente", "trazer_para_frente", {"aplicativo": "code"}),
    ("mostra a janela do chrome", "trazer_para_frente", {"aplicativo": "chrome"}),
    ("coloca o whatsapp na frente", "trazer_para_frente", {"aplicativo": "whats"}),
    ("volta pro terminal", "trazer_para_frente", {"aplicativo": "terminal"}),
    ("escreve bom dia equipe no whatsapp", "digitar_texto", {"texto": "bom dia"}),
    ("digita git status no terminal", "digitar_texto", {"texto": "git status"}),
    ("escreve olá mundo no sublime", "digitar_texto", {"texto": "mundo"}),
    ("salva o arquivo no vs code", "apertar_atalho", {"atalho": "salvar", "alvo": "code"}),
    ("salva o rascunho clarisse", "apertar_atalho", {"atalho": "salvar", "alvo": "clarisse"}),
    ("aperta enter", "apertar_atalho", {"atalho": "enter"}),
    ("desfaz isso", "apertar_atalho", {"atalho": "desfazer"}),
    ("fecha essa aba do chrome", "apertar_atalho", {"atalho": "fechar_aba", "alvo": "chrome"}),
    ("abre uma aba nova no navegador", "apertar_atalho", {"atalho": "nova_aba", "alvo": "navegador"}),
    ("aperta esc", "apertar_atalho", {"atalho": "esc"}),
    # não podem virar ferramenta de janela
    ("vai pro vs code do projeto clarisse", "abrir_projeto_vscode", {"projeto": "clarisse"}),
    ("abre o vs code", "abrir_aplicativo", {}),
    ("abre o projeto omni api no vs code", "abrir_projeto_vscode", {}),
    ("vai no VS Code na aba da Clarisse e digita obrigado", "mandar_para_conversa_do_claude", {}),
    ("fecha o chrome", "fechar_aplicativo", {}),
    ("que horas são?", "hora_e_data", {}),
    ("oi clarisse, tudo bem?", None, {}),
    ("o que é uma API?", None, {}),
    ("me conta uma curiosidade rápida", None, {}),
    ("quanto é quinze por cento de duzentos?", None, {}),
    ("obrigado, era só isso", None, {}),
]


def _sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", str(texto).lower()) if unicodedata.category(c) != "Mn")


async def main():
    ajustes = Ajustes(_env_file=RAIZ / ".env", pasta_config=RAIZ / "config")
    cadastros = carregar_cadastros(ajustes.pasta_config)

    async def _avisar(*_):
        pass

    registro = montar_registro(ajustes, cadastros, None, httpx.AsyncClient(), Delegacoes(_avisar))
    sistema = prompt_do_sistema(list(cadastros.projetos), datetime.now(), ajustes.cidade)
    ferramentas = [e for e in registro.esquemas() if e["function"]["name"] not in SEM]
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
            recebidos_com_alvo = {**recebidos, "alvo": f"{recebidos.get('aplicativo') or ''} {recebidos.get('titulo') or ''}"}
            ok = nome == esperada and all(_sem_acento(v) in _sem_acento(recebidos_com_alvo.get(k, "")) for k, v in args.items())
            acertos += ok
            texto = "" if chamadas else msg.get("content", "")[:80]
            print(f"{'OK ' if ok else 'ERR'} {pedido!r} -> {nome} {json.dumps(recebidos, ensure_ascii=False)} {texto}", flush=True)
    print(f"{acertos}/{len(CASOS)}")


asyncio.run(main())
