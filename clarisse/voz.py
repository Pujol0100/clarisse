"""Voz para texto (faster-whisper) e texto para voz (Kokoro), as duas na máquina: nada do que a
Clarisse ouve ou fala sai do notebook."""
import asyncio
import io
import re
import uuid
from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import soundfile

Gerador = Callable[[str, Path], Awaitable[None]]
_TAXA_DO_KOKORO = 24000
# Medido em 02/10/2026 (24 núcleos): com 4 a voz sai em ~1 s por frase e não sufoca o resto da máquina.
_THREADS_DA_VOZ = 4
_PARTE_DA_RECEITA = re.compile(r"^([a-z]{2}_[a-z]+)\*(\d+(?:\.\d+)?)$")


def receita_da_voz(receita: str) -> list[tuple[str, float]]:
    """'pf_dora*0.8+af_bella*0.2' (Dora com 20% de Bella, escolhida em 02/10/2026) vira [(voz, peso)]."""
    partes = []
    for parte in receita.replace(" ", "").split("+"):
        achado = _PARTE_DA_RECEITA.match(parte)
        if not achado:
            raise ValueError(f"receita de voz inválida: {receita!r} (exemplo: pf_dora*0.8+af_bella*0.2)")
        partes.append((achado.group(1), float(achado.group(2))))
    return partes


def carregar_kokoro():
    import misaki.espeak  # noqa: F401  aponta para o espeak embutido no espeakng-loader
    import torch
    from kokoro import KPipeline

    torch.set_num_threads(_THREADS_DA_VOZ)
    return KPipeline(lang_code="p", repo_id="hexgrad/Kokoro-82M")


def gerar_local(receita: str, velocidade: float, carregar: Callable[[], object] = carregar_kokoro) -> Gerador:
    """Voz do Kokoro, no processador. O modelo carrega no primeiro uso; a receita é conferida já.

    Toda frase é gerada na mesma thread: o PyTorch cria um grupo de trabalhadores por thread, e uma
    thread nova a cada frase lotava o processador (5,4 s por frase em vez de ~1 s, 02/10/2026)."""
    partes = receita_da_voz(receita)
    estado: dict = {}
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="voz")

    def sintetizar(texto: str, destino: Path) -> None:
        if "pipeline" not in estado:
            pipeline = carregar()
            estado["pipeline"] = pipeline
            estado["voz"] = sum(peso * pipeline.load_voice(nome) for nome, peso in partes)
        pedacos = [np.asarray(audio) for _, _, audio in estado["pipeline"](texto, voice=estado["voz"], speed=velocidade)]
        audio = np.concatenate(pedacos) if pedacos else np.zeros(_TAXA_DO_KOKORO // 10, dtype="float32")
        soundfile.write(destino, audio, _TAXA_DO_KOKORO, format="MP3")

    async def gerar(texto: str, destino: Path) -> None:
        await asyncio.get_running_loop().run_in_executor(executor, sintetizar, texto, destino)

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
    def __init__(self, pasta: Path, gerar: Gerador, guardar: int = 20):
        self._pasta = pasta
        self._gerar = gerar
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
