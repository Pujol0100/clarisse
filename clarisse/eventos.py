"""Estados da Clarisse e distribuição de eventos para as telas conectadas."""
import asyncio
from datetime import datetime
from enum import Enum


class Estado(str, Enum):
    PARADA = "idle"
    OUVINDO = "listening"
    PENSANDO = "thinking"
    EXECUTANDO = "executing"
    FALANDO = "speaking"
    ERRO = "error"


class Eventos:
    def __init__(self, tamanho_da_fila: int = 100):
        self._tamanho = tamanho_da_fila
        self.assinantes: set[asyncio.Queue] = set()
        self.estado_atual = Estado.PARADA

    def assinar(self) -> asyncio.Queue:
        fila = asyncio.Queue(maxsize=self._tamanho)
        self.assinantes.add(fila)
        return fila

    def cancelar(self, fila: asyncio.Queue) -> None:
        self.assinantes.discard(fila)

    async def publicar(self, evento: dict) -> None:
        evento = {**evento, "quando": datetime.now().isoformat(timespec="seconds")}
        for fila in list(self.assinantes):
            try:
                fila.put_nowait(evento)
            except asyncio.QueueFull:
                self.assinantes.discard(fila)

    async def estado(self, estado: Estado) -> None:
        self.estado_atual = estado
        await self.publicar({"tipo": "estado", "estado": estado.value})
