import asyncio
import json
from datetime import datetime

import pytest
from pydantic import Field

from clarisse.agente import Agente
from clarisse.auditoria import Auditoria
from clarisse.eventos import Eventos
from clarisse.ferramentas.registro import Argumentos, Ferramenta, Registro, Risco
from clarisse.llm import ChamadaDeFerramenta, ErroDoModelo, RespostaDoModelo


class ModeloFalso:
    """Devolve respostas roteirizadas e guarda o que recebeu."""

    def __init__(self, *roteiro):
        self.roteiro = list(roteiro)
        self.recebidas: list[list[dict]] = []

    async def conversar(self, mensagens, ferramentas):
        self.recebidas.append([dict(m) for m in mensagens])
        passo = self.roteiro.pop(0)
        if isinstance(passo, Exception):
            raise passo
        return passo


def texto(t):
    return RespostaDoModelo(t, [], {"role": "assistant", "content": t})


def chamada(nome, **argumentos):
    return RespostaDoModelo(
        "", [ChamadaDeFerramenta(nome, argumentos)],
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": nome, "arguments": argumentos}}]},
    )


class ArgsGit(Argumentos):
    projeto: str
    operacao: str = Field(pattern="^(status|pull)$")


@pytest.fixture
def executadas():
    return []


@pytest.fixture
def registro(executadas):
    async def git(args):
        executadas.append(("git", args.operacao))
        return f"git {args.operacao}: limpo"

    async def quebra(args):
        raise RuntimeError("disco cheio")

    r = Registro()
    r.registrar(Ferramenta(
        "git", "git", ArgsGit, git,
        risco=lambda a: Risco.CONFIRMAR if a.operacao == "pull" else Risco.SEGURO,
        descrever=lambda a: f"Vou dar pull no {a.projeto}. Confirma?",
    ))
    r.registrar(Ferramenta("quebra", "quebra", Argumentos, quebra))
    return r


@pytest.fixture
def auditoria(tmp_path):
    return Auditoria(tmp_path / "auditoria.jsonl")


@pytest.fixture
def eventos():
    return Eventos()


@pytest.fixture
def novo_agente(registro, eventos, auditoria):
    def _novo(modelo):
        return Agente(
            modelo, registro, eventos, auditoria,
            projetos=["omni-api", "smart-cep"], agora=lambda: datetime(2026, 9, 28, 14, 5), max_rodadas=3,
        )
    return _novo


def _mensagens_de_ferramenta(mensagens):
    return [m["content"] for m in mensagens if m["role"] == "tool"]


async def test_responde_sem_ferramenta_com_data_e_projetos_no_prompt(novo_agente):
    modelo = ModeloFalso(texto("Oi! Tudo bem."))

    resposta = await novo_agente(modelo).responder("oi clarisse")

    assert resposta.texto == "Oi! Tudo bem."
    sistema, usuario = modelo.recebidas[0][0], modelo.recebidas[0][-1]
    assert sistema["role"] == "system"
    assert "28 de setembro de 2026" in sistema["content"]
    assert "omni-api" in sistema["content"]
    assert usuario == {"role": "user", "content": "oi clarisse"}


async def test_ferramenta_segura_executa_e_o_resultado_volta_ao_modelo(novo_agente, executadas):
    modelo = ModeloFalso(chamada("git", projeto="omni-api", operacao="status"), texto("Está limpo."))

    resposta = await novo_agente(modelo).responder("git status no omni")

    assert executadas == [("git", "status")]
    assert _mensagens_de_ferramenta(modelo.recebidas[1]) == ["git status: limpo"]
    assert resposta.texto == "Está limpo."


async def test_ferramenta_de_risco_pergunta_e_so_executa_depois_do_sim(novo_agente, executadas):
    modelo = ModeloFalso(chamada("git", projeto="omni-api", operacao="pull"), texto("Atualizado."))
    agente = novo_agente(modelo)

    pergunta = await agente.responder("atualiza o omni")

    assert pergunta.texto == "Vou dar pull no omni-api. Confirma?"
    assert pergunta.aguardando_confirmacao
    assert executadas == []

    resposta = await agente.responder("sim, pode")

    assert executadas == [("git", "pull")]
    assert resposta.texto == "Atualizado."


async def test_nao_cancela_a_acao_pendente_sem_chamar_o_modelo(novo_agente, executadas):
    modelo = ModeloFalso(chamada("git", projeto="omni-api", operacao="pull"))
    agente = novo_agente(modelo)
    await agente.responder("atualiza o omni")

    resposta = await agente.responder("não")

    assert executadas == []
    assert "cancelei" in resposta.texto.lower()
    assert len(modelo.recebidas) == 1


async def test_outro_pedido_cancela_a_acao_pendente_e_e_atendido(novo_agente, executadas):
    modelo = ModeloFalso(chamada("git", projeto="omni-api", operacao="pull"), texto("São 14h05."))
    agente = novo_agente(modelo)
    await agente.responder("atualiza o omni")

    resposta = await agente.responder("que horas são?")

    assert executadas == []
    assert resposta.texto == "São 14h05."
    assert modelo.recebidas[1][-1] == {"role": "user", "content": "que horas são?"}


async def test_ferramenta_inexistente_volta_como_erro_ao_modelo(novo_agente):
    modelo = ModeloFalso(chamada("formatar_disco"), texto("Não posso fazer isso."))

    resposta = await novo_agente(modelo).responder("formata o disco")

    [erro] = _mensagens_de_ferramenta(modelo.recebidas[1])
    assert "formatar_disco" in erro
    assert resposta.texto == "Não posso fazer isso."


async def test_excecao_da_ferramenta_nao_derruba_o_agente(novo_agente):
    modelo = ModeloFalso(chamada("quebra"), texto("Deu erro: disco cheio."))

    resposta = await novo_agente(modelo).responder("quebra")

    [erro] = _mensagens_de_ferramenta(modelo.recebidas[1])
    assert "disco cheio" in erro
    assert resposta.texto == "Deu erro: disco cheio."


async def test_limite_de_rodadas(novo_agente):
    modelo = ModeloFalso(*[chamada("git", projeto="omni-api", operacao="status")] * 3)

    resposta = await novo_agente(modelo).responder("git status em loop")

    assert len(modelo.recebidas) == 3
    assert "não consegui concluir" in resposta.texto.lower()


async def test_parar_nao_chama_o_modelo_e_descarta_a_pendencia(novo_agente, executadas):
    modelo = ModeloFalso(chamada("git", projeto="omni-api", operacao="pull"), texto("ok"))
    agente = novo_agente(modelo)
    await agente.responder("atualiza o omni")

    resposta = await agente.responder("para, Clarisse")
    depois = await agente.responder("sim")

    assert resposta.parar
    assert executadas == []
    assert depois.texto == "ok"


async def test_modelo_fora_do_ar_vira_resposta_legivel(novo_agente):
    modelo = ModeloFalso(ErroDoModelo("o Ollama não respondeu: ConnectError"))

    resposta = await novo_agente(modelo).responder("oi")

    assert "modelo local" in resposta.texto.lower()


async def test_execucao_fica_na_auditoria(novo_agente, tmp_path):
    modelo = ModeloFalso(chamada("git", projeto="omni-api", operacao="status"), texto("ok"))

    await novo_agente(modelo).responder("git status")

    [linha] = (tmp_path / "auditoria.jsonl").read_text(encoding="utf-8").splitlines()
    registro = json.loads(linha)
    assert registro["ferramenta"] == "git"
    assert registro["situacao"] == "ok"
    assert registro["risco"] == "seguro"


async def test_publica_pensando_e_executando(novo_agente, eventos):
    fila = eventos.assinar()
    modelo = ModeloFalso(chamada("git", projeto="omni-api", operacao="status"), texto("ok"))

    await novo_agente(modelo).responder("git status")

    publicados = []
    while not fila.empty():
        publicados.append(fila.get_nowait())
    estados = [e["estado"] for e in publicados if e["tipo"] == "estado"]
    ferramentas = [(e["ferramenta"], e["situacao"]) for e in publicados if e["tipo"] == "ferramenta"]
    assert estados == ["thinking", "executing", "thinking"]
    assert ferramentas == [("git", "iniciada"), ("git", "concluida")]


async def test_lembra_da_conversa_anterior(novo_agente):
    modelo = ModeloFalso(texto("Oi!"), texto("Você disse oi."))
    agente = novo_agente(modelo)

    await agente.responder("oi")
    await agente.responder("o que eu disse?")

    conversa = [(m["role"], m["content"]) for m in modelo.recebidas[1][1:]]
    assert conversa == [("user", "oi"), ("assistant", "Oi!"), ("user", "o que eu disse?")]


async def test_historico_guarda_as_chamadas_de_ferramenta_para_o_modelo_nao_desaprender(novo_agente):
    modelo = ModeloFalso(chamada("git", projeto="omni-api", operacao="status"), texto("Está limpo."), texto("ok"))
    agente = novo_agente(modelo)

    await agente.responder("git status no omni")
    await agente.responder("e agora?")

    papeis = [m["role"] for m in modelo.recebidas[2][1:]]
    assert papeis == ["user", "assistant", "tool", "assistant", "user"]
    assert modelo.recebidas[2][2]["tool_calls"][0]["function"]["name"] == "git"


async def test_historico_guarda_so_as_ultimas_quatro_conversas(novo_agente):
    modelo = ModeloFalso(*[texto(f"resposta {i}") for i in range(6)])
    agente = novo_agente(modelo)

    for i in range(6):
        await agente.responder(f"fala {i}")

    falas = [m["content"] for m in modelo.recebidas[5] if m["role"] == "user"]
    assert falas == ["fala 1", "fala 2", "fala 3", "fala 4", "fala 5"]


async def test_resultado_longo_de_ferramenta_e_encurtado_no_historico(novo_agente, registro):
    async def longo(args):
        return "x" * 5000

    registro.registrar(Ferramenta("longo", "longo", Argumentos, longo))
    modelo = ModeloFalso(chamada("longo"), texto("ok"), texto("ok"))
    agente = novo_agente(modelo)

    await agente.responder("longo")
    await agente.responder("de novo")

    [resultado] = [m["content"] for m in modelo.recebidas[2] if m["role"] == "tool"]
    assert len(resultado) <= 400


async def test_pergunta_de_confirmacao_fica_no_historico_depois_da_chamada(novo_agente):
    modelo = ModeloFalso(chamada("git", projeto="omni-api", operacao="pull"), texto("ok"))
    agente = novo_agente(modelo)

    await agente.responder("atualiza o omni")
    await agente.responder("não")
    await agente.responder("e agora?")

    papeis = [m["role"] for m in modelo.recebidas[1][1:]]
    assert papeis == ["user", "assistant", "tool", "assistant", "user", "assistant", "user"]
    assert modelo.recebidas[1][2]["tool_calls"][0]["function"]["name"] == "git"
    assert modelo.recebidas[1][4]["content"] == "Vou dar pull no omni-api. Confirma?"


class ArgsPedido(Argumentos):
    pedido: str


@pytest.fixture
def pedidos_ao_claude(registro):
    recebidos = []

    async def pedir(args):
        recebidos.append(args.pedido)
        return "Pedi ao Claude. Aviso quando ele terminar."

    registro.registrar(Ferramenta("pedir_ao_claude", "Claude", ArgsPedido, pedir))
    return recebidos


async def test_anunciar_sem_chamar_ganha_segunda_chance(novo_agente, executadas):
    modelo = ModeloFalso(
        texto("Vou rodar o git status no omni-api."),
        chamada("git", projeto="omni-api", operacao="status"),
        texto("Está limpo."),
    )

    resposta = await novo_agente(modelo).responder("git status no omni")

    assert executadas == [("git", "status")]
    assert resposta.texto == "Está limpo."
    cutucada = modelo.recebidas[1][-1]
    assert cutucada["role"] == "user" and "não chamou" in cutucada["content"]


async def test_a_cutucada_nao_fica_no_historico(novo_agente):
    modelo = ModeloFalso(
        texto("Vou rodar o git status."),
        chamada("git", projeto="omni-api", operacao="status"),
        texto("Está limpo."),
        texto("ok"),
    )
    agente = novo_agente(modelo)

    await agente.responder("git status no omni")
    await agente.responder("e agora?")

    conteudos = [m.get("content") or "" for m in modelo.recebidas[3]]
    assert not any("não chamou" in c for c in conteudos)
    assert not any(c.startswith("Vou rodar") for c in conteudos)


async def test_segunda_chance_so_uma_vez(novo_agente):
    modelo = ModeloFalso(texto("Vou fazer."), texto("Vou fazer mesmo."))

    resposta = await novo_agente(modelo).responder("faz aquilo")

    assert len(modelo.recebidas) == 2
    assert resposta.texto == "Vou fazer mesmo."


async def test_resposta_sem_anuncio_nao_e_cutucada(novo_agente):
    modelo = ModeloFalso(texto("De nada!"))

    await novo_agente(modelo).responder("obrigado")

    assert len(modelo.recebidas) == 1


async def test_pedido_que_cita_o_claude_chega_ao_claude_mesmo_se_o_modelo_nao_chamar(novo_agente, pedidos_ao_claude):
    modelo = ModeloFalso(texto("Vou pedir ao Claude."), texto("Vou pedir ao Claude, pode deixar."))

    resposta = await novo_agente(modelo).responder("manda o Claude explicar REST e GraphQL")

    assert pedidos_ao_claude == ["manda o Claude explicar REST e GraphQL"]
    assert resposta.texto == "Pedi ao Claude. Aviso quando ele terminar."


async def test_pedido_sem_claude_nao_e_desviado_para_o_claude(novo_agente, pedidos_ao_claude):
    modelo = ModeloFalso(texto("Vou ver."), texto("Vou ver mesmo."))

    await novo_agente(modelo).responder("explica REST e GraphQL")

    assert pedidos_ao_claude == []


async def test_garantia_do_claude_nao_duplica_quando_o_modelo_ja_chamou(novo_agente, pedidos_ao_claude):
    modelo = ModeloFalso(
        RespostaDoModelo("", [ChamadaDeFerramenta("pedir_ao_claude", {"pedido": "explicar REST"})],
                         {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "pedir_ao_claude", "arguments": {"pedido": "explicar REST"}}}]}),
        texto("Pronto, pedi ao Claude."),
    )

    await novo_agente(modelo).responder("pede pro Claude explicar REST")

    assert pedidos_ao_claude == ["explicar REST"]


async def test_resposta_vazia_depois_da_ferramenta_fala_o_resultado_dela(novo_agente):
    modelo = ModeloFalso(chamada("git", projeto="omni-api", operacao="status"), texto(""))

    resposta = await novo_agente(modelo).responder("git status no omni")

    assert resposta.texto == "git status: limpo"


async def test_sim_depois_de_outro_pedido_nao_executa_a_acao_antiga(novo_agente, executadas):
    modelo = ModeloFalso(chamada("git", projeto="omni-api", operacao="pull"), texto("São 14h05."), texto("Sim o quê?"))
    agente = novo_agente(modelo)
    await agente.responder("atualiza o omni")
    await agente.responder("que horas são?")

    await agente.responder("sim")

    assert executadas == []


async def test_ferramenta_travada_estoura_o_tempo_e_o_agente_segue(registro, eventos, auditoria):
    async def travada(args):
        await asyncio.sleep(30)

    registro.registrar(Ferramenta("travada", "trava", Argumentos, travada))
    modelo = ModeloFalso(chamada("travada"), texto("Demorou demais."))
    agente = Agente(modelo, registro, eventos, auditoria, projetos=[], timeout_da_ferramenta=0.1)

    resposta = await agente.responder("trava")

    assert resposta.texto == "Demorou demais."
    assert _mensagens_de_ferramenta(modelo.recebidas[1])[0].startswith("Erro ao executar travada")
