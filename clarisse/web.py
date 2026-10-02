"""Rotas da Clarisse, WebSocket de eventos e a portaria que protege a porta local."""
import asyncio
import contextlib
import logging
import uuid
import re
import secrets
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field
from starlette.datastructures import Headers, MutableHeaders
from starlette.requests import cookie_parser
from starlette.responses import PlainTextResponse
from starlette.websockets import WebSocketClose

from clarisse.auditoria import Auditoria
from clarisse.eventos import Estado, Eventos
from clarisse.voz import dividir_em_trechos

log = logging.getLogger(__name__)

COOKIE = "clarisse_chave"
LIMITE_DO_AUDIO = 10 * 1024 * 1024
_NOME_DE_AUDIO = re.compile(r"^[0-9a-f]{32}\.mp3$")
_ROTAS_COM_CHAVE = ("/api/", "/audio/", "/ws")


def _cabecalhos_de_seguranca(porta: int) -> dict[str, str]:
    conexoes = f"'self' ws://127.0.0.1:{porta} ws://localhost:{porta}"
    return {
        "Content-Security-Policy": (
            # Fotos das notícias vêm do servidor de imagens da Globo; nada mais de fora.
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data: https://*.glbimg.com; "
            f"media-src 'self' blob:; connect-src {conexoes}; frame-ancestors 'none'; "
            "base-uri 'none'; form-action 'self'; object-src 'none'"
        ),
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "microphone=(self), camera=(), geolocation=(), payment=(), usb=()",
        "Cache-Control": "no-store",
    }


class Portaria:
    """Só a própria página, em 127.0.0.1, com a chave da sessão, fala com a Clarisse."""

    def __init__(self, app, chave: str, porta: int):
        self.app = app
        self._chave = chave
        self._hosts = {f"127.0.0.1:{porta}", f"localhost:{porta}"}
        self._origens = {f"http://{h}" for h in self._hosts}
        self._cabecalhos = _cabecalhos_de_seguranca(porta)

    async def __call__(self, scope, receive, send):
        if scope["type"] not in ("http", "websocket"):
            return await self.app(scope, receive, send)

        cabecalhos = Headers(scope=scope)
        if cabecalhos.get("host") not in self._hosts:
            return await self._recusar(scope, receive, send, 400)
        origem = cabecalhos.get("origin")
        if origem is not None and origem not in self._origens:
            return await self._recusar(scope, receive, send, 403)
        if scope["path"].startswith(_ROTAS_COM_CHAVE) and not self._chave_confere(cabecalhos):
            return await self._recusar(scope, receive, send, 401)

        if scope["type"] == "websocket":
            return await self.app(scope, receive, send)

        async def enviar_com_cabecalhos(mensagem):
            if mensagem["type"] == "http.response.start":
                resposta = MutableHeaders(scope=mensagem)
                for nome, valor in self._cabecalhos.items():
                    resposta[nome] = valor
            await send(mensagem)

        await self.app(scope, receive, enviar_com_cabecalhos)

    def _chave_confere(self, cabecalhos: Headers) -> bool:
        fornecida = cabecalhos.get("x-clarisse-chave") or cookie_parser(cabecalhos.get("cookie", "")).get(COOKIE)
        return bool(fornecida) and secrets.compare_digest(fornecida, self._chave)

    async def _recusar(self, scope, receive, send, codigo: int):
        if scope["type"] == "websocket":
            return await WebSocketClose(code=1008)(scope, receive, send)
        await PlainTextResponse(str(codigo), status_code=codigo)(scope, receive, send)


class PedidoDeFerramenta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nome: str = Field(min_length=1, max_length=80)
    argumentos: dict = Field(default_factory=dict)


class Mensagem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    texto: str = Field(min_length=1, max_length=2000)


def _nova_fala() -> str:
    return uuid.uuid4().hex


def _trechos(texto: str, cartao: dict | None = None) -> list[tuple[str, int | None]]:
    """Trechos da fala e o parágrafo de onde cada um saiu. Na leitura de uma matéria, o título vai
    primeiro e cada parágrafo se divide sozinho, para a tela acender o parágrafo da vez."""
    if not (cartao and cartao.get("tipo") == "leitura"):
        return [(trecho, None) for trecho in dividir_em_trechos(texto)]
    titulo = cartao["titulo"] if cartao["titulo"].endswith((".", "!", "?")) else f"{cartao['titulo']}."
    return [(trecho, None) for trecho in dividir_em_trechos(titulo)] + [
        (trecho, i) for i, paragrafo in enumerate(cartao["paragrafos"]) for trecho in dividir_em_trechos(paragrafo)
    ]


async def _falar(eventos: Eventos, locutor, texto: str, fala: str | None = None, cartao: dict | None = None) -> str | None:
    """Fala em trechos: o primeiro sai assim que fica pronto e os outros são gerados enquanto ele toca.
    Cada trecho leva a legenda; o texto na tela espera a fala `fala` começar."""
    fala = fala or _nova_fala()
    trechos = _trechos(texto, cartao)
    primeiro = None
    for parte, (trecho, paragrafo) in enumerate(trechos):
        try:
            caminho = await locutor.sintetizar(trecho)
        except Exception:
            log.exception("a síntese de voz falhou")
            await eventos.publicar({"tipo": "erro", "fala": fala, "texto": "A voz não está disponível agora; a resposta ficou só na tela."})
            await eventos.estado(Estado.PARADA)
            return primeiro
        url = f"/audio/{caminho.name}"
        if parte == 0:
            await eventos.estado(Estado.FALANDO)
        await eventos.publicar({
            "tipo": "falar", "fala": fala, "parte": parte, "total": len(trechos),
            "audio": url, "legenda": trecho, "paragrafo": paragrafo,
        })
        primeiro = primeiro or url
    return primeiro


def criar_anunciador(eventos: Eventos, locutor) -> Callable[[str], Awaitable[None]]:
    """Pergunta de confirmação vinda do Claude: aparece com os botões e é falada."""
    async def anunciar(frase: str) -> None:
        fala = _nova_fala()
        await eventos.publicar({"tipo": "resposta", "fala": fala, "texto": frase, "aguardando_confirmacao": True})
        await _falar(eventos, locutor, frase, fala=fala)

    return anunciar


def criar_avisador(eventos: Eventos, locutor) -> Callable[[str, str], Awaitable[None]]:
    async def avisar(titulo: str, texto: str, falar: str | None = None) -> None:
        fala = _nova_fala()
        cartao = {"tipo": "texto", "titulo": titulo, "texto": texto}
        falado = falar or f"Do {titulo}: {texto}"
        await eventos.publicar({"tipo": "aviso", "fala": fala, "titulo": titulo, "texto": texto, "cartao": cartao, "falado": falado})
        await _falar(eventos, locutor, falado, fala=fala)

    return avisar


def criar_app(
    *, agente, eventos: Eventos, transcritor, locutor, chave: str, porta: int, pasta_web: Path, pasta_audio: Path,
    conversa: Auditoria,
    tarefas_de_fundo: list[Callable[[], Awaitable[None]]] = (),
    externas=None,
) -> FastAPI:
    @contextlib.asynccontextmanager
    async def ciclo_de_vida(app):
        tarefas = [asyncio.create_task(t()) for t in tarefas_de_fundo]
        yield
        for tarefa in tarefas:
            tarefa.cancel()
        await asyncio.gather(*tarefas, return_exceptions=True)

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=ciclo_de_vida)
    app.add_middleware(Portaria, chave=chave, porta=porta)
    app.mount("/static", StaticFiles(directory=pasta_web), name="static")

    async def processar(texto: str) -> dict:
        await eventos.publicar({"tipo": "fala_do_usuario", "texto": texto})
        resposta = await agente.responder(texto)
        conversa.registrar(
            fala=texto, resposta=resposta.texto,
            aguardando_confirmacao=resposta.aguardando_confirmacao, parar=resposta.parar,
        )
        if resposta.parar:
            await eventos.publicar({"tipo": "parar"})
            await eventos.estado(Estado.PARADA)
            return {"texto": resposta.texto, "audio": None, "aguardando_confirmacao": False, "parar": True}
        fala = _nova_fala()
        await eventos.publicar({
            "tipo": "resposta", "fala": fala, "texto": resposta.texto,
            "aguardando_confirmacao": resposta.aguardando_confirmacao, "cartao": resposta.cartao,
        })
        audio = await _falar(eventos, locutor, resposta.texto, fala=fala, cartao=resposta.cartao)
        return {
            "texto": resposta.texto,
            "audio": audio,
            "aguardando_confirmacao": resposta.aguardando_confirmacao,
            "parar": False,
            "cartao": resposta.cartao,
        }

    @app.get("/", response_class=HTMLResponse)
    async def pagina():
        resposta = HTMLResponse((pasta_web / "index.html").read_text(encoding="utf-8"))
        resposta.set_cookie(COOKIE, chave, httponly=True, samesite="strict", path="/")
        return resposta

    @app.get("/health")
    async def saude():
        return {"ok": True}

    @app.get("/api/estado")
    async def estado():
        return {"estado": eventos.estado_atual.value}

    @app.get("/api/ferramentas")
    async def ferramentas():
        """Para o servidor MCP da Clarisse: o que o Claude pode pedir."""
        if externas is None:
            raise HTTPException(404)
        return {"ferramentas": externas.esquemas()}

    @app.post("/api/ferramenta")
    async def ferramenta(corpo: PedidoDeFerramenta):
        """Para o servidor MCP da Clarisse: executa com a mesma avaliação e confirmação da voz."""
        if externas is None:
            raise HTTPException(404)
        return {"resultado": await externas.executar(corpo.nome, corpo.argumentos)}

    @app.post("/api/mensagem")
    async def mensagem(corpo: Mensagem):
        return await processar(corpo.texto.strip())

    @app.post("/api/voz")
    async def voz(request: Request):
        if not request.headers.get("content-type", "").startswith("audio/"):
            raise HTTPException(415, "envie áudio")
        if int(request.headers.get("content-length") or 0) > LIMITE_DO_AUDIO:
            raise HTTPException(413, "áudio grande demais")
        audio = bytearray()
        async for pedaco in request.stream():
            audio += pedaco
            if len(audio) > LIMITE_DO_AUDIO:
                raise HTTPException(413, "áudio grande demais")

        await eventos.estado(Estado.PENSANDO)
        texto = await transcritor.transcrever(bytes(audio))
        await eventos.publicar({"tipo": "transcricao", "texto": texto})
        if not texto:
            await eventos.estado(Estado.PARADA)
            return {"transcricao": "", "texto": None, "audio": None, "aguardando_confirmacao": False, "parar": False}
        return {"transcricao": texto, **await processar(texto)}

    @app.post("/api/escutar")
    async def escutar():
        await eventos.publicar({"tipo": "escutar"})
        return {"ok": True}

    @app.post("/api/fim-da-fala")
    async def fim_da_fala():
        await eventos.estado(Estado.PARADA)
        return {"ok": True}

    @app.get("/audio/{nome}")
    async def audio(nome: str):
        caminho = pasta_audio / nome
        if not _NOME_DE_AUDIO.match(nome) or not caminho.is_file():
            raise HTTPException(404)
        return FileResponse(caminho, media_type="audio/mpeg")

    @app.websocket("/ws")
    async def ws(websocket: WebSocket):
        await websocket.accept()
        fila = eventos.assinar()
        eventos.entrar_na_voz(fila)

        async def enviar():
            await websocket.send_json({"tipo": "estado", "estado": eventos.estado_atual.value})
            while True:
                await websocket.send_json(await fila.get())

        async def receber():
            while True:
                if await websocket.receive_text() == "voz":
                    eventos.pedir_a_voz(fila)

        tarefas = [asyncio.create_task(enviar()), asyncio.create_task(receber())]
        try:
            await asyncio.wait(tarefas, return_when=asyncio.FIRST_COMPLETED)
        except WebSocketDisconnect:
            pass
        finally:
            for tarefa in tarefas:
                tarefa.cancel()
            eventos.cancelar(fila)

    return app
