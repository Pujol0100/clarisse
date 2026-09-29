import json

import httpx
import pytest

from clarisse.llm import ClienteOllama, ErroDoModelo


def _cliente(responder):
    http = httpx.AsyncClient(transport=httpx.MockTransport(responder), base_url="http://ollama")
    return ClienteOllama(http, modelo="gemma4:e4b-it-qat")


async def test_envia_modelo_mensagens_ferramentas_e_desliga_o_raciocinio():
    enviados = []

    def responder(pedido):
        enviados.append((pedido.url.path, json.loads(pedido.content)))
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "Oi!"}})

    ferramentas = [{"type": "function", "function": {"name": "x"}}]
    await _cliente(responder).conversar([{"role": "user", "content": "oi"}], ferramentas)

    [(caminho, corpo)] = enviados
    assert caminho == "/api/chat"
    assert corpo["model"] == "gemma4:e4b-it-qat"
    assert corpo["messages"] == [{"role": "user", "content": "oi"}]
    assert corpo["tools"] == ferramentas
    assert corpo["think"] is False
    assert corpo["stream"] is False


async def test_devolve_texto_sem_chamadas():
    cliente = _cliente(lambda p: httpx.Response(200, json={"message": {"role": "assistant", "content": " Tudo bem. "}}))

    resposta = await cliente.conversar([], [])

    assert resposta.texto == "Tudo bem."
    assert resposta.chamadas == []


async def test_devolve_chamadas_de_ferramenta_e_a_mensagem_original():
    mensagem = {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"function": {"name": "git", "arguments": {"projeto": "omni-api", "operacao": "status"}}}],
    }
    cliente = _cliente(lambda p: httpx.Response(200, json={"message": mensagem}))

    resposta = await cliente.conversar([], [])

    [chamada] = resposta.chamadas
    assert chamada.nome == "git"
    assert chamada.argumentos == {"projeto": "omni-api", "operacao": "status"}
    assert resposta.mensagem == mensagem


async def test_erro_http_vira_erro_do_modelo_com_o_motivo():
    cliente = _cliente(lambda p: httpx.Response(404, json={"error": "model 'x' not found"}))

    with pytest.raises(ErroDoModelo, match="not found"):
        await cliente.conversar([], [])


async def test_ollama_fora_do_ar_vira_erro_do_modelo():
    def responder(pedido):
        raise httpx.ConnectError("recusado")

    with pytest.raises(ErroDoModelo, match="Ollama"):
        await _cliente(responder).conversar([], [])


async def test_limita_o_tamanho_da_resposta():
    enviados = []

    def responder(pedido):
        enviados.append(json.loads(pedido.content))
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "ok"}})

    await _cliente(responder).conversar([], [])

    assert 0 < enviados[0]["options"]["num_predict"] <= 500
