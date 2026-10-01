"""Leitura do Outlook pelo Microsoft Graph com o token da conta Microsoft do GNOME."""
import httpx
import pytest

from clarisse.ferramentas.processos import Resultado
from clarisse.microsoft import ContaMicrosoft, SemContaMicrosoft

CONTAS = (
    "({objectpath '/org/gnome/OnlineAccounts/Manager': {'org.gnome.OnlineAccounts.Manager': {}}, "
    "'/org/gnome/OnlineAccounts/Accounts/account_1_0': {'org.gnome.OnlineAccounts.Account': "
    "{'ProviderType': <'google'>, 'Identity': <'x@gmail.com'>}}, "
    "'/org/gnome/OnlineAccounts/Accounts/account_2_0': {'org.gnome.OnlineAccounts.Account': "
    "{'ProviderType': <'ms_graph'>, 'Identity': <'x@empresa.com'>}}},)"
)


def _conta(executor, responder):
    return ContaMicrosoft(executor, httpx.AsyncClient(transport=httpx.MockTransport(responder)))


async def test_pede_o_token_a_conta_microsoft_do_gnome_e_usa_no_graph(executor):
    executor.respostas += [Resultado(0, CONTAS, ""), Resultado(0, "('token-1', 3599)", "")]
    pedidos = []

    def responder(pedido):
        pedidos.append(pedido)
        return httpx.Response(200, json={"value": []})

    dados = await _conta(executor, responder).get("/me/calendarView", {"$top": "5"})

    assert dados == {"value": []}
    pedir_token = executor.executados[1][0]
    assert "/org/gnome/OnlineAccounts/Accounts/account_2_0" in pedir_token
    assert pedir_token[-1] == "org.gnome.OnlineAccounts.OAuth2Based.GetAccessToken"
    assert pedidos[0].headers["Authorization"] == "Bearer token-1"
    assert str(pedidos[0].url).startswith("https://graph.microsoft.com/v1.0/me/calendarView")


async def test_guarda_o_token_entre_pedidos(executor):
    executor.respostas += [Resultado(0, CONTAS, ""), Resultado(0, "('token-1', 3599)", "")]
    conta = _conta(executor, lambda p: httpx.Response(200, json={}))

    await conta.get("/me", {})
    await conta.get("/me", {})

    assert len(executor.executados) == 2


async def test_token_vencido_pede_outro_e_repete_uma_vez(executor):
    executor.respostas += [
        Resultado(0, CONTAS, ""), Resultado(0, "('velho', 3599)", ""), Resultado(0, "('novo', 3599)", ""),
    ]
    usados = []

    def responder(pedido):
        usados.append(pedido.headers["Authorization"])
        return httpx.Response(401 if len(usados) == 1 else 200, json={"ok": True})

    dados = await _conta(executor, responder).get("/me", {})

    assert dados == {"ok": True}
    assert usados == ["Bearer velho", "Bearer novo"]


async def test_sem_conta_microsoft_no_gnome_avisa(executor):
    executor.respostas.append(Resultado(0, "({objectpath '/org/gnome/OnlineAccounts/Manager': {}},)", ""))

    with pytest.raises(SemContaMicrosoft):
        await _conta(executor, lambda p: httpx.Response(200)).get("/me", {})
