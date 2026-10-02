"""Voz para texto (faster-whisper, local) e texto para voz (Microsoft: edge-tts, gratuito, ou o
serviço de voz do Azure com chave, que tem mais vozes, como a Brenda)."""
import asyncio
import io
import logging
import re
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from xml.sax.saxutils import escape

import httpx

log = logging.getLogger(__name__)

Gerador = Callable[[str, Path], Awaitable[None]]


def gerar_azure(http: httpx.AsyncClient, chave: str, regiao: str, voz: str, velocidade: str) -> Gerador:
    """Voz do Azure AI Speech (faixa gratuita de 500 mil letras por mês em 02/10/2026). A chave só vai no cabeçalho."""
    endereco = f"https://{regiao}.tts.speech.microsoft.com/cognitiveservices/v1"

    async def gerar(texto: str, destino: Path) -> None:
        ssml = (f"<speak version='1.0' xml:lang='pt-BR'><voice name='{voz}'>"
                f"<prosody rate='{velocidade}'>{escape(texto)}</prosody></voice></speak>")
        resposta = await http.post(endereco, content=ssml.encode(), timeout=20, headers={
            "Ocp-Apim-Subscription-Key": chave,
            "Content-Type": "application/ssml+xml",
            "X-Microsoft-OutputFormat": "audio-24khz-48kbitrate-mono-mp3",
            "User-Agent": "clarisse",
        })
        resposta.raise_for_status()
        destino.write_bytes(resposta.content)

    return gerar


def gerar_edge(voz: str, velocidade: str) -> Gerador:
    async def gerar(texto: str, destino: Path) -> None:
        import edge_tts

        await edge_tts.Communicate(texto, voz, rate=velocidade).save(str(destino))

    return gerar


def com_reserva(principal: Gerador, reserva: Gerador) -> Gerador:
    """Se a voz principal falhar (limite do mês, rede), fala com a reserva em vez de ficar muda."""
    async def gerar(texto: str, destino: Path) -> None:
        try:
            await principal(texto, destino)
        except Exception:
            log.exception("a voz principal falhou; usando a reserva")
            await reserva(texto, destino)

    return gerar

_LINK_MARKDOWN = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_URL = re.compile(r"https?://\S+")
_MARCAS_DE_LISTA = re.compile(r"^\s*(?:#+|[-*•]|\d+[.)])\s*")
# Comando soletrado em voz alta não ajuda ninguém: o bloco vira um aviso.
_BLOCO_DE_CODIGO = re.compile(r"```.*?```", re.DOTALL)
_SEPARADOR_DE_TABELA = re.compile(r"^\s*\|?[\s:|-]*-{3,}[\s:|-]*$")


def _linha_de_tabela(linha: str) -> str:
    if not linha.strip().startswith("|"):
        return linha
    return ", ".join(celula.strip() for celula in linha.strip().strip("|").split("|") if celula.strip())


def texto_para_fala(texto: str) -> str:
    texto = _BLOCO_DE_CODIGO.sub("\nTrecho de código.\n", texto)
    texto = _LINK_MARKDOWN.sub(r"\1", texto)
    texto = _URL.sub("o link", texto)
    texto = re.sub(r"[*_`]", "", texto)
    frases = []
    for linha in texto.splitlines():
        if _SEPARADOR_DE_TABELA.match(linha):
            continue
        linha = _MARCAS_DE_LISTA.sub("", _linha_de_tabela(linha)).strip()
        if linha:
            frases.append(linha if linha[-1] in ".!?:;," else linha + ".")
    falado = " ".join(frases)
    if frases and not texto.rstrip().endswith((".", "!", "?")):
        falado = falado[:-1]
    return " ".join(falado.split())


_FIM_DE_FRASE = re.compile(r"(?<=[.!?;])\s+")
_TAMANHO_DO_TRECHO = 220


def dividir_em_trechos(texto: str) -> list[str]:
    """Texto já limpo para a fala, em trechos: a primeira frase sozinha, para a voz começar logo,
    e as seguintes juntas até ~220 letras, sem cortar nenhuma frase ao meio."""
    frases = [f for f in _FIM_DE_FRASE.split(texto_para_fala(texto)) if f]
    if not frases:
        return []
    trechos, atual = [frases[0]], ""
    for frase in frases[1:]:
        if atual and len(atual) + 1 + len(frase) > _TAMANHO_DO_TRECHO:
            trechos.append(atual)
            atual = frase
        else:
            atual = f"{atual} {frase}".strip()
    if atual:
        trechos.append(atual)
    return trechos


_PALAVRA = r"[^\W_]+"
_SEPARADOR = r"\s+(?:ponto|tra[cç]o|h[ií]fen|underline|underscore)\s+"
_ENDERECO_FALADO = re.compile(
    rf"\b({_PALAVRA}(?:{_SEPARADOR}{_PALAVRA})*)\s+arroba\s+({_PALAVRA}(?:\s+ponto\s+{_PALAVRA})+)\b", re.IGNORECASE,
)
_SIMBOLOS = {"ponto": ".", "traco": "-", "traço": "-", "hifen": "-", "hífen": "-", "underline": "_", "underscore": "_"}


def enderecos_falados(texto: str) -> str:
    """'fulano arroba empresa ponto com ponto br' vira 'fulano@empresa.com.br'. Só o que tem forma de
    endereço: 'ponto de vista' e 'o símbolo arroba' ficam como estão."""
    def escrever(achado: re.Match) -> str:
        partes = re.split(r"\s+", achado.group(0))
        return "".join("@" if p.lower() == "arroba" else _SIMBOLOS.get(p.lower(), p) for p in partes).lower()

    return _ENDERECO_FALADO.sub(escrever, texto)


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
        return enderecos_falados(" ".join(s.text.strip() for s in segmentos).strip())


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
        self._gerar = gerar or gerar_edge(voz, velocidade)
        self._guardar = guardar

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
