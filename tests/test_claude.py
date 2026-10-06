import base64
import json
from datetime import datetime

import pytest

from clarisse.ferramentas.claude import (
    FERRAMENTAS_DE_LEITURA,
    Delegacoes,
    ferramentas_do_claude,
)
from clarisse.ferramentas.processos import Resultado
from clarisse.ferramentas.registro import Risco


class Avisos:
    def __init__(self):
        self.recebidos: list[tuple[str, str]] = []

    async def __call__(self, titulo: str, texto: str):
        self.recebidos.append((titulo, texto))


@pytest.fixture
def avisos():
    return Avisos()


@pytest.fixture
def delegacoes(avisos):
    return Delegacoes(avisos)


@pytest.fixture
def montar(cadastros, executor, delegacoes, tmp_path):
    def _montar():
        lista = ferramentas_do_claude(
            cadastros, executor, delegacoes=delegacoes, pasta_neutra=tmp_path / "neutra",
            modelo="sonnet", timeout=600, teto_usd=1.5, agora=lambda: datetime(2026, 9, 28, 14, 5),
        )
        return {f.nome: f for f in lista}
    return _montar


def _json_do_claude(texto: str) -> Resultado:
    return Resultado(0, json.dumps({"type": "result", "is_error": False, "result": texto}), "")


def _valor_da_opcao(argumentos: list[str], opcao: str) -> str:
    return argumentos[argumentos.index(opcao) + 1]


async def test_abrir_na_tela_abre_vscode_e_terminal_com_o_pedido(montar, cadastros, executor):
    f = montar()["abrir_claude_na_tela"]
    pasta = str(cadastros.projetos["omni-api"])

    await f.executar(f.argumentos(projeto="omni-api", pedido="corrige o teste d'ela; del /q *"))

    (vscode, _), (terminal, _) = executor.iniciados
    assert vscode == ["code", pasta]
    assert terminal[:5] == ["wt.exe", "-w", "new", "-d", pasta]
    comando = base64.b64decode(terminal[-1]).decode("utf-16-le")
    assert comando == "claude 'corrige o teste d''ela; del /q *'"


async def test_pedir_ao_claude_responde_na_hora_e_avisa_quando_termina(montar, delegacoes, cadastros, executor, avisos):
    ferramentas = montar()
    f = ferramentas["pedir_ao_claude"]
    executor.respostas.append(_json_do_claude("O build quebra por falta da variável X."))

    resposta = await f.executar(f.argumentos(pedido="por que o build quebra?", projeto="omni-api"))
    assert "aviso" in resposta.lower()

    await delegacoes.aguardar()

    assert avisos.recebidos == [("omni-api", "O build quebra por falta da variável X.")]
    argumentos, pasta = executor.executados[0]
    assert argumentos[:2] == ["claude", "-p"]
    assert argumentos[2].startswith("por que o build quebra?")
    assert pasta == cadastros.projetos["omni-api"]
    assert _valor_da_opcao(argumentos, "--setting-sources") == "project"
    assert "--no-session-persistence" in argumentos
    assert _valor_da_opcao(argumentos, "--output-format") == "json"
    assert _valor_da_opcao(argumentos, "--allowedTools") == ",".join(FERRAMENTAS_DE_LEITURA)
    assert _valor_da_opcao(argumentos, "--tools") == ",".join(FERRAMENTAS_DE_LEITURA)
    assert _valor_da_opcao(argumentos, "--model") == "sonnet"
    assert _valor_da_opcao(argumentos, "--max-budget-usd") == "1.5"


async def test_pedir_ao_claude_sem_projeto_roda_numa_pasta_neutra(montar, delegacoes, executor, tmp_path):
    ferramentas = montar()
    f = ferramentas["pedir_ao_claude"]
    executor.respostas.append(_json_do_claude("ok"))

    await f.executar(f.argumentos(pedido="o que é uma API?"))
    await delegacoes.aguardar()

    assert executor.executados[0][1] == tmp_path / "neutra"
    assert (tmp_path / "neutra").is_dir()


async def test_pergunta_ao_claude_nao_carrega_nem_espera_os_conectores_da_conta(montar, delegacoes, executor):
    # Esperar conectores que a pergunta não pode usar custava ~6 s antes de o Claude começar (30/09/2026).
    f = montar()["pedir_ao_claude"]
    executor.respostas.append(_json_do_claude("Ottawa."))

    await f.executar(f.argumentos(pedido="qual a capital do Canadá?"))
    await delegacoes.aguardar()

    argumentos, _ = executor.executados[0]
    assert "--strict-mcp-config" in argumentos
    assert json.loads(_valor_da_opcao(argumentos, "--mcp-config")) == {"mcpServers": {}}
    assert "MCP_CONNECTION_NONBLOCKING" not in executor.ambientes[0]


async def test_falha_do_claude_vira_aviso_legivel(montar, delegacoes, executor, avisos):
    f = montar()["pedir_ao_claude"]
    executor.respostas.append(Resultado(1, "", "Error: not logged in"))

    await f.executar(f.argumentos(pedido="x"))
    await delegacoes.aguardar()

    [(_, texto)] = avisos.recebidos
    assert "não conseguiu" in texto.lower()


async def test_claude_que_estoura_o_tempo_vira_aviso(montar, delegacoes, executor, avisos):
    f = montar()["pedir_ao_claude"]
    executor.respostas.append(Resultado(None, "", "", estourou_tempo=True))

    await f.executar(f.argumentos(pedido="x"))
    await delegacoes.aguardar()

    [(_, texto)] = avisos.recebidos
    assert "demorou" in texto.lower()


@pytest.mark.parametrize("ferramenta,args", [
    ("criar_compromisso", {"titulo": "Reunião", "quando": "amanhã às 10h"}),
])
async def test_agenda_espera_os_conectores_antes_de_o_claude_comecar(montar, executor, ferramenta, args):
    # Sem esperar, o Claude às vezes começa antes do Microsoft 365 conectar e responde que não tem calendário.
    f = montar()[ferramenta]
    executor.respostas.append(_json_do_claude("ok"))

    await f.executar(f.argumentos(**args))

    assert executor.ambientes[0].get("MCP_CONNECTION_NONBLOCKING") == "false"


async def test_criar_compromisso_pede_confirmacao_e_so_pode_criar_evento(montar, executor):
    f = montar()["criar_compromisso"]
    args = f.argumentos(titulo="Reunião com João", quando="amanhã às 15h")
    executor.respostas.append(_json_do_claude("Criado."))

    assert f.risco_de(args) is Risco.CONFIRMAR
    assert "Reunião com João" in f.frase_de_confirmacao(args)
    await f.executar(args)
    argumentos, _ = executor.executados[0]
    assert _valor_da_opcao(argumentos, "--allowedTools") == "mcp__claude_ai_Microsoft_365__outlook_create_event"


async def test_compromisso_com_participantes_confirma_os_nomes_e_busca_as_pessoas(montar, executor):
    f = montar()["criar_compromisso"]
    args = f.argumentos(titulo="Alinhamento", quando="amanhã às 15h", participantes=["Bruno Santos", "Kaiki"])
    executor.respostas.append(_json_do_claude("Criado."))

    assert "convidando Bruno Santos e Kaiki" in f.frase_de_confirmacao(args)
    await f.executar(args)
    argumentos, _ = executor.executados[0]
    assert set(_valor_da_opcao(argumentos, "--allowedTools").split(",")) == {
        "mcp__claude_ai_Microsoft_365__outlook_create_event",
        "mcp__claude_ai_Microsoft_365__search_people",
    }
    pedido = argumentos[2]
    assert "Bruno Santos" in pedido and "Kaiki" in pedido
    assert "não crie" in pedido.lower()


def test_no_maximo_dez_participantes(montar):
    with pytest.raises(ValueError):
        montar()["criar_compromisso"].argumentos(titulo="x", quando="amanhã", participantes=[f"p{i}" for i in range(11)])


async def test_tarefa_que_passa_do_teto_de_gasto_vira_aviso(montar, delegacoes, executor, avisos):
    f = montar()["pedir_ao_claude"]
    executor.respostas.append(
        Resultado(1, json.dumps({"type": "result", "subtype": "error_max_budget_usd", "is_error": True}), "")
    )

    await f.executar(f.argumentos(pedido="x"))
    await delegacoes.aguardar()

    [(_, texto)] = avisos.recebidos
    assert "teto de gasto" in texto.lower()


async def test_erro_inesperado_na_tarefa_do_claude_ainda_avisa_o_usuario(avisos):
    delegacoes = Delegacoes(avisos)

    async def quebra():
        raise RuntimeError("falhou no meio")

    delegacoes.iniciar("omni-api", quebra())
    await delegacoes.aguardar()

    [(titulo, texto)] = avisos.recebidos
    assert titulo == "omni-api"
    assert "não conseguiu" in texto.lower()


async def test_criar_compromisso_manda_o_linux_atualizar_a_agenda(cadastros, executor, delegacoes, tmp_path):
    atualizacoes = []

    async def atualizar_agenda():
        atualizacoes.append(1)

    ferramentas = {f.nome: f for f in ferramentas_do_claude(
        cadastros, executor, delegacoes, pasta_neutra=tmp_path, modelo="sonnet", timeout=600, teto_usd=1.0,
        apos_mudar_agenda=atualizar_agenda,
    )}
    executor.respostas.append(_json_do_claude("Criado."))
    f = ferramentas["criar_compromisso"]

    await f.executar(f.argumentos(titulo="Reunião", quando="amanhã às 15h"))

    assert atualizacoes == [1]


@pytest.fixture
def navegador(cadastros, executor, delegacoes, tmp_path):
    config = tmp_path / "mcp-navegador.json"
    ferramentas = ferramentas_do_claude(
        cadastros, executor, delegacoes, pasta_neutra=tmp_path / "neutra", modelo="sonnet", timeout=600,
        teto_usd=1.0, mcp_navegador=config,
    )
    return {f.nome: f for f in ferramentas}["fazer_no_navegador"], config


async def test_navegador_pede_confirmacao_mostrando_o_pedido(navegador):
    f, _ = navegador
    args = f.argumentos(pedido="abre o painel fidc e me diz o total de hoje")

    assert f.risco_de(args) is Risco.CONFIRMAR
    assert "painel fidc" in f.frase_de_confirmacao(args)


async def test_navegador_roda_um_claude_so_com_o_navegador_e_proibido_de_agir(navegador, delegacoes, executor, avisos):
    f, config = navegador
    executor.respostas.append(_json_do_claude("O total de hoje é 10 mil."))

    resposta = await f.executar(f.argumentos(pedido="abre o painel fidc e me diz o total de hoje"))
    await delegacoes.aguardar()

    argumentos, _ = executor.executados[0]
    assert "aviso" in resposta.lower()
    assert _valor_da_opcao(argumentos, "--mcp-config") == str(config)
    assert "--strict-mcp-config" in argumentos
    assert _valor_da_opcao(argumentos, "--allowedTools") == "mcp__playwright"
    assert _valor_da_opcao(argumentos, "--tools") == "ToolSearch"
    assert "painel fidc" in argumentos[2] and "Não envie formulários" in argumentos[2]
    assert avisos.recebidos == [("navegador", "O total de hoje é 10 mil.")]


def test_sem_configuracao_do_navegador_a_ferramenta_nao_existe(montar):
    assert "fazer_no_navegador" not in montar()


async def test_pedido_ao_claude_manda_pesquisar_na_internet_perguntas_sobre_o_mundo(montar, executor, delegacoes):
    f = montar()["pedir_ao_claude"]
    executor.respostas.append(_json_do_claude("A Smart Compass é..."))

    await f.executar(f.argumentos(pedido="O que é a Smart Compass?"))
    await delegacoes.aguardar()

    argumentos, _ = executor.executados[0]
    assert argumentos[2].startswith("O que é a Smart Compass?")
    assert "pesquise na internet" in argumentos[2].lower()


@pytest.fixture
def em_etapas(cadastros, executor, delegacoes, tmp_path):
    config = tmp_path / "mcp-clarisse.json"
    ferramentas = ferramentas_do_claude(
        cadastros, executor, delegacoes, pasta_neutra=tmp_path / "neutra", modelo="sonnet", timeout=600,
        teto_usd=1.0, mcp_clarisse=config,
    )
    return {f.nome: f for f in ferramentas}["fazer_em_etapas"], config


async def test_em_etapas_roda_um_claude_so_com_as_ferramentas_da_clarisse(em_etapas, delegacoes, executor, avisos):
    f, config = em_etapas
    executor.respostas.append(_json_do_claude("Abri o projeto e o arquivo."))
    args = f.argumentos(pedido="abre o projeto omni api e depois o arquivo do boleto")

    resposta = await f.executar(args)
    await delegacoes.aguardar()

    assert f.risco_de(args) is Risco.SEGURO
    assert "aviso" in resposta.lower()
    argumentos, _ = executor.executados[0]
    assert _valor_da_opcao(argumentos, "--mcp-config") == str(config)
    assert "--strict-mcp-config" in argumentos
    assert set(_valor_da_opcao(argumentos, "--allowedTools").split(",")) == {"mcp__clarisse", "WebSearch", "WebFetch"}
    assert set(_valor_da_opcao(argumentos, "--tools").split(",")) == {"WebSearch", "WebFetch", "ToolSearch"}
    assert argumentos[2].startswith("abre o projeto omni api e depois o arquivo do boleto")
    assert "confirmad" in argumentos[2]
    assert avisos.recebidos == [("Claude", "Abri o projeto e o arquivo.")]


def test_sem_o_servidor_da_clarisse_nao_ha_em_etapas(montar):
    assert "fazer_em_etapas" not in montar()
