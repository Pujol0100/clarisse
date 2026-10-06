"""Fronteira com a área de trabalho do Windows: volume, janelas, área de transferência e teclas."""
import ctypes
import time
from ctypes import wintypes

import psutil
import pyperclip
from pycaw.pycaw import AudioUtilities

_WS_EX_TOOLWINDOW = 0x00000080
_DWMWA_CLOAKED = 14


def definir_volume(nivel: int) -> None:
    AudioUtilities.GetSpeakers().EndpointVolume.SetMasterVolumeLevelScalar(nivel / 100, None)


def _escondida(janela: int) -> bool:
    """Janelas que o Windows mantém mas não mostra (aplicativos suspensos, entrada de texto)."""
    valor = wintypes.DWORD()
    ctypes.windll.dwmapi.DwmGetWindowAttribute(
        wintypes.HWND(janela), _DWMWA_CLOAKED, ctypes.byref(valor), ctypes.sizeof(valor),
    )
    return valor.value != 0


class AreaDeTrabalho:
    """As mesmas janelas do Alt+Tab. O pywinauto é importado só quando usado: ele mexe no COM ao carregar."""

    def listar(self) -> list[dict]:
        from pywinauto import Desktop

        janelas = []
        for janela in Desktop(backend="win32").windows(visible_only=True):
            titulo = janela.window_text()
            if not titulo or janela.exstyle() & _WS_EX_TOOLWINDOW or _escondida(janela.handle):
                continue
            janelas.append({
                "id": janela.handle, "titulo": titulo, "processo": psutil.Process(janela.process_id()).name(),
            })
        return janelas

    def ativar(self, janela: int) -> None:
        """Só volta quando a janela já está na frente: tecla mandada antes cai na janela anterior."""
        from pywinauto import Desktop

        Desktop(backend="win32").window(handle=janela).wrapper_object().set_focus()
        limite = time.monotonic() + 2
        while ctypes.windll.user32.GetForegroundWindow() != janela:
            if time.monotonic() > limite:
                raise RuntimeError("o Windows não deixou trazer a janela para a frente")
            time.sleep(0.05)

    def colar(self, texto: str) -> None:
        pyperclip.copy(texto)

    def apertar(self, teclas: str) -> None:
        from pywinauto.keyboard import send_keys

        send_keys(teclas)
