"""Previsão do tempo pelo Open-Meteo (sem chave), em graus Celsius e km/h, no fuso de Brasília."""
import logging
import math
from datetime import date
from typing import Literal

import httpx
from pydantic import Field

from clarisse.ferramentas.registro import Argumentos, Ferramenta
from clarisse.cartoes import Retorno

log = logging.getLogger(__name__)

_BUSCA = "https://geocoding-api.open-meteo.com/v1/search"
_PREVISAO = "https://api.open-meteo.com/v1/forecast"
_DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]

# Códigos de tempo da Organização Meteorológica Mundial, como o Open-Meteo devolve.
_CONDICOES = {
    0: "céu limpo", 1: "predominantemente limpo", 2: "parcialmente nublado", 3: "nublado",
    45: "neblina", 48: "neblina com geada",
    51: "garoa fraca", 53: "garoa", 55: "garoa forte", 56: "garoa congelante", 57: "garoa congelante",
    61: "chuva fraca", 63: "chuva moderada", 65: "chuva forte", 66: "chuva congelante", 67: "chuva congelante",
    71: "neve fraca", 73: "neve", 75: "neve forte", 77: "grãos de neve",
    80: "pancadas de chuva fracas", 81: "pancadas de chuva", 82: "pancadas de chuva fortes",
    85: "pancadas de neve", 86: "pancadas de neve fortes",
    95: "trovoada", 96: "trovoada com granizo", 99: "trovoada com granizo",
}


def _graus(valor: float) -> str:
    return f"{math.floor(valor + 0.5)} °C"


def _grau_curto(valor: float) -> str:
    return f"{math.floor(valor + 0.5)}°"


def _condicao(codigo: int) -> str:
    return _CONDICOES.get(codigo, "tempo indefinido")


class ArgsTempo(Argumentos):
    cidade: str | None = Field(None, max_length=80, description="Cidade, se o usuário disser uma")
    dia: Literal["agora", "hoje", "amanhã", "depois de amanhã"] | None = Field(
        None, description="De quando o usuário perguntou: agora, hoje, amanhã ou depois de amanhã"
    )


def ferramentas_do_tempo(cliente: httpx.AsyncClient, cidade_padrao: str | None) -> list[Ferramenta]:
    async def previsao_do_tempo(args: ArgsTempo) -> Retorno | str:
        cidade = args.cidade or cidade_padrao
        if not cidade:
            return "Diga de qual cidade você quer a previsão."
        try:
            busca = await cliente.get(
                _BUSCA, params={"name": cidade, "count": 1, "language": "pt", "countryCode": "BR"}, timeout=10
            )
            busca.raise_for_status()
            lugares = busca.json().get("results") or []
            if not lugares:
                return f"Não achei a cidade {cidade}."
            lugar = lugares[0]
            resposta = await cliente.get(
                _PREVISAO,
                params={
                    "latitude": lugar["latitude"],
                    "longitude": lugar["longitude"],
                    "current": "temperature_2m,apparent_temperature,relative_humidity_2m,weather_code,wind_speed_10m",
                    "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max",
                    "timezone": "America/Sao_Paulo",
                    "forecast_days": 3,
                },
                timeout=10,
            )
            resposta.raise_for_status()
            dados = resposta.json()
        except httpx.HTTPError as erro:
            log.warning("previsão do tempo falhou em %s: %r", erro.request.url, erro)
            return f"Não consegui consultar a previsão agora: {type(erro).__name__}."

        agora, dias = dados["current"], dados["daily"]
        partes = [
            f"{lugar['name']} agora: {_graus(agora['temperature_2m'])}, "
            f"sensação de {_graus(agora['apparent_temperature'])}, {_condicao(agora['weather_code'])}, "
            f"vento de {math.floor(agora['wind_speed_10m'] + 0.5)} km/h."
        ]
        cartao = {
            "tipo": "clima", "titulo": "Clima", "canto": lugar["name"],
            "temp": _grau_curto(agora["temperature_2m"]), "cond": _condicao(agora["weather_code"]).capitalize(),
            "dias": [],
        }
        for i, dia in enumerate(dias["time"]):
            nome_do_dia = _DIAS[date.fromisoformat(dia).weekday()]
            rotulo = ["Hoje", "Amanhã"][i] if i < 2 else nome_do_dia.capitalize()
            partes.append(
                f"{rotulo}: mínima de {_graus(dias['temperature_2m_min'][i])} e máxima de "
                f"{_graus(dias['temperature_2m_max'][i])}, {_condicao(dias['weather_code'][i])}, "
                f"{dias['precipitation_probability_max'][i]}% de chance de chuva."
            )
            cartao["dias"].append([
                ["Hoje", "Amanhã"][i] if i < 2 else nome_do_dia.split("-")[0].capitalize(),
                _grau_curto(dias["temperature_2m_min"][i]), _grau_curto(dias["temperature_2m_max"][i]),
                f"{dias['precipitation_probability_max'][i]}%",
            ])
        return Retorno(" ".join(partes), cartao=cartao)

    descricao = (
        "Consulta o tempo agora e a previsão de hoje, amanhã e depois. Use sempre que perguntarem de clima, "
        "temperatura ou chuva; nunca invente o tempo."
    )
    if cidade_padrao:
        descricao += f" Se o usuário não disser a cidade, use {cidade_padrao}."

    return [
        Ferramenta(
            "previsao_do_tempo",
            descricao,
            ArgsTempo,
            previsao_do_tempo,
            grupo="clima",
        )
    ]
