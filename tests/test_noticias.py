import httpx
import pytest

from clarisse.ferramentas.noticias import FEEDS, ferramentas_de_noticias


def _rss(*titulos: str) -> str:
    itens = "".join(f"<item><title>{t}</title><link>https://g1.globo.com/x</link></item>" for t in titulos)
    return f"<?xml version='1.0' encoding='UTF-8'?><rss version='2.0'><channel><title>g1</title>{itens}</channel></rss>"


def _montar(responder):
    cliente = httpx.AsyncClient(transport=httpx.MockTransport(responder))
    [f] = ferramentas_de_noticias(cliente)
    return f


async def test_devolve_as_cinco_primeiras_manchetes_do_feed_geral():
    pedidos = []

    def responder(pedido):
        pedidos.append(str(pedido.url))
        return httpx.Response(200, text=_rss(*[f"Manchete {i}" for i in range(1, 9)]))

    f = _montar(responder)
    resposta = await f.executar(f.argumentos())

    assert pedidos == [FEEDS["geral"]]
    assert "Manchete 1" in resposta and "Manchete 5" in resposta
    assert "Manchete 6" not in resposta


async def test_tema_escolhe_o_feed_sem_acento_e_caixa():
    pedidos = []

    def responder(pedido):
        pedidos.append(str(pedido.url))
        return httpx.Response(200, text=_rss("Dólar cai"))

    f = _montar(responder)
    await f.executar(f.argumentos(tema="Política"))

    assert pedidos == [FEEDS["politica"]]


async def test_tema_desconhecido_cai_no_geral():
    pedidos = []

    def responder(pedido):
        pedidos.append(str(pedido.url))
        return httpx.Response(200, text=_rss("x"))

    f = _montar(responder)
    await f.executar(f.argumentos(tema="culinária"))

    assert pedidos == [FEEDS["geral"]]


@pytest.mark.parametrize("resposta_http", [httpx.Response(503), httpx.Response(200, text="<html>não é rss")])
async def test_falha_do_feed_vira_mensagem(resposta_http):
    f = _montar(lambda p: resposta_http)

    resposta = await f.executar(f.argumentos())

    assert "não consegui" in resposta.lower()


async def test_falha_de_rede_vira_mensagem():
    def responder(pedido):
        raise httpx.ConnectError("sem rede")

    f = _montar(responder)
    resposta = await f.executar(f.argumentos())

    assert "não consegui" in resposta.lower()
