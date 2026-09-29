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

    await f.executar(f.argumentos(projeto="omni-api", pedido="corrige o teste; rm -rf ~"))

    assert executor.iniciados == [
        (["code", pasta], None),
        (["ptyxis", "--new-window", "-d", pasta, "--", "claude", "corrige o teste; rm -rf ~"], None),
    ]


async def test_pedir_ao_claude_responde_na_hora_e_avisa_quando_termina(montar, delegacoes, cadastros, executor, avisos):
    ferramentas = montar()
    f = ferramentas["pedir_ao_claude"]
    executor.respostas.append(_json_do_claude("O build quebra por falta da variável X."))

    resposta = await f.executar(f.argumentos(pedido="por que o build quebra?", projeto="omni-api"))
    assert "aviso" in resposta.lower()

    await delegacoes.aguardar()

    assert avisos.recebidos == [("omni-api", "O build quebra por falta da variável X.")]
    argumentos, pasta = executor.executados[0]
    assert argumentos[:3] == ["claude", "-p", "por que o build quebra?"]
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


async def test_consultar_agenda_usa_so_a_leitura_do_calendario_e_a_data_de_hoje(montar, executor):
    f = montar()["consultar_agenda"]
    executor.respostas.append(_json_do_claude("Às 10h, reunião de time."))

    resposta = await f.executar(f.argumentos(periodo="hoje"))

    argumentos, _ = executor.executados[0]
    assert resposta == "Às 10h, reunião de time."
    assert _valor_da_opcao(argumentos, "--allowedTools") == "mcp__claude_ai_Microsoft_365__outlook_calendar_search"
    assert _valor_da_opcao(argumentos, "--tools") == "ToolSearch"
    assert "28 de setembro de 2026" in argumentos[2]


async def test_criar_compromisso_pede_confirmacao_e_so_pode_criar_evento(montar, executor):
    f = montar()["criar_compromisso"]
    args = f.argumentos(titulo="Reunião com João", quando="amanhã às 15h")
    executor.respostas.append(_json_do_claude("Criado."))

    assert f.risco_de(args) is Risco.CONFIRMAR
    assert "Reunião com João" in f.frase_de_confirmacao(args)
    await f.executar(args)
    argumentos, _ = executor.executados[0]
    assert _valor_da_opcao(argumentos, "--allowedTools") == "mcp__claude_ai_Microsoft_365__outlook_create_event"


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
