"""Lê em voz alta a última resposta do Claude Code, direto da conversa que ele grava nesta máquina."""
import json
import re
from pathlib import Path

from pydantic import Field

from clarisse.cartoes import Retorno
from clarisse.config import Cadastros, normalizar
from clarisse.ferramentas.projetos import projeto_desconhecido
from clarisse.ferramentas.registro import Argumentos, Ferramenta

PASTA_DAS_CONVERSAS = Path.home() / ".claude" / "projects"
# Para achar a conversa de um projeto, olha só as mais recentes: cada uma pode ter vários MB.
_CONVERSAS_OLHADAS = 30


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
    projeto: str | None = Field(
        default=None, max_length=80,
        description="Projeto cadastrado, se o usuário disser 'no projeto X'; lê a conversa mais recente dele",
    )
    conversa: str | None = Field(
        default=None, max_length=80,
        description="Nome da conversa do Claude, se o usuário disser; vazio lê a conversa mais recente",
    )


def _mexeu_no_projeto(conversa: Path, marcas: tuple[str, ...]) -> bool:
    """Conta só a pasta onde o Claude estava e o que as ferramentas dele usaram; citar o caminho num
    texto ou receber o caminho num resultado não faz da conversa uma conversa do projeto."""
    texto = conversa.read_text(encoding="utf-8", errors="ignore")
    for bruta in texto.splitlines():
        if not any(m in bruta for m in marcas):
            continue
        try:
            linha = json.loads(bruta)
        except json.JSONDecodeError:
            continue
        if any(m in f"{linha.get('cwd') or ''}/" for m in marcas):
            return True
        if linha.get("type") != "assistant":
            continue
        for item in (linha.get("message") or {}).get("content") or []:
            if isinstance(item, dict) and item.get("type") == "tool_use":
                entrada = json.dumps(item.get("input"), ensure_ascii=False)
                if any(m in entrada for m in marcas):
                    return True
    return False


def _mais_recente(conversas: list[Path]) -> Path | None:
    return max(conversas, key=lambda c: c.stat().st_mtime) if conversas else None


def ferramentas_de_leitura(
    executor, pasta_das_conversas: Path = PASTA_DAS_CONVERSAS, cadastros: Cadastros | None = None,
) -> list[Ferramenta]:
    cadastros = cadastros or Cadastros()

    def achar_pelo_projeto(nome: str) -> Path | str:
        """A conversa mais recente do projeto: aberta na pasta dele, ou aberta noutra pasta (quase sempre a
        pasta geral dos projetos) mas que mexeu em arquivos dele ou de uma worktree dele."""
        chave = cadastros.achar_projeto(nome)
        if chave is None:
            return projeto_desconhecido(cadastros, nome)
        caminho = cadastros.projetos[chave]
        propria = pasta_das_conversas / _pasta_do_projeto(str(caminho))
        marcas = (f"{caminho}/", f"/worktrees/{caminho.name}/")
        recentes = sorted(
            pasta_das_conversas.glob("*/*.jsonl") if pasta_das_conversas.is_dir() else [],
            key=lambda c: c.stat().st_mtime, reverse=True,
        )[:_CONVERSAS_OLHADAS]
        for conversa in recentes:
            if conversa.parent == propria or _mexeu_no_projeto(conversa, marcas):
                return conversa
        return f"Não achei conversa do Claude no projeto {chave}."

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
        if args.projeto or args.conversa:
            conversa = achar_pelo_projeto(args.projeto) if args.projeto else await achar_pelo_nome(args.conversa)
            if isinstance(conversa, str):
                return conversa
        else:
            todas = list(pasta_das_conversas.glob("*/*.jsonl")) if pasta_das_conversas.is_dir() else []
            if not todas:
                return "Não achei nenhuma conversa do Claude nesta máquina."
            conversa = _mais_recente(todas)
        if not conversa.is_file():
            return "Não achei o registro dessa conversa do Claude."
        texto = ultima_resposta(conversa)
        if not texto:
            return "A última pergunta dessa conversa ainda não tem resposta do Claude."
        return Retorno(texto, na_integra=True)

    return [
        Ferramenta(
            "ler_resposta_do_claude",
            "Lê em voz alta, na íntegra, a última resposta do Claude Code: da conversa mais recente, do projeto "
            "que o usuário disser ('no projeto omni-api') ou da conversa que ele disser o nome. Use para 'lê o que "
            "o Claude respondeu', 'lê a última resposta', 'o que o Claude disse no projeto X'.",
            ArgsLeitura, ler_resposta_do_claude, grupo="claude",
        )
    ]
