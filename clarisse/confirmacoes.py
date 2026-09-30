"""Confirmações pedidas pelo Claude em segundo plano: a Clarisse fala a pergunta e espera o usuário."""
import asyncio
from collections.abc import Awaitable, Callable

from clarisse.seguranca import confirma


class Confirmacoes:
    def __init__(self, anunciar: Callable[[str], Awaitable[None]], limite: float = 60):
        self._anunciar = anunciar
        self._limite = limite
        self._uma_por_vez = asyncio.Lock()
        self._resposta: asyncio.Future | None = None

    async def pedir(self, frase: str) -> bool:
        """Fala a pergunta e devolve True só com "sim" dentro do prazo."""
        async with self._uma_por_vez:
            self._resposta = asyncio.get_running_loop().create_future()
            try:
                await self._anunciar(frase)
                return await asyncio.wait_for(self._resposta, self._limite)
            except TimeoutError:
                return False
            finally:
                self._resposta = None

    def responder(self, fala: str) -> str | None:
        """Resolve a pergunta pendente com a fala do usuário; qualquer coisa além de "sim" cancela."""
        if self._resposta is None or self._resposta.done():
            return None
        aceito = confirma(fala)
        self._resposta.set_result(aceito)
        return "Pode deixar, o Claude segue." if aceito else "Cancelei o pedido do Claude."

    def cancelar(self) -> None:
        if self._resposta is not None and not self._resposta.done():
            self._resposta.set_result(False)
