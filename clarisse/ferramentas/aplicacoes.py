"""Roda na máquina, em terminais visíveis, qualquer projeto Node que tenha script de desenvolvimento.

Antes de rodar, lê do .env só o endereço e a porta dos bancos (nunca a senha) e compara com a
lista pessoal de bancos conhecidos: banco de produção recusa, mesmo com "sim".
"""
import asyncio
import json
import re
import time
from collections.abc import Awaitable, Callable
from typing import Literal
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx
from dotenv import dotenv_values
from pydantic import Field

from clarisse.config import Cadastros, normalizar
from clarisse.ferramentas.registro import Argumentos, Ferramenta, Risco
from clarisse.sites import Site, achar_sites

_ARQUIVOS_ENV = (".env", ".env.local", ".env.development")
# Só as variáveis que o servidor de desenvolvimento usa por convenção. O .env costuma ter
# também as de scripts (sincronização, migração) apontando para produção, que o dev não lê.
_URLS_DO_BANCO = ("DATABASE_URL", "MONGO_URI", "MONGODB_URI", "MONGO_URL", "REDIS_URL")
_PREFIXOS_HOST_PORTA = ("DB", "POSTGRES", "PG", "MYSQL")
_LOCAIS = {"localhost", "127.0.0.1", "::1"}
_ESPERA_DO_SITE = 120
_ESPERA_COM_INSTALACAO = 600
# Sem isto a janela fecha quando o servidor morre e o erro some junto.
_SEGURAR_A_JANELA = "; echo; echo 'O servidor parou. Veja o erro acima e aperte Enter para fechar.'; read"
_PORTA_NO_SCRIPT = re.compile(r"(?:-p|--port)[ =](\d+)")
_PORTA_PADRAO = {"next": 3000, "vite": 5173, "react-scripts": 3000, "nuxt": 3000}


@dataclass
class Banco:
    nome: str
    producao: bool


_SCRIPTS_DE_DEV = ("dev", "start:dev")


@dataclass
class Parte:
    pasta: Path
    script: str
    porta_web: int | None


def _script_de_dev(pasta: Path) -> tuple[str, str] | None:
    """Nome e conteúdo do script de desenvolvimento do package.json da pasta."""
    try:
        scripts = json.loads((pasta / "package.json").read_text()).get("scripts", {})
    except (OSError, json.JSONDecodeError):
        return None
    return next(((nome, scripts[nome]) for nome in _SCRIPTS_DE_DEV if nome in scripts), None)


def _porta_web(script: str) -> int | None:
    if achada := _PORTA_NO_SCRIPT.search(script):
        return int(achada.group(1))
    return next((porta for nome, porta in _PORTA_PADRAO.items() if nome in script.split()), None)


def partes_do_projeto(projeto: Path) -> list[Parte]:
    pastas = [projeto] if _script_de_dev(projeto) else sorted(p for p in projeto.iterdir() if p.is_dir())
    partes = []
    for pasta in pastas:
        if achado := _script_de_dev(pasta):
            nome, script = achado
            partes.append(Parte(pasta, nome, _porta_web(script)))
    return partes


def bancos_do_env(pasta: Path) -> list[str]:
    valores = {}
    for nome in _ARQUIVOS_ENV:
        if (pasta / nome).is_file():
            valores.update(dotenv_values(pasta / nome))
    enderecos = []
    for chave in _URLS_DO_BANCO:
        url = urlparse(valores.get(chave) or "")
        if url.hostname:
            enderecos.append(f"{url.hostname}:{url.port or ''}".rstrip(":"))
    for prefixo in _PREFIXOS_HOST_PORTA:
        host = valores.get(f"{prefixo}_HOST") or valores.get(f"{prefixo}HOST")
        if host:
            porta = valores.get(f"{prefixo}_PORT") or valores.get(f"{prefixo}PORT") or ""
            enderecos.append(f"{host}:{porta}".rstrip(":"))
    return list(dict.fromkeys(enderecos))


def achar_projetos(nome: str, raizes: list[Path]) -> list[Path]:
    alvo = normalizar(nome)
    candidatas = [p for raiz in raizes if raiz.is_dir() for p in sorted(raiz.iterdir()) if p.is_dir()]
    exatas = [p for p in candidatas if normalizar(p.name) == alvo]
    return exatas or [p for p in candidatas if alvo in normalizar(p.name)]


async def esperar_site(endereco: str, cliente: httpx.AsyncClient, limite: float = 120, intervalo: float = 2) -> bool:
    """Qualquer resposta, até página de erro, quer dizer que o servidor subiu."""
    fim = time.monotonic() + limite
    while time.monotonic() < fim:
        try:
            await cliente.get(endereco, timeout=5)
            return True
        except httpx.TransportError:
            await asyncio.sleep(intervalo)
    return False


def carregar_bancos(caminho: Path) -> dict[str, Banco]:
    if not caminho.is_file():
        return {}
    return {endereco: Banco(**dados) for endereco, dados in json.loads(caminho.read_text()).items()}


class ArgsRodar(Argumentos):
    projeto: str = Field(max_length=80, description="Nome do projeto como o usuário falou")


class ArgsAbrir(Argumentos):
    nome: str = Field(max_length=80, description="O que abrir, como o usuário falou: programa, sistema ou projeto")
    onde: Literal["site", "local"] | None = Field(
        default=None,
        description="Só com a palavra do usuário: 'site' se ele disse site ou internet, 'local' se disse local, "
        "rodar ou na máquina. Se ele só disse 'abre o X', deixe vazio: a Clarisse decide ou pergunta.",
    )


def ferramentas_de_aplicacoes(
    executor,
    delegacoes,
    raizes: list[Path],
    bancos: dict[str, Banco],
    esperar_site: Callable[[str, float], Awaitable[bool]],
    cadastros: Cadastros | None = None,
    sites: Callable[[], list[Site]] = list,
) -> list[Ferramenta]:

    def _plano(args: ArgsRodar) -> tuple[Path | None, list[Parte], list[tuple[Parte, str]], str | None]:
        """Projeto, partes, bancos por parte, e o motivo de não rodar (ou None)."""
        achados = achar_projetos(args.projeto, raizes)
        if not achados:
            return None, [], [], f"Não achei o projeto {args.projeto} nas pastas de programas."
        if len(achados) > 1:
            nomes = ", ".join(p.name for p in achados[:4])
            return None, [], [], f"Achei mais de um projeto com esse nome: {nomes}. Qual deles?"
        projeto = achados[0]
        partes = partes_do_projeto(projeto)
        if not partes:
            return projeto, [], [], f"Não sei rodar o {projeto.name}: ele não tem script de desenvolvimento (npm run dev ou start:dev)."
        usados = [(parte, endereco) for parte in partes for endereco in bancos_do_env(parte.pasta)]
        producao = [bancos[e].nome for _, e in usados if e in bancos and bancos[e].producao]
        if producao:
            return projeto, partes, usados, f"Não rodo o {projeto.name}: o .env aponta para {producao[0]}."
        return projeto, partes, usados, None

    def _instalar(projeto: Path, parte: Parte) -> str | None:
        """Comando de instalação, se a parte ainda não tem as dependências nesta máquina."""
        if (parte.pasta / "node_modules").is_dir() or (projeto / "node_modules").is_dir():
            return None
        return "npm ci" if (parte.pasta / "package-lock.json").is_file() else "npm install"

    def _nome_da_parte(projeto: Path, parte: Parte) -> str:
        return parte.pasta.name if parte.pasta != projeto else projeto.name

    def risco(args: ArgsRodar) -> Risco:
        return Risco.SEGURO if _plano(args)[3] else Risco.CONFIRMAR

    def confirmar(args: ArgsRodar) -> str:
        projeto, partes, usados, _ = _plano(args)
        nomes = [_nome_da_parte(projeto, p) for p in partes]
        instala = any(_instalar(projeto, p) for p in partes)
        frase = ("Vou instalar as dependências e rodar" if instala else "Vou rodar") + f" o {projeto.name}"
        frase += f" ({' e '.join(nomes)})." if len(nomes) > 1 else "."
        if instala:
            frase += " A instalação pode levar alguns minutos."
        for parte, endereco in usados:
            quem = _nome_da_parte(projeto, parte)
            if endereco in bancos:
                frase += f" O {quem} usa o banco {bancos[endereco].nome}."
            elif endereco.partition(":")[0] in _LOCAIS:
                frase += f" O {quem} usa um banco local desta máquina."
            else:
                host, _, porta = endereco.partition(":")
                frase += f" O {quem} usa um banco que eu não conheço, no endereço {host}" + (f" porta {porta}." if porta else ".")
        return frase + " Confirma?"

    async def _quando_subir(projeto: Path, endereco: str, limite: float) -> str:
        if await esperar_site(endereco, limite):
            await executor.iniciar(["xdg-open", endereco])
            return f"O {projeto.name} está no ar. Abri {endereco} no navegador."
        return f"O {projeto.name} não respondeu em {endereco}. Olhe o erro no terminal dele."

    async def rodar_aplicacao(args: ArgsRodar) -> str:
        projeto, partes, _, motivo = _plano(args)
        if motivo:
            return motivo
        instala = False
        for parte in partes:
            # Só nomes fixos no bash: o script vem de _SCRIPTS_DE_DEV, nunca do pedido.
            comando = f"npm run {parte.script}"
            if instalar := _instalar(projeto, parte):
                comando = f"{instalar} && {comando}"
                instala = True
            await executor.iniciar(
                ["ptyxis", "--new-window", "-d", str(parte.pasta), "--", "bash", "-c", comando + _SEGURAR_A_JANELA]
            )
        demora = " Como preciso instalar as dependências antes, pode levar alguns minutos." if instala else ""
        web = next((p for p in partes if p.porta_web), None)
        if web is None:
            return f"Liguei o {projeto.name} em {len(partes)} terminal(is).{demora}"
        endereco = f"http://localhost:{web.porta_web}"
        limite = _ESPERA_COM_INSTALACAO if instala else _ESPERA_DO_SITE
        delegacoes.iniciar(projeto.name, _quando_subir(projeto, endereco, limite))
        return f"Liguei o {projeto.name}.{demora} Aviso quando o site responder."

    def _destino(args: ArgsAbrir) -> tuple[str, object]:
        """O que "abrir" faz: ("app", Aplicativo), ("site", Site), ("local", ArgsRodar) ou ("responder", texto)."""
        chave = cadastros.achar_aplicativo(args.nome) if cadastros and args.onde is None else None
        if chave:
            return "app", cadastros.aplicativos[chave]
        achados = achar_sites(args.nome, sites()) if args.onde != "local" else []
        projetos = achar_projetos(args.nome, raizes) if args.onde != "site" else []
        if achados and projetos and args.onde is None:
            return "responder", (
                f"O {args.nome} tem o site no ar e o projeto nesta máquina. Quer abrir o site ou rodar o projeto local?"
            )
        if len(achados) > 1:
            return "responder", f"Achei mais de um: {', '.join(s.nome for s in achados[:4])}. Qual deles?"
        if achados:
            return "site", achados[0]
        if projetos:
            return "local", ArgsRodar(projeto=args.nome)
        if args.onde == "site":
            return "responder", f"Não conheço o site do {args.nome}."
        return "responder", f"Não conheço {args.nome}: não é programa instalado, sistema da empresa nem projeto da máquina."

    def risco_de_abrir(args: ArgsAbrir) -> Risco:
        tipo, alvo = _destino(args)
        return risco(alvo) if tipo == "local" else Risco.SEGURO

    def confirmar_abrir(args: ArgsAbrir) -> str:
        return confirmar(_destino(args)[1])

    async def abrir(args: ArgsAbrir) -> str:
        tipo, alvo = _destino(args)
        if tipo == "app":
            await executor.iniciar(alvo.abrir)
            return f"Abri o {args.nome}."
        if tipo == "site":
            await executor.iniciar(["xdg-open", alvo.endereco])
            return f"Abri o {alvo.nome} no navegador."
        if tipo == "local":
            return await rodar_aplicacao(alvo)
        return alvo

    return [
        Ferramenta(
            "abrir",
            "Abre o que o usuário pedir pelo nome: programa instalado, sistema da empresa na internet ou projeto da "
            "máquina (que roda local). Use para 'abre o X'. Se o usuário disser 'site' ou 'local', preencha onde.",
            ArgsAbrir, abrir, risco=risco_de_abrir, descrever=confirmar_abrir,
        ),
        Ferramenta(
            "rodar_aplicacao",
            "Roda na máquina um projeto de programação (npm run dev), em terminais visíveis, e abre o site "
            "no navegador quando ele responder. Use para 'roda', 'sobe', 'inicia local' ou 'abre no Chrome' um projeto.",
            ArgsRodar, rodar_aplicacao, risco=risco, descrever=confirmar,
        )
    ]
