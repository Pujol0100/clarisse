"""Cliente do Ollama: uma rodada de conversa com ferramentas, sem raciocínio estendido."""
from dataclasses import dataclass, field

import httpx


class ErroDoModelo(Exception):
    pass


@dataclass
class ChamadaDeFerramenta:
    nome: str
    argumentos: dict


@dataclass
class RespostaDoModelo:
    texto: str
    chamadas: list[ChamadaDeFerramenta] = field(default_factory=list)
    mensagem: dict = field(default_factory=dict)


class ClienteOllama:
    def __init__(self, http: httpx.AsyncClient, modelo: str, contexto: int = 8192):
        self._http = http
        self._modelo = modelo
        self._contexto = contexto

    async def conversar(self, mensagens: list[dict], ferramentas: list[dict]) -> RespostaDoModelo:
        corpo = {
            "model": self._modelo,
            "messages": mensagens,
            "tools": ferramentas,
            "stream": False,
            "think": False,
            "keep_alive": "30m",
            "options": {"temperature": 0, "num_ctx": self._contexto},
        }
        try:
            resposta = await self._http.post("/api/chat", json=corpo, timeout=120)
        except httpx.HTTPError as erro:
            raise ErroDoModelo(f"o Ollama não respondeu: {type(erro).__name__}") from erro
        if resposta.status_code != 200:
            raise ErroDoModelo(f"o Ollama respondeu {resposta.status_code}: {resposta.text[:300]}")
        mensagem = resposta.json()["message"]
        chamadas = [
            ChamadaDeFerramenta(c["function"]["name"], c["function"].get("arguments") or {})
            for c in mensagem.get("tool_calls") or []
        ]
        return RespostaDoModelo((mensagem.get("content") or "").strip(), chamadas, mensagem)
