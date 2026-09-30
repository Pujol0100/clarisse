"""Lê em voz alta a última resposta do Claude Code, direto da conversa que ele grava nesta máquina."""
import json
import re
from pathlib import Path

from pydantic import Field

from clarisse.config import normalizar
from clarisse.ferramentas.registro import Argumentos, Ferramenta
from clarisse.figuras import MENSAGEM, Retorno

PASTA_DAS_CONVERSAS = Path.home() / ".claude" / "projects"


def _eh_pergunta(linha: dict) -> bool:
    """Linha que o usuário escreveu, e não resultado de ferramenta nem aviso do sistema."""
    if linha.get("type") != "user" or linha.get("isMeta") or linha.get("isSidechain"):
        return False
    conteudo = (linha.get("message") or {}).get("content")
    if isinstance(conteudo, str):
        return True
    return any(isinstance(c, dict) and c.get("type") == "text" for c in conteudo or [])


def ultima_resposta(conversa: Path) -> str | None:
    linhas = []
    for texto in conversa.read_text(encoding="utf-8").splitlines():
        try:
            linhas.append(json.loads(texto))
        except json.JSONDecodeError:
            continue
    perguntas = [i for i, linha in enumerate(linhas) if _eh_pergunta(linha)]
    depois = linhas[perguntas[-1] + 1:] if perguntas else linhas
    partes = [
        c["text"].strip()
        for linha in depois
        if linha.get("type") == "assistant" and not linha.get("isSidechain")
        for c in (linha.get("message") or {}).get("content") or []
        if isinstance(c, dict) and c.get("type") == "text" and c.get("text", "").strip()
    ]
    return "\n\n".join(partes) or None


def _pasta_do_projeto(cwd: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "-", cwd)


class ArgsLeitura(Argumentos):
    conversa: str | None = Field(
        default=None, max_length=80,
        description="Nome da conversa do Claude, se o usuário disser; vazio lê a conversa mais recente",
    )


def ferramentas_de_leitura(executor, pasta_das_conversas: Path = PASTA_DAS_CONVERSAS) -> list[Ferramenta]:

    async def achar_pelo_nome(nome: str) -> Path | str:
        listagem = await executor.executar(["claude", "agents", "--json"], timeout=30)
        try:
            sessoes = json.loads(listagem.saida)
        except json.JSONDecodeError:
            return "Não consegui ver as conversas do Claude abertas agora."
        alvo = normalizar(nome)
        exatas = [s for s in sessoes if normalizar(s.get("name") or "") == alvo]
        achadas = exatas or [s for s in sessoes if alvo in normalizar(s.get("name") or "")]
        if not achadas:
            nomes = ", ".join(s.get("name") or "sem nome" for s in sessoes) or "nenhuma"
            return f"Não achei a conversa {nome}. Abertas agora: {nomes}."
        sessao = achadas[0]
        return pasta_das_conversas / _pasta_do_projeto(sessao["cwd"]) / f"{sessao['sessionId']}.jsonl"

    async def ler_resposta_do_claude(args: ArgsLeitura) -> Retorno | str:
        if args.conversa:
            conversa = await achar_pelo_nome(args.conversa)
            if isinstance(conversa, str):
                return conversa
        else:
            todas = list(pasta_das_conversas.glob("*/*.jsonl")) if pasta_das_conversas.is_dir() else []
            if not todas:
                return "Não achei nenhuma conversa do Claude nesta máquina."
            conversa = max(todas, key=lambda c: c.stat().st_mtime)
        if not conversa.is_file():
            return "Não achei o registro dessa conversa do Claude."
        texto = ultima_resposta(conversa)
        if not texto:
            return "A última pergunta dessa conversa ainda não tem resposta do Claude."
        return Retorno(texto, figura=MENSAGEM, na_integra=True)

    return [
        Ferramenta(
            "ler_resposta_do_claude",
            "Lê em voz alta, na íntegra, a última resposta do Claude Code: da conversa mais recente, ou da "
            "conversa que o usuário disser o nome. Use para 'lê o que o Claude respondeu', 'lê a última resposta'.",
            ArgsLeitura, ler_resposta_do_claude, figura=MENSAGEM,
        )
    ]
