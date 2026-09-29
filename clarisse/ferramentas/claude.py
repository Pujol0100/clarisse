"""Ponte com o Claude Code: na tela, com o pedido já digitado, ou em segundo plano, com o resultado falado."""
import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path

from pydantic import Field, create_model

from clarisse.config import Cadastros, normalizar
from clarisse.figuras import CALENDARIO, CODIGO, MENSAGEM
from clarisse.ferramentas.projetos import campo_projeto, projeto_desconhecido
from clarisse.ferramentas.registro import Argumentos, Ferramenta, Risco
from clarisse.ferramentas.sistema import data_por_extenso

log = logging.getLogger(__name__)

FERRAMENTAS_DE_LEITURA = ["Read", "Grep", "Glob", "WebSearch", "WebFetch"]
_LER_AGENDA = "mcp__claude_ai_Microsoft_365__outlook_calendar_search"
_CRIAR_EVENTO = "mcp__claude_ai_Microsoft_365__outlook_create_event"
_PARA_VOZ = (
    "Sua resposta será lida em voz alta por uma assistente. Responda em português do Brasil, "
    "em no máximo quatro frases curtas, sem markdown, sem listas e sem caminhos de arquivo."
)
_TIMEOUT_DA_AGENDA = 120
_FERRAMENTAS_DE_MENSAGEM = ["SendMessage", "ListAgents"]


class Delegacoes:
    """Tarefas do Claude em segundo plano; o resultado de cada uma é entregue a `avisar`."""

    def __init__(self, avisar: Callable[[str, str], Awaitable[None]]):
        self._avisar = avisar
        self._tarefas: set[asyncio.Task] = set()

    def iniciar(self, titulo: str, trabalho: Awaitable[str]) -> None:
        tarefa = asyncio.create_task(self._entregar(titulo, trabalho))
        self._tarefas.add(tarefa)
        tarefa.add_done_callback(self._tarefas.discard)

    async def _entregar(self, titulo: str, trabalho: Awaitable[str]) -> None:
        try:
            texto = await trabalho
        except Exception:
            log.exception("delegação ao Claude falhou")
            texto = "O Claude não conseguiu terminar a tarefa por um erro interno. Os detalhes estão no log."
        await self._avisar(titulo, texto)

    async def aguardar(self) -> None:
        await asyncio.gather(*self._tarefas)


def _embutidas(ferramentas: list[str]) -> list[str]:
    """--allowedTools só pré-aprova; o que o Claude usa sem pedir (como SendMessage) só some com --tools.

    Conectores (mcp__) não são embutidos, mas só carregam pela ToolSearch.
    """
    embutidas = [f for f in ferramentas if not f.startswith("mcp__")]
    if len(embutidas) < len(ferramentas):
        embutidas.append("ToolSearch")
    return embutidas


async def rodar_claude(
    executor, pedido: str, pasta: Path, ferramentas: list[str], modelo: str, timeout: float, teto_usd: float
) -> str:
    resultado = await executor.executar(
        [
            "claude", "-p", pedido,
            "--output-format", "json",
            "--setting-sources", "project",
            "--no-session-persistence",
            "--model", modelo,
            "--max-budget-usd", str(teto_usd),
            "--append-system-prompt", _PARA_VOZ,
            "--allowedTools", ",".join(ferramentas),
            "--tools", ",".join(_embutidas(ferramentas)),
        ],
        pasta=pasta,
        timeout=timeout,
    )
    if resultado.estourou_tempo:
        return f"O Claude demorou mais de {int(timeout // 60)} minutos e eu interrompi."
    try:
        dados = json.loads(resultado.saida)
    except json.JSONDecodeError:
        log.warning("saída do claude sem JSON (código %s): %s", resultado.codigo, resultado.erro[:500])
        return "O Claude não conseguiu responder. O motivo está no log."
    if dados.get("subtype") == "error_max_budget_usd":
        return f"O Claude parou porque a tarefa passou do teto de gasto de {teto_usd} dólar por pedido."
    if dados.get("is_error") or not dados.get("result"):
        return "O Claude não conseguiu concluir a tarefa."
    return dados["result"].strip()


def ferramentas_do_claude(
    cadastros: Cadastros,
    executor,
    delegacoes: Delegacoes,
    pasta_neutra: Path,
    modelo: str,
    timeout: float,
    teto_usd: float,
    agora: Callable[[], datetime] = datetime.now,
    apos_mudar_agenda: Callable[[], Awaitable[None]] | None = None,
) -> list[Ferramenta]:
    ArgsNaTela = create_model(
        "ArgsNaTela",
        __base__=Argumentos,
        projeto=campo_projeto(cadastros),
        pedido=(str, Field(max_length=2000, description="O que o Claude deve fazer, com as palavras do usuário")),
    )
    ArgsPedido = create_model(
        "ArgsPedido",
        __base__=Argumentos,
        pedido=(str, Field(max_length=2000, description="A tarefa ou pergunta para o Claude")),
        projeto=campo_projeto(cadastros, "Projeto, se o pedido for sobre um", obrigatorio=False),
    )

    class ArgsAgenda(Argumentos):
        periodo: str = Field("hoje", max_length=100, description="Período, como o usuário falou")

    class ArgsCompromisso(Argumentos):
        titulo: str = Field(max_length=200, description="Título do compromisso")
        quando: str = Field(max_length=100, description="Data e hora como o usuário falou")

    def _pasta_neutra() -> Path:
        pasta_neutra.mkdir(parents=True, exist_ok=True)
        return pasta_neutra

    async def abrir_claude_na_tela(args) -> str:
        chave = cadastros.achar_projeto(args.projeto)
        if chave is None:
            return projeto_desconhecido(cadastros, args.projeto)
        pasta = str(cadastros.projetos[chave])
        await executor.iniciar(["code", pasta])
        await executor.iniciar(["ptyxis", "--new-window", "-d", pasta, "--", "claude", args.pedido])
        return f"Abri o VS Code e o Claude no projeto {chave}, já com o seu pedido."

    async def pedir_ao_claude(args) -> str:
        if args.projeto:
            chave = cadastros.achar_projeto(args.projeto)
            if chave is None:
                return projeto_desconhecido(cadastros, args.projeto)
            pasta, titulo = cadastros.projetos[chave], chave
        else:
            pasta, titulo = _pasta_neutra(), "Claude"
        delegacoes.iniciar(titulo, rodar_claude(executor, args.pedido, pasta, FERRAMENTAS_DE_LEITURA, modelo, timeout, teto_usd))
        return "Pedi ao Claude. Aviso quando ele terminar."

    async def consultar_agenda(args: ArgsAgenda) -> str:
        pedido = (
            f"Hoje é {data_por_extenso(agora())}. Liste meus compromissos de {args.periodo} "
            "com horário e título, usando a busca de calendário."
        )
        return await rodar_claude(executor, pedido, _pasta_neutra(), [_LER_AGENDA], modelo, _TIMEOUT_DA_AGENDA, teto_usd)

    async def criar_compromisso(args: ArgsCompromisso) -> str:
        pedido = (
            f"Hoje é {data_por_extenso(agora())}. Crie no meu calendário o compromisso "
            f"'{args.titulo}' para {args.quando}, com uma hora de duração se nada for dito. "
            "Confirme a data e a hora que ficaram."
        )
        resultado = await rodar_claude(executor, pedido, _pasta_neutra(), [_CRIAR_EVENTO], modelo, _TIMEOUT_DA_AGENDA, teto_usd)
        if apos_mudar_agenda:
            await apos_mudar_agenda()
        return resultado

    def confirmar_compromisso(args: ArgsCompromisso) -> str:
        return f"Vou criar na sua agenda: {args.titulo}, {args.quando}. Confirma?"

    class ArgsMensagem(Argumentos):
        conversa: str = Field(max_length=80, description="Nome da conversa do Claude, como o usuário falou")
        mensagem: str = Field(max_length=2000, description="O texto a entregar, com as palavras do usuário")

    async def mandar_para_conversa_do_claude(args: ArgsMensagem) -> str:
        listagem = await executor.executar(["claude", "agents", "--json"], timeout=30)
        try:
            nomes = [s["name"] for s in json.loads(listagem.saida)]
        except (json.JSONDecodeError, KeyError, TypeError):
            log.warning("claude agents não listou as conversas: %s", listagem.erro[:300])
            return "Não consegui ver as conversas do Claude abertas agora."
        alvo = normalizar(args.conversa)
        exatos = [n for n in nomes if normalizar(n) == alvo]
        parecidos = exatos or [n for n in nomes if alvo in normalizar(n)]
        if not parecidos:
            return f"Não achei conversa do Claude chamada {args.conversa}. As abertas são: {', '.join(nomes) or 'nenhuma'}."
        if len(parecidos) > 1:
            return f"Mais de uma conversa combina com {args.conversa}: {', '.join(parecidos)}. Qual delas?"
        nome = parecidos[0]
        pedido = (
            f"Use a ferramenta SendMessage para enviar exatamente esta mensagem para a sessão local chamada {nome}: "
            f"{json.dumps(args.mensagem, ensure_ascii=False)}. Não faça mais nada. Depois responda só ENVIADO ou o erro."
        )
        resultado = await rodar_claude(executor, pedido, _pasta_neutra(), _FERRAMENTAS_DE_MENSAGEM, modelo, 120, teto_usd)
        if resultado.strip().upper().startswith("ENVIADO"):
            return f"Mandei a mensagem para a conversa {nome}."
        return f"Não consegui entregar a mensagem para a conversa {nome}: {resultado}"

    def confirmar_mensagem(args: ArgsMensagem) -> str:
        return f"Vou mandar para a conversa {args.conversa} do Claude: {args.mensagem}. Confirma?"

    return [
        Ferramenta(
            "abrir_claude_na_tela",
            "Abre o VS Code no projeto e inicia uma conversa NOVA do Claude Code, visível, já com o pedido do usuário. "
            "Use quando o usuário quer ver o Claude trabalhando numa conversa nova.",
            ArgsNaTela, abrir_claude_na_tela, figura=CODIGO,
        ),
        Ferramenta(
            "pedir_ao_claude",
            "Envia um pedido ao Claude, que responde em segundo plano; o resultado é falado quando fica pronto. "
            "Use para perguntas difíceis, programação, análise e leitura de sites.",
            ArgsPedido, pedir_ao_claude, figura=CODIGO,
        ),
        Ferramenta("consultar_agenda", "Lê os compromissos da agenda.", ArgsAgenda, consultar_agenda, figura=CALENDARIO),
        Ferramenta(
            "criar_compromisso", "Cria um compromisso ou lembrete na agenda.", ArgsCompromisso, criar_compromisso,
            risco=Risco.CONFIRMAR, descrever=confirmar_compromisso, figura=CALENDARIO,
        ),
        Ferramenta(
            "mandar_para_conversa_do_claude",
            "Entrega uma mensagem numa conversa do Claude Code que JÁ ESTÁ ABERTA, pelo nome dela. "
            "Use quando o usuário quer falar com uma aba, janela ou sessão do Claude existente. Não abre nada novo.",
            ArgsMensagem, mandar_para_conversa_do_claude,
            risco=Risco.CONFIRMAR, descrever=confirmar_mensagem, figura=MENSAGEM,
        ),
    ]
