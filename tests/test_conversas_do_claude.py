import json
from datetime import datetime

import pytest

from clarisse.ferramentas.claude import Delegacoes, ferramentas_do_claude
from clarisse.ferramentas.processos import Resultado
from clarisse.ferramentas.registro import Risco

SESSOES = [
    {"pid": 1, "kind": "interactive", "sessionId": "a", "name": "programassmart-6a", "status": "busy"},
    {"pid": 5, "kind": "interactive", "sessionId": "e", "name": "programassmart-76", "status": "idle"},
    {"pid": 2, "kind": "interactive", "sessionId": "b", "name": "Omni", "status": "idle"},
    {"pid": 3, "kind": "interactive", "sessionId": "c", "name": "omni-app-revisao", "status": "idle"},
    {"pid": 4, "kind": "interactive", "sessionId": "d", "name": "Clarisse", "status": "busy"},
]


async def _nada(*args):
    pass


@pytest.fixture
def mandar(cadastros, executor, tmp_path):
    ferramentas = ferramentas_do_claude(
        cadastros, executor, Delegacoes(_nada), pasta_neutra=tmp_path, modelo="sonnet", timeout=600,
        teto_usd=1.0, agora=lambda: datetime(2026, 9, 29, 10, 30),
    )
    return {f.nome: f for f in ferramentas}["mandar_para_conversa_do_claude"]


def _lista():
    return Resultado(0, json.dumps(SESSOES), "")


def _entregue():
    return Resultado(0, json.dumps({"type": "result", "is_error": False, "result": "ENVIADO"}), "")


def _valor(argumentos, opcao):
    return argumentos[argumentos.index(opcao) + 1]


async def test_entrega_a_mensagem_na_conversa_pelo_nome_sem_diferenciar_caixa(mandar, executor):
    executor.respostas += [_lista(), _entregue()]

    resposta = await mandar.executar(mandar.argumentos(conversa="clarisse", mensagem="O tempo já está funcionando, obrigado"))

    listar, enviar = [argumentos for argumentos, _ in executor.executados]
    assert listar == ["claude", "agents", "--json"]
    assert enviar[:2] == ["claude", "-p"]
    assert "Clarisse" in enviar[2] and "O tempo já está funcionando, obrigado" in enviar[2]
    assert _valor(enviar, "--allowedTools") == "SendMessage,ListAgents"
    assert _valor(enviar, "--tools") == "SendMessage,ListAgents"
    assert "Clarisse" in resposta


async def test_nome_exato_ganha_do_parcial(mandar, executor):
    executor.respostas += [_lista(), _entregue()]

    await mandar.executar(mandar.argumentos(conversa="omni", mensagem="oi"))

    assert "sessão local chamada Omni:" in executor.executados[1][0][2]


async def test_nome_parcial_unico_serve(mandar, executor):
    executor.respostas += [_lista(), _entregue()]

    await mandar.executar(mandar.argumentos(conversa="revisao", mensagem="oi"))

    assert "omni-app-revisao" in executor.executados[1][0][2]


async def test_conversa_inexistente_nao_envia_e_lista_as_abertas(mandar, executor):
    executor.respostas += [_lista()]

    resposta = await mandar.executar(mandar.argumentos(conversa="sienge", mensagem="oi"))

    assert len(executor.executados) == 1
    assert "Omni" in resposta and "Clarisse" in resposta


async def test_nome_ambiguo_nao_envia_e_pergunta(mandar, executor):
    executor.respostas += [_lista()]

    resposta = await mandar.executar(mandar.argumentos(conversa="programassmart", mensagem="oi"))

    assert len(executor.executados) == 1
    assert "programassmart-6a" in resposta


async def test_pede_confirmacao_mostrando_a_conversa_e_a_mensagem(mandar):
    args = mandar.argumentos(conversa="clarisse", mensagem="O tempo já está funcionando")

    assert mandar.risco_de(args) is Risco.CONFIRMAR
    frase = mandar.frase_de_confirmacao(args)
    assert "clarisse" in frase and "O tempo já está funcionando" in frase


async def test_falha_na_entrega_vira_mensagem(mandar, executor):
    executor.respostas += [_lista(), Resultado(0, json.dumps({"is_error": True, "result": None}), "")]

    resposta = await mandar.executar(mandar.argumentos(conversa="omni", mensagem="oi"))

    assert "não consegui" in resposta.lower() or "não conseguiu" in resposta.lower()


async def test_falha_ao_listar_vira_mensagem(mandar, executor):
    executor.respostas += [Resultado(1, "", "erro")]

    resposta = await mandar.executar(mandar.argumentos(conversa="omni", mensagem="oi"))

    assert "não consegui" in resposta.lower()
