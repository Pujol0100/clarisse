"""Leitura do Outlook pelo Microsoft Graph com o token do login MSAL."""
import httpx
import pytest

from clarisse.microsoft import ESCOPOS, ContaMicrosoft, LoginMicrosoft, SemContaMicrosoft


class Tokens:
    def __init__(self, *tokens):
        self.tokens = list(tokens)
        self.pedidos: list[bool] = []

    async def __call__(self, forcar_novo: bool) -> str:
        self.pedidos.append(forcar_novo)
        if not self.tokens:
            raise SemContaMicrosoft("Entre na conta Microsoft.")
        return self.tokens.pop(0)


def _conta(tokens, responder):
    return ContaMicrosoft(tokens, httpx.AsyncClient(transport=httpx.MockTransport(responder)))


async def test_usa_o_token_do_login_no_graph():
    pedidos = []

    def responder(pedido):
        pedidos.append(pedido)
        return httpx.Response(200, json={"value": []})

    dados = await _conta(Tokens("token-1"), responder).get("/me/calendarView", {"$top": "5"})

    assert dados == {"value": []}
    assert pedidos[0].headers["Authorization"] == "Bearer token-1"
    assert str(pedidos[0].url).startswith("https://graph.microsoft.com/v1.0/me/calendarView")


async def test_guarda_o_token_entre_pedidos():
    tokens = Tokens("token-1")
    conta = _conta(tokens, lambda p: httpx.Response(200, json={}))

    await conta.get("/me", {})
    await conta.get("/me", {})

    assert tokens.pedidos == [False]


async def test_token_vencido_pede_outro_a_forca_e_repete_uma_vez():
    tokens = Tokens("velho", "novo")
    usados = []

    def responder(pedido):
        usados.append(pedido.headers["Authorization"])
        return httpx.Response(401 if len(usados) == 1 else 200, json={"ok": True})

    dados = await _conta(tokens, responder).get("/me", {})

    assert dados == {"ok": True}
    assert usados == ["Bearer velho", "Bearer novo"]
    assert tokens.pedidos == [False, True]


async def test_sem_login_avisa():
    with pytest.raises(SemContaMicrosoft):
        await _conta(Tokens(), lambda p: httpx.Response(200)).get("/me", {})


async def test_post_manda_o_corpo_com_o_token_e_aceita_resposta_vazia():
    pedidos = []

    def responder(pedido):
        pedidos.append(pedido)
        return httpx.Response(202) if pedido.url.path.endswith("/send") else httpx.Response(201, json={"id": "r1"})

    conta = _conta(Tokens("token-1"), responder)
    criado = await conta.post("/me/messages", {"subject": "Oi"})
    enviado = await conta.post("/me/messages/r1/send", None)

    assert criado == {"id": "r1"} and enviado == {}
    assert pedidos[0].method == "POST" and pedidos[0].headers["Authorization"] == "Bearer token-1"
    assert pedidos[0].read() == b'{"subject":"Oi"}'


class AppFalso:
    """No lugar do msal.PublicClientApplication."""

    def __init__(self, contas=(), silencioso=None, interativo=None):
        self.contas = list(contas)
        self.silencioso = silencioso
        self.interativo = interativo
        self.pedidos_silenciosos: list[dict] = []
        self.pedidos_interativos: list[dict] = []

    def get_accounts(self):
        return self.contas

    def acquire_token_silent(self, scopes, account, force_refresh=False):
        self.pedidos_silenciosos.append({"escopos": scopes, "conta": account, "forcar": force_refresh})
        return self.silencioso

    def acquire_token_interactive(self, scopes, prompt=None):
        self.pedidos_interativos.append({"escopos": scopes, "prompt": prompt})
        return self.interativo


CONTA = {"username": "eu@empresa.com.br"}


async def test_login_guardado_devolve_token_sem_abrir_o_navegador():
    app = AppFalso(contas=[CONTA], silencioso={"access_token": "t-1"})

    token = await LoginMicrosoft(criar_app=lambda: app).token(False)

    assert token == "t-1"
    assert app.pedidos_silenciosos == [{"escopos": ESCOPOS, "conta": CONTA, "forcar": False}]
    assert app.pedidos_interativos == []


async def test_forcar_novo_chega_ao_msal():
    app = AppFalso(contas=[CONTA], silencioso={"access_token": "t-2"})

    await LoginMicrosoft(criar_app=lambda: app).token(True)

    assert app.pedidos_silenciosos[0]["forcar"] is True


async def test_sem_conta_guardada_manda_rodar_o_script_de_entrar():
    login = LoginMicrosoft(criar_app=lambda: AppFalso())

    with pytest.raises(SemContaMicrosoft, match="entrar-microsoft"):
        await login.token(False)


async def test_login_vencido_sem_renovacao_manda_entrar_de_novo():
    app = AppFalso(contas=[CONTA], silencioso={"error": "invalid_grant"})

    with pytest.raises(SemContaMicrosoft, match="entrar-microsoft"):
        await LoginMicrosoft(criar_app=lambda: app).token(False)


def test_entrar_abre_a_escolha_de_conta_e_diz_quem_entrou():
    app = AppFalso(interativo={"access_token": "t", "id_token_claims": {"preferred_username": "eu@empresa.com.br"}})

    quem = LoginMicrosoft(criar_app=lambda: app).entrar()

    assert quem == "eu@empresa.com.br"
    assert app.pedidos_interativos == [{"escopos": ESCOPOS, "prompt": "select_account"}]


def test_entrada_recusada_diz_o_motivo():
    app = AppFalso(interativo={"error": "access_denied", "error_description": "AADSTS65001: falta consentimento"})

    with pytest.raises(SemContaMicrosoft, match="AADSTS65001"):
        LoginMicrosoft(criar_app=lambda: app).entrar()
