"""Leitura do Outlook (agenda e e-mail) pelo Microsoft Graph, com o token da conta Microsoft 365 que
já está ligada no GNOME (Configurações → Contas on-line). Nenhum app registrado, nada passa pelo Claude.

O token nunca vai para log nem para o modelo: só para o cabeçalho do pedido ao Graph."""
import json
import re

import httpx

GRAPH = "https://graph.microsoft.com/v1.0"
_GOA = ["gdbus", "call", "--session", "--dest", "org.gnome.OnlineAccounts"]
_CONTA = re.compile(r"'(/org/gnome/OnlineAccounts/Accounts/account_[0-9_]+)'")
_TOKEN = re.compile(r"^\('([^']+)'")
# Horários da agenda já no fuso de Brasília.
FUSO = 'outlook.timezone="E. South America Standard Time"'


class SemContaMicrosoft(RuntimeError):
    pass


class ContaMicrosoft:
    def __init__(self, executor, http: httpx.AsyncClient):
        self._executor = executor
        self._http = http
        self._token: str | None = None
        self._caminho: str | None = None

    async def _conta(self) -> str:
        objetos = await self._executor.executar(
            [*_GOA, "--object-path", "/org/gnome/OnlineAccounts",
             "--method", "org.freedesktop.DBus.ObjectManager.GetManagedObjects"],
            timeout=15,
        )
        achadas = list(_CONTA.finditer(objetos.saida))
        for i, achada in enumerate(achadas):
            fim = achadas[i + 1].start() if i + 1 < len(achadas) else len(objetos.saida)
            if "'ProviderType': <'ms_graph'>" in objetos.saida[achada.end():fim]:
                return achada.group(1)
        raise SemContaMicrosoft("Não achei conta Microsoft nas contas on-line do GNOME.")

    async def _novo_token(self) -> str:
        self._caminho = self._caminho or await self._conta()
        conta = self._caminho
        resposta = await self._executor.executar(
            [*_GOA, "--object-path", conta, "--method", "org.gnome.OnlineAccounts.OAuth2Based.GetAccessToken"],
            timeout=15,
        )
        achado = _TOKEN.match(resposta.saida.strip())
        if not achado:
            raise SemContaMicrosoft("A conta Microsoft do GNOME não devolveu acesso; entre de novo nas contas on-line.")
        return achado.group(1)

    async def _pedir(self, metodo: str, caminho: str, parametros: dict | None = None,
                     corpo: dict | None = None, cabecalhos: dict | None = None) -> dict:
        conteudo = json.dumps(corpo, ensure_ascii=False, separators=(",", ":")).encode() if corpo is not None else None
        extras = {"Content-Type": "application/json"} if conteudo is not None else {}
        for tentativa in range(2):
            if self._token is None or tentativa:
                self._token = await self._novo_token()
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
