"""Junta as peças da Clarisse a partir dos ajustes e cadastros."""
import json
import os
import secrets
import sys
from pathlib import Path

import httpx

from clarisse.agenda_linux import agendas_do_microsoft365, atualizar_agendas, manter_agendas_atualizadas
from clarisse.agente import Agente
from clarisse.auditoria import Auditoria
from clarisse.config import Ajustes, Cadastros
from clarisse.confirmacoes import Confirmacoes
from clarisse.eventos import Eventos
from clarisse.externas import FerramentasExternas
from clarisse.ferramentas.aplicacoes import carregar_bancos, esperar_site, ferramentas_de_aplicacoes
from clarisse.ferramentas.claude import Delegacoes, ferramentas_do_claude
from clarisse.ferramentas.janelas import ferramentas_de_janelas
from clarisse.ferramentas.noticias import ferramentas_de_noticias
from clarisse.ferramentas.processos import Executor
from clarisse.ferramentas.projetos import ferramentas_de_projetos
from clarisse.ferramentas.registro import Registro
from clarisse.sites import carregar_sites, manter_sites_atualizados
from clarisse.ferramentas.sistema import ferramentas_do_sistema
from clarisse.ferramentas.tempo import ferramentas_do_tempo
from clarisse.llm import ClienteOllama
from clarisse.voz import Locutor, Transcritor, carregar_whisper
from clarisse.web import criar_anunciador, criar_app, criar_avisador

CAMINHO_DA_CHAVE = Path.home() / ".config" / "clarisse" / "chave"
RAIZ = Path(__file__).resolve().parent.parent
# Ferramentas que chamariam outro Claude: o Claude das etapas não pode pedi-las.
FORA_DO_CLAUDE = {"pedir_ao_claude", "fazer_em_etapas"}
PASTA_WEB = Path(__file__).resolve().parent.parent / "web"
# Fora de qualquer repositório: dentro de um, o Claude carrega o CLAUDE.md dele e acha que a pergunta é sobre o código.
PASTA_NEUTRA_DO_CLAUDE = Path.home() / ".local" / "share" / "clarisse" / "claude"
# Palavras que a transcrição erra sem dica: "git" virou "G de" na medição de 29/09/2026.
VOCABULARIO_FALADO = ["Clarisse", "Claude", "git", "git status", "git pull", "VS Code"]
# Versão fixa: com @latest o npx baixaria código novo sem revisão a cada tarefa.
PLAYWRIGHT_MCP = "@playwright/mcp@0.0.83"


def gravar_chave(caminho: Path, chave: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    caminho.unlink(missing_ok=True)
    descritor = os.open(caminho, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descritor, "w") as arquivo:
        arquivo.write(chave)


def _config_do_navegador() -> Path:
    """O Claude das tarefas no navegador só enxerga este servidor: o Playwright, com janela visível para login."""
    PASTA_NEUTRA_DO_CLAUDE.mkdir(parents=True, exist_ok=True)
    caminho = PASTA_NEUTRA_DO_CLAUDE / "mcp-navegador.json"
    caminho.write_text(json.dumps({"mcpServers": {"playwright": {"command": "npx", "args": ["-y", PLAYWRIGHT_MCP]}}}))
    return caminho


def _config_da_clarisse(porta: int) -> Path:
    """O Claude das tarefas em etapas só enxerga este servidor: as ferramentas da própria Clarisse."""
    PASTA_NEUTRA_DO_CLAUDE.mkdir(parents=True, exist_ok=True)
    caminho = PASTA_NEUTRA_DO_CLAUDE / "mcp-clarisse.json"
    servidor = {
        "command": sys.executable,
        "args": ["-m", "clarisse.mcp_servidor"],
        "env": {"PYTHONPATH": str(RAIZ), "CLARISSE_PORTA": str(porta)},
    }
    caminho.write_text(json.dumps({"mcpServers": {"clarisse": servidor}}))
    return caminho


def montar_registro(
    ajustes: Ajustes, cadastros: Cadastros, executor, http: httpx.AsyncClient, delegacoes: Delegacoes,
    apos_mudar_agenda=None,
) -> Registro:
    registro = Registro()
    http_local = httpx.AsyncClient()

    def sites_da_empresa():
        return carregar_sites(ajustes.pasta_config)

    raizes = sorted({pasta.parent for pasta in cadastros.projetos.values()})

    ferramentas = [
        *ferramentas_do_sistema(cadastros, executor, sites=sites_da_empresa, raizes=raizes),
        *ferramentas_de_projetos(cadastros, executor),
        *ferramentas_de_janelas(cadastros, executor),
        *ferramentas_de_aplicacoes(
            executor, delegacoes,
            raizes=raizes,
            bancos=carregar_bancos(ajustes.pasta_config / "bancos.json"),
            esperar_site=lambda endereco, limite: esperar_site(endereco, http_local, limite=limite),
            cadastros=cadastros,
            sites=sites_da_empresa,
        ),
        *ferramentas_do_claude(
            cadastros, executor, delegacoes,
            pasta_neutra=PASTA_NEUTRA_DO_CLAUDE,
            modelo=ajustes.claude_modelo,
            timeout=ajustes.claude_timeout,
            teto_usd=ajustes.claude_teto_usd,
            apos_mudar_agenda=apos_mudar_agenda,
            mcp_navegador=_config_do_navegador(),
            mcp_clarisse=_config_da_clarisse(ajustes.porta),
        ),
        *ferramentas_de_noticias(http),
        *ferramentas_do_tempo(http, cidade_padrao=ajustes.cidade),
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
    executor = Executor()

    async def atualizar_agenda_do_linux():
        await atualizar_agendas(executor, agendas_do_microsoft365())

    async def manter_sites_da_empresa():
        await manter_sites_atualizados(
            http_externo, Path.home() / ".claude.json", ajustes.pasta_config / "sites-dokploy.json",
        )

    async def manter_agenda_do_linux():
        await manter_agendas_atualizadas(executor, agendas_do_microsoft365, ajustes.agenda_intervalo_minutos * 60)

    registro = montar_registro(ajustes, cadastros, executor, http_externo, delegacoes, apos_mudar_agenda=atualizar_agenda_do_linux)
    modelo = ClienteOllama(httpx.AsyncClient(base_url=ajustes.ollama_url), ajustes.modelo)
    agente = Agente(
        modelo, registro, eventos, Auditoria(ajustes.pasta_dados / "auditoria.jsonl"),
        projetos=list(cadastros.projetos),
        cidade=ajustes.cidade,
        sistemas=lambda: [site.nome for site in carregar_sites(ajustes.pasta_config)],
        confirmacoes=Confirmacoes(criar_anunciador(eventos, locutor)),
    )
    transcritor = Transcritor(
        carregar=lambda: carregar_whisper(ajustes.whisper_modelo, ajustes.whisper_dispositivo),
        dicas=[*cadastros.projetos, *VOCABULARIO_FALADO],
    )
    return criar_app(
        agente=agente, eventos=eventos, transcritor=transcritor, locutor=locutor,
        chave=chave, porta=ajustes.porta, pasta_web=PASTA_WEB, pasta_audio=ajustes.pasta_dados / "audio",
        conversa=Auditoria(ajustes.pasta_dados / "conversa.jsonl"),
        tarefas_de_fundo=[manter_agenda_do_linux, manter_sites_da_empresa],
        externas=FerramentasExternas(registro, agente, fora=FORA_DO_CLAUDE),
    )
