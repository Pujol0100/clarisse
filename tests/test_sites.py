import json

import httpx
import pytest

from clarisse.sites import achar_sites, atualizar_sites_do_dokploy, carregar_sites, servidores_do_dokploy


def _gravar(caminho, dados):
    caminho.write_text(json.dumps(dados, ensure_ascii=False))


def test_apelidos_manuais_valem_e_o_dokploy_so_acrescenta_o_que_falta(tmp_path):
    _gravar(tmp_path / "sites.json", {"omni": {"endereco": "https://omni.exemplo.com/", "apelidos": ["o omni"]}})
    _gravar(tmp_path / "sites-dokploy.json", {
        "https://painel-a": {"omni-app": "https://omni.exemplo.com"},
        "https://painel-b": {"Relatório Novo": "https://novo.exemplo.com/"},
    })

    sites = carregar_sites(tmp_path)

    assert {s.nome: s.endereco for s in sites} == {
        "omni": "https://omni.exemplo.com/",
        "Relatório Novo": "https://novo.exemplo.com/",
    }


def test_sem_arquivos_nao_ha_sites(tmp_path):
    assert carregar_sites(tmp_path) == []


def test_acha_pelo_nome_ou_apelido_sem_acento_e_prefere_o_exato(tmp_path):
    _gravar(tmp_path / "sites.json", {
        "omni": {"endereco": "https://omni/", "apelidos": []},
        "omni staging": {"endereco": "https://staging/", "apelidos": []},
        "inadimplência": {"endereco": "https://inad/", "apelidos": ["painel de inadimplência"]},
    })
    sites = carregar_sites(tmp_path)

    assert [s.nome for s in achar_sites("Omni", sites)] == ["omni"]
    assert [s.nome for s in achar_sites("painel de inadimplencia", sites)] == ["inadimplência"]
    assert [s.nome for s in achar_sites("staging", sites)] == ["omni staging"]
    assert achar_sites("spotify", sites) == []


def test_le_as_chaves_do_dokploy_da_configuracao_do_claude(tmp_path):
    _gravar(tmp_path / ".claude.json", {"mcpServers": {
        "dokploy-omni": {"env": {"DOKPLOY_URL": "https://painel-a/", "DOKPLOY_API_KEY": "chave-a"}},
        "dokploy-store": {"env": {"DOKPLOY_URL": "https://painel-b", "DOKPLOY_API_KEY": "chave-b"}},
        "outro": {"env": {"DOKPLOY_URL": "https://x", "DOKPLOY_API_KEY": "y"}},
    }})

    assert servidores_do_dokploy(tmp_path / ".claude.json") == [("https://painel-a", "chave-a"), ("https://painel-b", "chave-b")]


def _dokploy(respostas_por_rota, chamadas):
    def responder(pedido):
        if pedido.url.host == "quebrado":
            raise httpx.ConnectError("fora do ar")
        chamadas.append((pedido.url.path, pedido.headers.get("x-api-key")))
        rota = pedido.url.path.removeprefix("/api/")
        chave = f"{rota}?{pedido.url.query.decode()}" if pedido.url.query else rota
        if chave not in respostas_por_rota:
            return httpx.Response(404)
        return httpx.Response(200, json=respostas_por_rota[chave])
    return httpx.AsyncClient(transport=httpx.MockTransport(responder))


PROJETOS = [{"name": "Projects", "environments": [{"applications": [
    {"applicationId": "a1", "name": "Kanban"},
    {"applicationId": "a2", "name": "omni-api"},
    {"applicationId": "a3", "name": "themis-mcp"},
], "compose": []}]}]
DOMINIOS = {
    "project.all": PROJETOS,
    "domain.byApplicationId?applicationId=a1": [{"host": "kanban.exemplo.com", "https": True, "path": "/"}],
    "domain.byApplicationId?applicationId=a2": [{"host": "api.omni.exemplo.com", "https": True, "path": "/"}],
    "domain.byApplicationId?applicationId=a3": [{"host": "themis-mcp.exemplo.com", "https": True, "path": "/"}],
}


async def test_atualiza_com_as_telas_do_dokploy_sem_apis_nem_mcp(tmp_path):
    chamadas = []
    http = _dokploy(DOMINIOS, chamadas)

    await atualizar_sites_do_dokploy(http, [("https://painel", "chave-a")], tmp_path / "sites-dokploy.json")

    assert json.loads((tmp_path / "sites-dokploy.json").read_text()) == {
        "https://painel": {"Kanban": "https://kanban.exemplo.com/"},
    }
    assert all(chave == "chave-a" for _, chave in chamadas)


async def test_painel_fora_do_ar_mantem_o_que_ele_tinha_e_os_outros_atualizam(tmp_path):
    destino = tmp_path / "sites-dokploy.json"
    _gravar(destino, {
        "https://quebrado": {"Favo": "https://favo.exemplo.com/"},
        "https://painel": {"Antigo": "https://antigo.exemplo.com/"},
    })

    await atualizar_sites_do_dokploy(_dokploy(DOMINIOS, []), [("https://quebrado", "x"), ("https://painel", "c")], destino)

    assert json.loads(destino.read_text()) == {
        "https://quebrado": {"Favo": "https://favo.exemplo.com/"},
        "https://painel": {"Kanban": "https://kanban.exemplo.com/"},
    }


@pytest.mark.parametrize("host", ["api.omni.exemplo.com", "api-staging.exemplo.com", "registry.sc.exemplo.io", "x-31-97.traefik.me"])
async def test_enderecos_que_nao_sao_tela_ficam_de_fora(tmp_path, host):
    respostas = {
        "project.all": [{"name": "p", "environments": [{"applications": [{"applicationId": "a", "name": "App"}], "compose": []}]}],
        "domain.byApplicationId?applicationId=a": [{"host": host, "https": True, "path": "/"}],
    }

    await atualizar_sites_do_dokploy(_dokploy(respostas, []), [("https://painel", "c")], tmp_path / "s.json")

    assert json.loads((tmp_path / "s.json").read_text()) == {"https://painel": {}}


async def test_palavra_que_so_contem_api_continua_sendo_tela(tmp_path):
    respostas = {
        "project.all": [{"name": "p", "environments": [{"applications": [{"applicationId": "a", "name": "Mapa Capital"}], "compose": []}]}],
        "domain.byApplicationId?applicationId=a": [{"host": "capital.exemplo.com", "https": True, "path": "/"}],
    }

    await atualizar_sites_do_dokploy(_dokploy(respostas, []), [("https://painel", "c")], tmp_path / "s.json")

    assert json.loads((tmp_path / "s.json").read_text()) == {"https://painel": {"Mapa Capital": "https://capital.exemplo.com/"}}
