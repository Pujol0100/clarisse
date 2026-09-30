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
    """Todas as telas recebem os eventos, mas só uma toca a voz: a última que a pediu (a que a pessoa
    usou), ou, sem pedido, a que está aberta há mais tempo. Página que reconecta entra atrás das outras."""

    def __init__(self, tamanho_da_fila: int = 100):
        self._tamanho = tamanho_da_fila
        self.assinantes: set[asyncio.Queue] = set()
        self.estado_atual = Estado.PARADA
        self._fila_da_voz: list[asyncio.Queue] = []

    def assinar(self) -> asyncio.Queue:
        fila = asyncio.Queue(maxsize=self._tamanho)
        self.assinantes.add(fila)
        return fila

    def entrar_na_voz(self, fila: asyncio.Queue) -> None:
        """Tela que toca áudio: entra na disputa pela voz e fica sabendo se é ela quem fala."""
        self._fila_da_voz.insert(0, fila)
        self._avisar_da_voz(fila, fila is self._dona_da_voz())

    def cancelar(self, fila: asyncio.Queue) -> None:
        self.assinantes.discard(fila)
        self._trocar_a_voz(lambda: self._fila_da_voz.remove(fila) if fila in self._fila_da_voz else None)

    def pedir_a_voz(self, fila: asyncio.Queue) -> None:
        if fila in self._fila_da_voz:
            self._trocar_a_voz(lambda: (self._fila_da_voz.remove(fila), self._fila_da_voz.append(fila)))

    def _dona_da_voz(self) -> asyncio.Queue | None:
        return self._fila_da_voz[-1] if self._fila_da_voz else None

    def _trocar_a_voz(self, mudar) -> None:
        antes = self._dona_da_voz()
        mudar()
        depois = self._dona_da_voz()
        if antes is depois:
            return
        if antes in self.assinantes:
            self._avisar_da_voz(antes, False)
        if depois is not None:
            self._avisar_da_voz(depois, True)

    def _avisar_da_voz(self, fila: asyncio.Queue, sua: bool) -> None:
        try:
            fila.put_nowait({"tipo": "voz", "sua": sua})
        except asyncio.QueueFull:
            self.cancelar(fila)

    async def publicar(self, evento: dict) -> None:
        evento = {**evento, "quando": datetime.now().isoformat(timespec="seconds")}
        for fila in list(self.assinantes):
            try:
                fila.put_nowait(evento)
            except asyncio.QueueFull:
                self.cancelar(fila)

    async def estado(self, estado: Estado) -> None:
        self.estado_atual = estado
        await self.publicar({"tipo": "estado", "estado": estado.value})
