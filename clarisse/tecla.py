"""Tecla Insert em qualquer janela: liga e desliga o microfone da Clarisse."""
import asyncio
import ctypes
import threading
from collections.abc import AsyncIterator, Awaitable, Callable
from ctypes import wintypes

_VK_INSERT = 0x2D
_MOD_NOREPEAT = 0x4000
_WM_HOTKEY = 0x0312
_WM_QUIT = 0x0012
_ID_DA_TECLA = 1


async def tecla_insert() -> AsyncIterator[None]:
    """Um item a cada aperto. O Windows entrega a tecla na fila de mensagens da thread que a registrou."""
    loop = asyncio.get_running_loop()
    apertos: asyncio.Queue[None] = asyncio.Queue()
    registrada: asyncio.Future[int] = loop.create_future()

    def escutar() -> None:
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        if not user32.RegisterHotKey(None, _ID_DA_TECLA, _MOD_NOREPEAT, _VK_INSERT):
            erro = OSError(f"não consegui registrar a tecla Insert: {ctypes.WinError(ctypes.get_last_error())}")
            loop.call_soon_threadsafe(registrada.set_exception, erro)
            return
        loop.call_soon_threadsafe(registrada.set_result, ctypes.windll.kernel32.GetCurrentThreadId())
        mensagem = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(mensagem), None, 0, 0) > 0:
            if mensagem.message == _WM_HOTKEY:
                loop.call_soon_threadsafe(apertos.put_nowait, None)
        user32.UnregisterHotKey(None, _ID_DA_TECLA)

    threading.Thread(target=escutar, name="tecla-insert", daemon=True).start()
    thread = await registrada
    try:
        while True:
            yield await apertos.get()
    finally:
        ctypes.windll.user32.PostThreadMessageW(thread, _WM_QUIT, 0, 0)


async def escutar_pela_tecla(
    publicar: Callable[[dict], Awaitable[None]], apertos: Callable[[], AsyncIterator[None]] = tecla_insert,
) -> None:
    async for _ in apertos():
        await publicar({"tipo": "escutar"})
