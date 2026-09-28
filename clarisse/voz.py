"""Voz para texto (faster-whisper, local) e texto para voz (edge-tts, serviço da Microsoft)."""
import asyncio
import io
import re
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path

_URL = re.compile(r"https?://\S+")
_MARCAS_DE_LISTA = re.compile(r"^\s*(?:#+|[-*•]|\d+[.)])\s*")


def texto_para_fala(texto: str) -> str:
    texto = _URL.sub("o link", texto)
    texto = re.sub(r"[*_`]", "", texto)
    frases = []
    for linha in texto.splitlines():
        linha = _MARCAS_DE_LISTA.sub("", linha).strip()
        if linha:
            frases.append(linha if linha[-1] in ".!?:;," else linha + ".")
    falado = " ".join(frases)
    if frases and not texto.rstrip().endswith((".", "!", "?")):
        falado = falado[:-1]
    return " ".join(falado.split())


class Transcritor:
    def __init__(self, carregar: Callable[[], object], dicas: list[str]):
        self._carregar = carregar
        self._dicas = " ".join(dicas)
        self._modelo = None
        self._trava = asyncio.Lock()

    async def transcrever(self, audio: bytes) -> str:
        async with self._trava:
            if self._modelo is None:
                self._modelo = await asyncio.to_thread(self._carregar)
            return await asyncio.to_thread(self._transcrever, audio)

    def _transcrever(self, audio: bytes) -> str:
        segmentos, _ = self._modelo.transcribe(
            io.BytesIO(audio), language="pt", hotwords=self._dicas or None, vad_filter=True, beam_size=5,
        )
        return " ".join(s.text.strip() for s in segmentos).strip()


def carregar_whisper(modelo: str, dispositivo: str):
    from faster_whisper import WhisperModel

    return WhisperModel(modelo, device=dispositivo, compute_type="int8" if dispositivo == "cpu" else "float16")


class Locutor:
    def __init__(
        self,
        pasta: Path,
        gerar: Callable[[str, Path], Awaitable[None]] | None = None,
        voz: str = "pt-BR-ThalitaMultilingualNeural",
        velocidade: str = "+10%",
        guardar: int = 20,
    ):
        self._pasta = pasta
        self._gerar = gerar or self._edge_tts
        self._voz = voz
        self._velocidade = velocidade
        self._guardar = guardar

    async def _edge_tts(self, texto: str, destino: Path) -> None:
        import edge_tts

        await edge_tts.Communicate(texto, self._voz, rate=self._velocidade).save(str(destino))

    async def sintetizar(self, texto: str) -> Path:
        self._pasta.mkdir(parents=True, exist_ok=True)
        destino = self._pasta / f"{uuid.uuid4().hex}.mp3"
        await self._gerar(texto_para_fala(texto), destino)
        self._apagar_antigos()
        return destino

    def _apagar_antigos(self) -> None:
        audios = sorted(self._pasta.glob("*.mp3"), key=lambda p: p.stat().st_mtime_ns)
        for antigo in audios[: -self._guardar]:
            antigo.unlink(missing_ok=True)
