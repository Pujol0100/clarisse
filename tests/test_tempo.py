import httpx
import pytest

from clarisse.ferramentas.tempo import ferramentas_do_tempo

CURITIBA = {"results": [{"name": "Curitiba", "admin1": "Paraná", "latitude": -25.43, "longitude": -49.27}]}
PREVISAO = {
    "current": {"temperature_2m": 24.1, "apparent_temperature": 25.8, "relative_humidity_2m": 64,
                "weather_code": 3, "wind_speed_10m": 4.9},
    "daily": {"time": ["2026-09-29", "2026-09-30", "2026-10-01"], "weather_code": [95, 61, 0],
              "temperature_2m_max": [30.1, 26.7, 22.6], "temperature_2m_min": [15.0, 19.2, 13.2],
              "precipitation_probability_max": [91, 60, 0]},
}


def _montar(responder, cidade_padrao="Curitiba"):
    cliente = httpx.AsyncClient(transport=httpx.MockTransport(responder))
    [f] = ferramentas_do_tempo(cliente, cidade_padrao=cidade_padrao)
    return f


def _responder_normal(pedidos):
    def responder(pedido):
        pedidos.append(pedido.url)
        if pedido.url.host.startswith("geocoding"):
            return httpx.Response(200, json=CURITIBA)
        return httpx.Response(200, json=PREVISAO)
    return responder


async def test_previsao_em_portugues_com_celsius_e_km_por_hora():
    pedidos = []
    f = _montar(_responder_normal(pedidos))

    resposta = (await f.executar(f.argumentos(cidade="Curitiba"))).texto

    assert "Curitiba agora: 24 °C, sensação de 26 °C, nublado, vento de 5 km/h" in resposta
    assert "Hoje: mínima de 15 °C e máxima de 30 °C, trovoada, 91% de chance de chuva" in resposta
    assert "Amanhã: mínima de 19 °C e máxima de 27 °C, chuva fraca, 60% de chance de chuva" in resposta


async def test_busca_a_cidade_no_brasil_em_portugues_e_usa_o_fuso_de_brasilia():
    pedidos = []
    f = _montar(_responder_normal(pedidos))

    await f.executar(f.argumentos(cidade="Curitiba"))

    busca, previsao = pedidos
    assert busca.params["name"] == "Curitiba"
    assert busca.params["countryCode"] == "BR"
    assert busca.params["language"] == "pt"
    assert previsao.params["latitude"] == "-25.43"
    assert previsao.params["timezone"] == "America/Sao_Paulo"


async def test_sem_cidade_usa_a_cidade_padrao():
    pedidos = []
    f = _montar(_responder_normal(pedidos), cidade_padrao="Curitiba")

    await f.executar(f.argumentos())

    assert pedidos[0].params["name"] == "Curitiba"


async def test_sem_cidade_e_sem_padrao_pede_a_cidade():
    pedidos = []
    f = _montar(_responder_normal(pedidos), cidade_padrao=None)

    resposta = await f.executar(f.argumentos())

    assert pedidos == []
    assert "cidade" in resposta.lower()


async def test_cidade_nao_encontrada_vira_mensagem():
    f = _montar(lambda p: httpx.Response(200, json={}))

    resposta = await f.executar(f.argumentos(cidade="Xyzabc"))

    assert "não achei a cidade xyzabc" in resposta.lower()


@pytest.mark.parametrize("falha", [httpx.Response(503), httpx.ConnectError("sem rede")])
async def test_falha_do_servico_vira_mensagem(falha):
    def responder(pedido):
        if isinstance(falha, Exception):
            raise falha
        return falha

    f = _montar(responder)

    resposta = await f.executar(f.argumentos(cidade="Curitiba"))

    assert "não consegui" in resposta.lower()


def test_descricao_avisa_o_modelo_da_cidade_padrao():
    com_padrao = _montar(lambda p: httpx.Response(200), cidade_padrao="Curitiba")
    sem_padrao = _montar(lambda p: httpx.Response(200), cidade_padrao=None)

    assert "use Curitiba" in com_padrao.descricao
    assert "Curitiba" not in sem_padrao.descricao


@pytest.mark.parametrize("dia,figura", [(None, "nuvem"), ("agora", "nuvem"), ("hoje", "trovoada"), ("amanhã", "chuva"), ("depois de amanhã", "sol")])
async def test_figura_segue_o_dia_perguntado(dia, figura):
    f = _montar(_responder_normal([]))

    resposta = await f.executar(f.argumentos(cidade="Curitiba", dia=dia))

    assert resposta.figura == figura


def test_dia_fora_da_lista_e_invalido():
    f = _montar(_responder_normal([]))

    with pytest.raises(ValueError):
        f.argumentos(dia="semana que vem")
