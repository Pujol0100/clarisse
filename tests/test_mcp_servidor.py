import httpx

from clarisse.mcp_servidor import chamar, listar


def _clarisse(pedidos, falhar=False):
    def responder(pedido):
        if falhar:
            raise httpx.ConnectError("desligada")
        pedidos.append((pedido.method, pedido.url.path, pedido.headers.get("x-clarisse-chave"), pedido.content))
        if pedido.url.path == "/api/ferramentas":
            return httpx.Response(200, json={"ferramentas": [
                {"nome": "abrir", "descricao": "Abre algo.", "parametros": {"type": "object", "properties": {"nome": {"type": "string"}}}},
            ]})
        return httpx.Response(200, json={"resultado": "Abri o kanban no navegador."})
    return httpx.AsyncClient(
        base_url="http://127.0.0.1:8765", headers={"X-Clarisse-Chave": "segredo"},
        transport=httpx.MockTransport(responder),
    )


async def test_lista_as_ferramentas_da_clarisse():
    pedidos = []

    [ferramenta] = await listar(_clarisse(pedidos))

    assert ferramenta.name == "abrir"
    assert ferramenta.description == "Abre algo."
    assert ferramenta.input_schema["properties"]["nome"]["type"] == "string"
    assert pedidos[0][2] == "segredo"


async def test_repassa_a_chamada_e_devolve_o_texto():
    pedidos = []

    resultado = await chamar(_clarisse(pedidos), "abrir", {"nome": "kanban"})

    assert resultado.content[0].text == "Abri o kanban no navegador."
    assert not resultado.is_error
    assert pedidos[0][:2] == ("POST", "/api/ferramenta")
    assert b'"nome":"kanban"' in pedidos[0][3].replace(b" ", b"")


async def test_clarisse_desligada_vira_erro_explicado():
    resultado = await chamar(_clarisse([], falhar=True), "abrir", {"nome": "kanban"})

    assert resultado.is_error
    assert "clarisse" in resultado.content[0].text.lower()
