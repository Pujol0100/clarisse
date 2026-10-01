"""Situação de um sistema nos painéis do Dokploy, só leitura."""
import httpx

from clarisse.ferramentas.dokploy import ferramentas_do_dokploy

PAINEIS = [("https://infra.omni.exemplo", "chave-omni"), ("https://infra.anchor.exemplo", "chave-anchor")]
PROJETOS = {
    "infra.omni.exemplo": [{"name": "Plataforma", "environments": [{"applications": [
        {"applicationId": "a1", "name": "omni-app", "applicationStatus": "done"},
        {"applicationId": "a2", "name": "staging_omni-app", "applicationStatus": "error"},
    ]}]}],
    "infra.anchor.exemplo": [{"name": "Anchor", "environments": [{"applications": [
        {"applicationId": "b1", "name": "smart-anchor", "applicationStatus": "idle"},
    ]}]}],
}
DEPLOYS = {
    "a1": [{"status": "done", "createdAt": "2026-09-30T18:04:43.092Z", "title": "Merge pull request #432"},
           {"status": "error", "createdAt": "2026-09-29T10:00:00.000Z", "title": "antigo"}],
    "a2": [{"status": "error", "createdAt": "2026-10-01T12:30:00.000Z", "title": "Merge pull request #440"}],
    "b1": [],
}


def _ferramenta(pedidos=None, paineis=PAINEIS):
    def responder(pedido):
        if pedidos is not None:
            pedidos.append(pedido)
        if pedido.url.path == "/api/project.all":
            return httpx.Response(200, json=PROJETOS[pedido.url.host])
        return httpx.Response(200, json=DEPLOYS[pedido.url.params["applicationId"]])

    [f] = ferramentas_do_dokploy(httpx.AsyncClient(transport=httpx.MockTransport(responder)), lambda: paineis)
    return f


async def test_sistema_no_ar_com_o_ultimo_deploy_no_horario_de_brasilia():
    pedidos = []
    f = _ferramenta(pedidos)

    resposta = await f.executar(f.argumentos(sistema="omni app"))

    assert resposta.texto == "omni-app está no ar. Último deploy em 30/09 às 15:04, concluído: Merge pull request #432."
    assert resposta.cartao == {
        "tipo": "lista", "titulo": "Servidores", "canto": "omni-app",
        "itens": [["situação", "no ar"], ["último deploy", "30/09 15:04 · concluído"], ["painel", "infra.omni.exemplo"]],
    }
    assert all(p.headers["x-api-key"] in {"chave-omni", "chave-anchor"} for p in pedidos)
    assert all(p.method == "GET" for p in pedidos)


async def test_procura_em_todos_os_paineis_e_aceita_parte_do_nome():
    f = _ferramenta()

    resposta = await f.executar(f.argumentos(sistema="anchor"))

    assert resposta.texto == "smart-anchor está parado. Nenhum deploy registrado."


async def test_deploy_com_erro_aparece():
    f = _ferramenta()

    resposta = await f.executar(f.argumentos(sistema="staging_omni-app"))

    assert resposta.texto.startswith("staging_omni-app está com erro. Último deploy em 01/10 às 09:30, com erro")


async def test_nome_que_casa_com_varios_pergunta_qual():
    f = _ferramenta()

    resposta = await f.executar(f.argumentos(sistema="omni"))

    assert resposta == "Achei mais de um sistema com esse nome: omni-app, staging_omni-app. Qual deles?"


async def test_sistema_que_nao_existe():
    resposta = await _ferramenta().executar(_ferramenta().argumentos(sistema="financeiro"))

    assert resposta == "Não achei o sistema financeiro no Dokploy."


async def test_sem_painel_configurado():
    f = _ferramenta(paineis=[])

    assert await f.executar(f.argumentos(sistema="omni-app")) == "Não tenho acesso a nenhum painel do Dokploy."
