"""Sistemas da empresa na internet: apelidos manuais mais o que o Dokploy tem no ar.

`config/sites.json` guarda os apelidos que o usuário escolheu. `config/sites-dokploy.json` é
refeito sozinho a partir dos painéis do Dokploy, separado por painel: um painel fora do ar
mantém o que já tinha. Só leitura no Dokploy; a chave vem da configuração do Claude Code.
"""
import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlencode

import httpx

from clarisse.config import normalizar

log = logging.getLogger(__name__)

# Endereços que não são tela de gente: APIs, servidores MCP, registro de imagens, endereço provisório.
_NAO_E_TELA = {"api", "mcp", "registry", "pgadmin"}


@dataclass
class Site:
    nome: str
    endereco: str
    apelidos: list[str] = field(default_factory=list)


def _sem_barra(endereco: str) -> str:
    return endereco.rstrip("/")


def carregar_sites(pasta_config: Path) -> list[Site]:
    manuais = []
    if (pasta_config / "sites.json").is_file():
        for nome, dados in json.loads((pasta_config / "sites.json").read_text()).items():
            manuais.append(Site(nome, dados["endereco"], dados.get("apelidos", [])))
    conhecidos = {_sem_barra(s.endereco) for s in manuais}
    automaticos = []
    if (pasta_config / "sites-dokploy.json").is_file():
        for por_painel in json.loads((pasta_config / "sites-dokploy.json").read_text()).values():
            for nome, endereco in por_painel.items():
                if _sem_barra(endereco) not in conhecidos:
                    conhecidos.add(_sem_barra(endereco))
                    automaticos.append(Site(nome, endereco))
    return manuais + automaticos


def achar_sites(nome: str, sites: list[Site]) -> list[Site]:
    alvo = normalizar(nome)
    exatos = [s for s in sites if alvo in {normalizar(n) for n in [s.nome, *s.apelidos]}]
    return exatos or [s for s in sites if any(alvo in normalizar(n) for n in [s.nome, *s.apelidos])]


def servidores_do_dokploy(configuracao_do_claude: Path) -> list[tuple[str, str]]:
    servidores = json.loads(configuracao_do_claude.read_text()).get("mcpServers", {})
    pares = []
    for nome, servidor in servidores.items():
        env = servidor.get("env", {})
        if nome.startswith("dokploy") and env.get("DOKPLOY_URL") and env.get("DOKPLOY_API_KEY"):
            pares.append((env["DOKPLOY_URL"].rstrip("/"), env["DOKPLOY_API_KEY"]))
    return pares


def _e_tela(nome_do_app: str, host: str) -> bool:
    palavras = set(re.split(r"[^a-z0-9]+", f"{nome_do_app} {host}".lower()))
    return not (palavras & _NAO_E_TELA or host.endswith("traefik.me"))


async def _telas_do_painel(http, url: str, chave: str) -> dict[str, str]:
    async def get(rota: str, **parametros):
        resposta = await http.get(f"{url}/api/{rota}" + (f"?{urlencode(parametros)}" if parametros else ""),
                                  headers={"x-api-key": chave}, timeout=20)
        resposta.raise_for_status()
        return resposta.json()

    telas = {}
    for projeto in await get("project.all"):
        for ambiente in projeto.get("environments", []):
            for app in ambiente.get("applications", []):
                for dominio in await get("domain.byApplicationId", applicationId=app["applicationId"]):
                    if _e_tela(app["name"], dominio["host"]):
                        esquema = "https" if dominio.get("https") else "http"
                        telas[app["name"]] = f"{esquema}://{dominio['host']}{dominio.get('path') or '/'}"
    return telas


async def atualizar_sites_do_dokploy(http, servidores: list[tuple[str, str]], destino: Path) -> None:
    anterior = json.loads(destino.read_text()) if destino.is_file() else {}
    novo = dict(anterior)
    for url, chave in servidores:
        try:
            novo[url] = await _telas_do_painel(http, url, chave)
        except (httpx.HTTPError, KeyError, ValueError) as erro:
            log.warning("não consegui ler os sites do Dokploy em %s: %r", url, erro)
    destino.write_text(json.dumps(novo, ensure_ascii=False, indent=1))


async def manter_sites_atualizados(http, configuracao_do_claude: Path, destino: Path, intervalo: float = 86400) -> None:
    while True:
        if configuracao_do_claude.is_file():
            await atualizar_sites_do_dokploy(http, servidores_do_dokploy(configuracao_do_claude), destino)
        await asyncio.sleep(intervalo)
