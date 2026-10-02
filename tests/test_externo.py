"""Ferramentas pedidas pelo Claude (pelo servidor MCP da Clarisse), com confirmação pela voz."""
import asyncio
from datetime import datetime

import pytest
from pydantic import Field

from clarisse.agente import Agente
from clarisse.auditoria import Auditoria
from clarisse.confirmacoes import Confirmacoes
from clarisse.eventos import Eventos
from clarisse.ferramentas.registro import Argumentos, Ferramenta, Registro, Risco
from clarisse.figuras import CALENDARIO


class ArgsTexto(Argumentos):
    texto: str = Field(max_length=100)


class Anuncios:
    def __init__(self):
        self.falados = []

    async def __call__(self, frase):
        self.falados.append(frase)


@pytest.fixture
def executadas():
    return []


@pytest.fixture
def anuncios():
    return Anuncios()


@pytest.fixture
def confirmacoes(anuncios):
    return Confirmacoes(anuncios, limite=0.5)


@pytest.fixture
def eventos():
    return Eventos()


@pytest.fixture
def agente(executadas, confirmacoes, eventos, tmp_path):
    async def agenda(args):
        executadas.append(("agenda", args.texto))
        return "Amanhã: reunião às 10h."

    async def colar(args):
        executadas.append(("colar", args.texto))
        return f"Colei {args.texto}."

    r = Registro()
    r.registrar(Ferramenta("agenda", "lê a agenda", ArgsTexto, agenda, figura=CALENDARIO))
    r.registrar(Ferramenta(
        "colar", "cola texto", ArgsTexto, colar,
        risco=Risco.CONFIRMAR, descrever=lambda a: f"Vou colar {a.texto}. Confirma?",
    ))

    class ModeloQueNaoDeveSerUsado:
        async def conversar(self, mensagens, ferramentas):
            raise AssertionError("a resposta da confirmação não passa pelo modelo")

    return Agente(
        ModeloQueNaoDeveSerUsado(), r, eventos, Auditoria(tmp_path / "a.jsonl"), projetos=[],
        agora=lambda: datetime(2026, 9, 30, 10, 0), confirmacoes=confirmacoes,
    )


async def test_ferramenta_segura_roda_e_mostra_a_figura(agente, executadas, eventos):
    fila = eventos.assinar()

    resultado = await agente.executar_externo("agenda", {"texto": "amanhã"})

    assert resultado == "Amanhã: reunião às 10h."
    assert executadas == [("agenda", "amanhã")]
    publicados = [fila.get_nowait() for _ in range(fila.qsize())]
    assert {"tipo": "figura", "figura": CALENDARIO} in [{k: e[k] for k in ("tipo", "figura")} for e in publicados if e["tipo"] == "figura"]


async def test_ferramenta_arriscada_pergunta_pela_voz_e_roda_com_sim(agente, executadas, anuncios):
    pedido = asyncio.create_task(agente.executar_externo("colar", {"texto": "oi"}))
    await asyncio.sleep(0.05)

    assert anuncios.falados == ["O Claude quer: Vou colar oi. Confirma?"]
    assert executadas == []
    resposta = await agente.responder("sim")

    assert await pedido == "Colei oi."
    assert executadas == [("colar", "oi")]
    assert resposta.texto


@pytest.mark.parametrize("fala", ["não", "deixa pra lá"])
async def test_qualquer_resposta_que_nao_seja_sim_cancela(agente, executadas, fala):
    pedido = asyncio.create_task(agente.executar_externo("colar", {"texto": "oi"}))
    await asyncio.sleep(0.05)

    await agente.responder(fala)

    assert "não confirmou" in (await pedido).lower()
    assert executadas == []


async def test_sem_resposta_no_prazo_cancela(agente, executadas):
    resultado = await agente.executar_externo("colar", {"texto": "oi"})

    assert "não confirmou" in resultado.lower()
    assert executadas == []


async def test_parar_cancela_a_confirmacao_do_claude_na_hora(agente, executadas, confirmacoes):
    confirmacoes._limite = 30
    pedido = asyncio.create_task(agente.executar_externo("colar", {"texto": "oi"}))
    await asyncio.sleep(0.05)

    resposta = await agente.responder("para")

    assert resposta.parar
    assert "não confirmou" in (await asyncio.wait_for(pedido, 1)).lower()
    assert executadas == []


async def test_ferramenta_que_nao_existe_e_recusada(agente, executadas):
    resultado = await agente.executar_externo("apagar_tudo", {})

    assert "recus" in resultado.lower()
    assert executadas == []


async def test_argumento_invalido_e_recusado(agente, executadas):
    resultado = await agente.executar_externo("agenda", {"texto": "x", "extra": "invasão"})

    assert "recus" in resultado.lower()
    assert executadas == []


def test_lista_para_o_claude_deixa_de_fora_as_ferramentas_que_chamam_outro_claude(agente):
    from clarisse.externas import FerramentasExternas

    externas = FerramentasExternas(agente._registro, agente, fora={"colar"})

    [unica] = externas.esquemas()
    assert unica["nome"] == "agenda"
    assert unica["descricao"] == "lê a agenda"
    assert unica["parametros"]["properties"]["texto"]["type"] == "string"


async def test_ferramenta_de_fora_e_recusada_mesmo_se_pedida(agente, executadas):
    from clarisse.externas import FerramentasExternas

    externas = FerramentasExternas(agente._registro, agente, fora={"agenda"})

    resultado = await externas.executar("agenda", {"texto": "x"})

    assert "recus" in resultado.lower()
    assert executadas == []


async def test_ferramenta_marcada_pede_confirmacao_quando_quem_pede_e_o_claude(agente, executadas, anuncios):
    from clarisse.externas import FerramentasExternas

    externas = FerramentasExternas(agente._registro, agente, fora=set(), sempre_confirmar={"agenda"})
    pedido = asyncio.create_task(externas.executar("agenda", {"texto": "amanhã"}))
    await asyncio.sleep(0.05)

    assert anuncios.falados and anuncios.falados[0].startswith("O Claude quer:")
    assert executadas == []
    await agente.responder("sim")
    assert await pedido == "Amanhã: reunião às 10h."
