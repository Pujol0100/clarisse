"""Leitura do Outlook (agenda e e-mail) pelo Microsoft Graph, com login próprio pelo MSAL.

O login usa o aplicativo público do Microsoft Graph PowerShell (escolha do usuário em 05/10/2026):
nada é registrado no Entra, e o administrador do Microsoft 365 pode bloquear esse aplicativo.
O navegador só abre pelo scripts\\entrar-microsoft.ps1; durante uma pergunta o token vem em silêncio
do cache, que o Windows criptografa para o usuário.

O token nunca vai para log nem para o modelo: só para o cabeçalho do pedido ao Graph.
Para entrar: python -m clarisse.microsoft entrar"""
import asyncio
import json
import sys
from collections.abc import Awaitable, Callable

import httpx

from clarisse.config import PASTA_LOCAL

GRAPH = "https://graph.microsoft.com/v1.0"
GRAPH_POWERSHELL = "14d82eec-204b-4c2f-b7e8-296a70dab67e"
AUTORIDADE = "https://login.microsoftonline.com/organizations"
# Só o que ferramentas/outlook.py usa: agenda, caixa de entrada, rascunho, envio e busca de pessoas.
ESCOPOS = ["User.Read", "Calendars.Read", "Mail.ReadWrite", "Mail.Send", "People.Read"]
_ENTRE = "Entre na conta Microsoft: rode o scripts\\entrar-microsoft.ps1."
# Horários da agenda já no fuso de Brasília.
FUSO = 'outlook.timezone="E. South America Standard Time"'


class SemContaMicrosoft(RuntimeError):
    pass


def _app_do_msal():
    import msal
    from msal_extensions import FilePersistenceWithDataProtection, PersistedTokenCache

    PASTA_LOCAL.mkdir(parents=True, exist_ok=True)
    cache = PersistedTokenCache(FilePersistenceWithDataProtection(str(PASTA_LOCAL / "conta-microsoft.bin")))
    return msal.PublicClientApplication(GRAPH_POWERSHELL, authority=AUTORIDADE, token_cache=cache)


class LoginMicrosoft:
    def __init__(self, criar_app: Callable[[], object] = _app_do_msal):
        self._criar_app = criar_app
        self._app = None

    def _aplicativo(self):
        if self._app is None:
            self._app = self._criar_app()
        return self._app

    def _silencioso(self, forcar_novo: bool) -> str:
        app = self._aplicativo()
        contas = app.get_accounts()
        if not contas:
            raise SemContaMicrosoft(_ENTRE)
        resultado = app.acquire_token_silent(ESCOPOS, account=contas[0], force_refresh=forcar_novo)
        if not resultado or "access_token" not in resultado:
            raise SemContaMicrosoft(_ENTRE)
        return resultado["access_token"]

    async def token(self, forcar_novo: bool) -> str:
        return await asyncio.to_thread(self._silencioso, forcar_novo)

    def entrar(self) -> str:
        """Abre o navegador para escolher a conta; devolve o e-mail de quem entrou."""
        resultado = self._aplicativo().acquire_token_interactive(ESCOPOS, prompt="select_account")
        if "access_token" not in resultado:
            motivo = resultado.get("error_description") or resultado.get("error")
            raise SemContaMicrosoft(f"A Microsoft recusou a entrada: {motivo}")
        return resultado["id_token_claims"]["preferred_username"]


class ContaMicrosoft:
    def __init__(self, pedir_token: Callable[[bool], Awaitable[str]], http: httpx.AsyncClient):
        self._pedir_token = pedir_token
        self._http = http
        self._token: str | None = None

    async def _pedir(self, metodo: str, caminho: str, parametros: dict | None = None,
                     corpo: dict | None = None, cabecalhos: dict | None = None) -> dict:
        conteudo = json.dumps(corpo, ensure_ascii=False, separators=(",", ":")).encode() if corpo is not None else None
        extras = {"Content-Type": "application/json"} if conteudo is not None else {}
        for tentativa in range(2):
            if self._token is None or tentativa:
                self._token = await self._pedir_token(tentativa > 0)
            resposta = await self._http.request(
                metodo, f"{GRAPH}{caminho}", params=parametros, content=conteudo, timeout=15,
                headers={"Authorization": f"Bearer {self._token}", **extras, **(cabecalhos or {})},
            )
            if resposta.status_code != 401:
                break
        resposta.raise_for_status()
        return resposta.json() if resposta.content else {}

    async def get(self, caminho: str, parametros: dict, cabecalhos: dict | None = None) -> dict:
        return await self._pedir("GET", caminho, parametros, cabecalhos=cabecalhos)

    async def post(self, caminho: str, corpo: dict | None) -> dict:
        """Escrita: só criar rascunho e enviar o rascunho que o usuário confirmou."""
        return await self._pedir("POST", caminho, corpo=corpo)


if __name__ == "__main__" and sys.argv[1:] == ["entrar"]:
    print(f"Entrou como {LoginMicrosoft().entrar()}. A Clarisse já pode ler a agenda e os e-mails.")
