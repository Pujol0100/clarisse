"""Previsão do tempo pelo Open-Meteo (sem chave), em graus Celsius e km/h, no fuso de Brasília."""
import math
from datetime import date

import httpx
from pydantic import Field

from clarisse.ferramentas.registro import Argumentos, Ferramenta

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


def _condicao(codigo: int) -> str:
    return _CONDICOES.get(codigo, "tempo indefinido")


class ArgsTempo(Argumentos):
    cidade: str | None = Field(None, max_length=80, description="Cidade, se o usuário disser uma")


def ferramentas_do_tempo(cliente: httpx.AsyncClient, cidade_padrao: str | None) -> list[Ferramenta]:
    async def previsao_do_tempo(args: ArgsTempo) -> str:
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
            return f"Não consegui consultar a previsão agora: {type(erro).__name__}."

        agora, dias = dados["current"], dados["daily"]
        partes = [
            f"{lugar['name']} agora: {_graus(agora['temperature_2m'])}, "
            f"sensação de {_graus(agora['apparent_temperature'])}, {_condicao(agora['weather_code'])}, "
            f"vento de {math.floor(agora['wind_speed_10m'] + 0.5)} km/h."
        ]
        for i, dia in enumerate(dias["time"]):
            rotulo = ["Hoje", "Amanhã"][i] if i < 2 else _DIAS[date.fromisoformat(dia).weekday()].capitalize()
            partes.append(
                f"{rotulo}: mínima de {_graus(dias['temperature_2m_min'][i])} e máxima de "
                f"{_graus(dias['temperature_2m_max'][i])}, {_condicao(dias['weather_code'][i])}, "
                f"{dias['precipitation_probability_max'][i]}% de chance de chuva."
            )
        return " ".join(partes)

    return [
        Ferramenta(
            "previsao_do_tempo",
            "Consulta o tempo agora e a previsão de hoje, amanhã e depois. Use sempre que perguntarem de clima, "
            "temperatura ou chuva; nunca invente o tempo.",
            ArgsTempo,
            previsao_do_tempo,
        )
    ]
