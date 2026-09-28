"""Mede se um modelo local escolhe a ferramenta certa para pedidos falados em português.

Uso: python3 medir_roteador.py <modelo> [<modelo> ...]
Grava resultado_<modelo>.json ao lado deste arquivo.
"""
import json
import os
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

OLLAMA = "http://127.0.0.1:11434"
NUM_CTX = int(os.environ.get("NUM_CTX", "8192"))
SUFIXO = os.environ.get("SUFIXO", "")
AQUI = Path(__file__).parent

PROJETOS = ["omni-api", "omni-app", "sienge-automacao", "clarisse", "smart-cep", "conciliacao-bancaria"]

SISTEMA = f"""Você é a Clarisse, assistente de voz que roda no computador do usuário.
Responda sempre em português do Brasil, em no máximo duas frases curtas, porque a resposta será falada.
Quando o pedido exigir uma ação ou uma informação do mundo real, chame a ferramenta adequada. Nunca invente o resultado de uma ferramenta.
Para conversa, contas simples ou conhecimento geral, responda direto, sem ferramenta.
Tarefas complexas de programação, análise, leitura de sites ou agenda vão para o Claude.{os.environ.get("REGRA_EXTRA", "")}
Projetos cadastrados: {", ".join(PROJETOS)}. A transcrição de voz pode errar o nome; escolha o projeto cadastrado mais parecido."""


def ferramenta(nome, descricao, props=None, obrigatorios=None):
    return {
        "type": "function",
        "function": {
            "name": nome,
            "description": descricao,
            "parameters": {
                "type": "object",
                "properties": props or {},
                "required": obrigatorios or [],
            },
        },
    }


TXT = {"type": "string"}
PROJ = {"type": "string", "enum": PROJETOS, "description": "Nome do projeto cadastrado"}

FERRAMENTAS = [
    ferramenta("hora_e_data", "Informa a hora e a data atuais."),
    ferramenta("abrir_aplicativo", "Abre um aplicativo instalado.", {"nome": TXT}, ["nome"]),
    ferramenta("fechar_aplicativo", "Fecha um aplicativo aberto.", {"nome": TXT}, ["nome"]),
    ferramenta("listar_programas_abertos", "Lista os programas abertos no computador."),
    ferramenta("abrir_pasta", "Abre uma pasta no gerenciador de arquivos.", {"pasta": TXT}, ["pasta"]),
    ferramenta("abrir_projeto_vscode", "Abre um projeto no VS Code.", {"projeto": PROJ}, ["projeto"]),
    ferramenta(
        "abrir_claude_na_tela",
        "Abre o VS Code no projeto e inicia o Claude Code visível, já com o pedido do usuário. Use quando o usuário quer ver o Claude trabalhando.",
        {"projeto": PROJ, "pedido": TXT},
        ["projeto", "pedido"],
    ),
    ferramenta(
        "pedir_ao_claude",
        "Delega uma tarefa complexa ao Claude em segundo plano e depois fala o resultado. Serve para programação, análise, ler dashboards e sites, e dúvidas difíceis.",
        {"pedido": TXT, "projeto": {**PROJ, "description": "Projeto, se o pedido for sobre um"}},
        ["pedido"],
    ),
    ferramenta(
        "git",
        "Executa uma operação git num projeto.",
        {"projeto": PROJ, "operacao": {"type": "string", "enum": ["status", "log", "pull"]}},
        ["projeto", "operacao"],
    ),
    ferramenta("noticias_do_dia", "Busca as manchetes de hoje.", {"tema": {"type": "string", "description": "Tema opcional"}}),
    ferramenta("previsao_do_tempo", "Consulta a previsão do tempo.", {"cidade": TXT}),
    ferramenta(
        "criar_compromisso",
        "Cria um compromisso ou lembrete na agenda.",
        {"titulo": TXT, "quando": {"type": "string", "description": "Data e hora como o usuário falou"}},
        ["titulo", "quando"],
    ),
    ferramenta("consultar_agenda", "Lê os compromissos da agenda.", {"periodo": TXT}),
    ferramenta("enviar_whatsapp", "Envia uma mensagem de WhatsApp.", {"contato": TXT, "mensagem": TXT}, ["contato", "mensagem"]),
    ferramenta("abrir_site", "Abre um site no navegador.", {"endereco": TXT}, ["endereco"]),
    ferramenta("ajustar_volume", "Ajusta o volume do sistema.", {"nivel": {"type": "integer", "minimum": 0, "maximum": 100}}, ["nivel"]),
    ferramenta("parar", "Interrompe o que a Clarisse está fazendo ou falando."),
]

# (pedido, ferramenta esperada ou None, {argumento: trecho esperado no valor})
CASOS = [
    ("que horas são?", "hora_e_data", {}),
    ("que dia é hoje?", "hora_e_data", {}),
    ("abre o spotify", "abrir_aplicativo", {"nome": "spotify"}),
    ("fecha o chrome pra mim", "fechar_aplicativo", {"nome": "chrome"}),
    ("quais programas estão abertos agora?", "listar_programas_abertos", {}),
    ("abre a pasta de downloads", "abrir_pasta", {"pasta": "download"}),
    ("abre o projeto omni api no vs code", "abrir_projeto_vscode", {"projeto": "omni-api"}),
    ("abre o homem in api no visual code", "abrir_projeto_vscode", {"projeto": "omni-api"}),
    ("abre o sienge no vscode", "abrir_projeto_vscode", {"projeto": "sienge-automacao"}),
    ("abre o claude no smart cep e pede pra ele corrigir o teste que está falhando", "abrir_claude_na_tela", {"projeto": "smart-cep", "pedido": "teste"}),
    ("inicia o claude code no projeto clarisse pra eu ver ele criando a tela da bola neural", "abrir_claude_na_tela", {"projeto": "clarisse", "pedido": "bola"}),
    ("pede pro claude revisar o último pull request do omni app e me fala o resultado", "pedir_ao_claude", {"projeto": "omni-app"}),
    ("pergunta pro claude por que o build da conciliação bancária está quebrando", "pedir_ao_claude", {"projeto": "conciliacao-bancaria"}),
    ("lê o dashboard de vendas no site do omni e me diz o total do mês", "pedir_ao_claude", {}),
    ("quero conversar com o claude sobre uma aplicação nova de controle de estoque", "pedir_ao_claude", {"pedido": "estoque"}),
    ("roda um git status no omni api", "git", {"projeto": "omni-api", "operacao": "status"}),
    ("atualiza o repositório do smart cep", "git", {"projeto": "smart-cep", "operacao": "pull"}),
    ("quais são as notícias de hoje?", "noticias_do_dia", {}),
    ("me dá as notícias de economia", "noticias_do_dia", {"tema": "economia"}),
    ("vai chover em curitiba amanhã?", "previsao_do_tempo", {"cidade": "curitiba"}),
    ("marca uma reunião com o joão amanhã às três da tarde", "criar_compromisso", {"titulo": "jo"}),
    ("me lembra de pagar o boleto sexta às nove", "criar_compromisso", {"titulo": "boleto"}),
    ("o que eu tenho na agenda hoje?", "consultar_agenda", {}),
    ("manda um whats pra maria dizendo que eu chego em dez minutos", "enviar_whatsapp", {"contato": "maria", "mensagem": "dez"}),
    ("abre o github", "abrir_site", {"endereco": "github"}),
    ("abaixa o volume pra trinta", "ajustar_volume", {"nivel": "30"}),
    ("para, clarisse", "parar", {}),
    ("oi clarisse, tudo bem?", None, {}),
    ("quanto é quinze por cento de duzentos?", None, {}),
    ("o que é uma API?", None, {}),
    ("obrigado, era só isso", None, {}),
    ("me conta uma curiosidade rápida", None, {}),
]


def sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", str(texto).lower()) if unicodedata.category(c) != "Mn")


def chat(modelo, pedido):
    corpo = {
        "model": modelo,
        "messages": [{"role": "system", "content": SISTEMA}, {"role": "user", "content": pedido}],
        "tools": FERRAMENTAS,
        "stream": False,
        "think": False,
        "keep_alive": "10m",
        "options": {"temperature": 0, "num_ctx": NUM_CTX},
    }
    req = urllib.request.Request(f"{OLLAMA}/api/chat", json.dumps(corpo).encode(), {"Content-Type": "application/json"})
    inicio = time.perf_counter()
    with urllib.request.urlopen(req, timeout=300) as resp:
        dados = json.load(resp)
    return dados, time.perf_counter() - inicio


def avaliar(esperada, args_esperados, mensagem):
    chamadas = mensagem.get("tool_calls") or []
    if esperada is None:
        return (not chamadas), "chamou ferramenta sem precisar" if chamadas else ""
    if not chamadas:
        return False, "não chamou ferramenta"
    fn = chamadas[0]["function"]
    if fn["name"] != esperada:
        return False, f"chamou {fn['name']}"
    args = fn.get("arguments") or {}
    for chave, trecho in args_esperados.items():
        if sem_acento(trecho) not in sem_acento(args.get(chave, "")):
            return False, f"argumento {chave}={args.get(chave)!r}"
    return True, ""


def medir(modelo):
    chat(modelo, "oi")  # carrega o modelo na placa; fora da conta
    linhas = []
    for pedido, esperada, args in CASOS:
        dados, segundos = chat(modelo, pedido)
        msg = dados["message"]
        ok, motivo = avaliar(esperada, args, msg)
        linhas.append({
            "pedido": pedido,
            "esperada": esperada,
            "ok": ok,
            "motivo": motivo,
            "segundos": round(segundos, 2),
            "prompt_tokens": dados.get("prompt_eval_count"),
            "saida_tokens": dados.get("eval_count"),
            "tool_calls": msg.get("tool_calls"),
            "texto": msg.get("content", "")[:200],
        })
        print(f"{'OK ' if ok else 'ERR'} {segundos:5.2f}s  {pedido}  {motivo}", flush=True)
    acertos = sum(l["ok"] for l in linhas)
    tempos = sorted(l["segundos"] for l in linhas)
    resumo = {
        "modelo": modelo,
        "acertos": acertos,
        "total": len(linhas),
        "mediana_s": tempos[len(tempos) // 2],
        "pior_s": tempos[-1],
    }
    print(json.dumps(resumo, ensure_ascii=False), flush=True)
    nome = modelo.replace(":", "_").replace("/", "_") + SUFIXO
    (AQUI / f"resultado_{nome}.json").write_text(json.dumps({"resumo": resumo, "casos": linhas}, ensure_ascii=False, indent=1))
    return resumo


if __name__ == "__main__":
    for m in sys.argv[1:]:
        medir(m)
