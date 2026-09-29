"""Junta as peças da Clarisse a partir dos ajustes e cadastros."""
import os
import secrets
from pathlib import Path

import httpx

from clarisse.agente import Agente
from clarisse.auditoria import Auditoria
from clarisse.config import Ajustes, Cadastros
from clarisse.eventos import Eventos
from clarisse.ferramentas.claude import Delegacoes, ferramentas_do_claude
from clarisse.ferramentas.noticias import ferramentas_de_noticias
from clarisse.ferramentas.processos import Executor
from clarisse.ferramentas.projetos import ferramentas_de_projetos
from clarisse.ferramentas.registro import Registro
from clarisse.ferramentas.sistema import ferramentas_do_sistema
from clarisse.llm import ClienteOllama
from clarisse.voz import Locutor, Transcritor, carregar_whisper
from clarisse.web import criar_app, criar_avisador

CAMINHO_DA_CHAVE = Path.home() / ".config" / "clarisse" / "chave"
PASTA_WEB = Path(__file__).resolve().parent.parent / "web"
# Fora de qualquer repositório: dentro de um, o Claude carrega o CLAUDE.md dele e acha que a pergunta é sobre o código.
PASTA_NEUTRA_DO_CLAUDE = Path.home() / ".local" / "share" / "clarisse" / "claude"


def gravar_chave(caminho: Path, chave: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    caminho.unlink(missing_ok=True)
    descritor = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descritor, "w") as arquivo:
        arquivo.write(chave)


def montar_registro(ajustes: Ajustes, cadastros: Cadastros, executor, http: httpx.AsyncClient, delegacoes: Delegacoes) -> Registro:
    registro = Registro()
    ferramentas = [
        *ferramentas_do_sistema(cadastros, executor),
        *ferramentas_de_projetos(cadastros, executor),
        *ferramentas_do_claude(
            cadastros, executor, delegacoes,
            pasta_neutra=PASTA_NEUTRA_DO_CLAUDE,
            modelo=ajustes.claude_modelo,
            timeout=ajustes.claude_timeout,
            teto_usd=ajustes.claude_teto_usd,
        ),
        *ferramentas_de_noticias(http),
    ]
    for ferramenta in ferramentas:
        registro.registrar(ferramenta)
    return registro


def montar_app(ajustes: Ajustes, cadastros: Cadastros):
    chave = secrets.token_urlsafe(32)
    gravar_chave(CAMINHO_DA_CHAVE, chave)

    eventos = Eventos()
    locutor = Locutor(ajustes.pasta_dados / "audio", voz=ajustes.voz, velocidade=ajustes.voz_velocidade)
    delegacoes = Delegacoes(criar_avisador(eventos, locutor))
    http_externo = httpx.AsyncClient()
    registro = montar_registro(ajustes, cadastros, Executor(), http_externo, delegacoes)
    modelo = ClienteOllama(httpx.AsyncClient(base_url=ajustes.ollama_url), ajustes.modelo)
    agente = Agente(
        modelo, registro, eventos, Auditoria(ajustes.pasta_dados / "auditoria.jsonl"),
        projetos=list(cadastros.projetos),
    )
    transcritor = Transcritor(
        carregar=lambda: carregar_whisper(ajustes.whisper_modelo, ajustes.whisper_dispositivo),
        dicas=list(cadastros.projetos),
    )
    return criar_app(
        agente=agente, eventos=eventos, transcritor=transcritor, locutor=locutor,
        chave=chave, porta=ajustes.porta, pasta_web=PASTA_WEB, pasta_audio=ajustes.pasta_dados / "audio",
    )
