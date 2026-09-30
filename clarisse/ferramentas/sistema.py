"""Ferramentas do computador: hora, aplicativos, pastas, arquivos, sites e volume."""
import asyncio
import os
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import psutil
from pydantic import Field

from clarisse.config import Cadastros, normalizar
from clarisse.figuras import RELOGIO
from clarisse.ferramentas.registro import Argumentos, Ferramenta, Risco

_DIAS = ["segunda-feira", "terça-feira", "quarta-feira", "quinta-feira", "sexta-feira", "sábado", "domingo"]
_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho",
          "agosto", "setembro", "outubro", "novembro", "dezembro"]
_ESQUEMAS_PERIGOSOS = ("javascript:", "data:", "file:", "vbscript:", "mailto:")
_PASTAS_PULADAS = {"node_modules", "__pycache__", "venv", "site-packages", "dist", "build", "graphify-out"}
# Abrir estes pode executar um programa em vez de mostrar o arquivo.
_EXTENSOES_QUE_EXECUTAM = {".sh", ".bash", ".desktop", ".appimage", ".run", ".bin", ".exe", ".jar", ".deb", ".rpm"}


def data_por_extenso(momento: datetime) -> str:
    return (
        f"{_DIAS[momento.weekday()]}, {momento.day} de {_MESES[momento.month - 1]} "
        f"de {momento.year}, {momento:%H:%M}"
    )


def _nomes_dos_processos() -> list[str]:
    return [p.info["name"] or "" for p in psutil.process_iter(["name"])]


def normalizar_site(endereco: str) -> str | None:
    endereco = endereco.strip()
    if not endereco or endereco.startswith("-") or " " in endereco:
        return None
    if "://" in endereco:
        if not endereco.lower().startswith(("http://", "https://")):
            return None
    elif endereco.lower().startswith(_ESQUEMAS_PERIGOSOS):
        return None
    else:
        endereco = "https://" + endereco
    partes = urlparse(endereco)
    host = partes.hostname or ""
    if not re.fullmatch(r"[a-z0-9.-]+", host):
        return None
    if "." not in host and host != "localhost":
        partes = partes._replace(netloc=partes.netloc.replace(host, host + ".com", 1))
    return partes.geturl()


class ArgsNome(Argumentos):
    nome: str = Field(max_length=80, description="Nome do aplicativo como o usuário falou")


class ArgsPasta(Argumentos):
    pasta: str = Field(max_length=300, description="Apelido cadastrado ou caminho dentro da pasta pessoal")


class ArgsArquivo(Argumentos):
    nome: str = Field(max_length=200, description="Nome ou pedaço do nome do arquivo, como o usuário falou")


def _palavras(texto: str) -> list[str]:
    normalizado = normalizar(texto)
    return [p for p in normalizado.split("-") if len(p) >= 3] or [normalizado]


def _procurar_arquivos(nome: str) -> list[Path]:
    palavras = _palavras(nome)
    achados = []
    for raiz, pastas, arquivos in os.walk(Path.home()):
        pastas[:] = [p for p in pastas if not p.startswith(".") and p not in _PASTAS_PULADAS]
        for arquivo in arquivos:
            if not arquivo.startswith(".") and all(p in normalizar(arquivo) for p in palavras):
                achados.append(Path(raiz) / arquivo)
    return sorted(achados, key=lambda c: c.stat().st_mtime, reverse=True)


def _executa_programa(caminho: Path) -> bool:
    return caminho.suffix.lower() in _EXTENSOES_QUE_EXECUTAM or os.access(caminho, os.X_OK)


class ArgsSite(Argumentos):
    endereco: str = Field(max_length=500, description="Endereço ou nome do site")


class ArgsVolume(Argumentos):
    nivel: int = Field(ge=0, le=100, description="Volume de 0 a 100")


def ferramentas_do_sistema(
    cadastros: Cadastros,
    executor,
    agora: Callable[[], datetime] = datetime.now,
    processos: Callable[[], list[str]] = _nomes_dos_processos,
) -> list[Ferramenta]:
    cadastrados = ", ".join(cadastros.aplicativos) or "nenhum"

    async def hora_e_data(args: Argumentos) -> str:
        return f"Hoje é {data_por_extenso(agora())}."

    async def abrir_aplicativo(args: ArgsNome) -> str:
        chave = cadastros.achar_aplicativo(args.nome)
        if chave is None:
            return f"Não conheço o aplicativo {args.nome}. Os cadastrados são: {cadastrados}."
        await executor.iniciar(cadastros.aplicativos[chave].abrir)
        return f"Abri o {chave}."

    async def fechar_aplicativo(args: ArgsNome) -> str:
        chave = cadastros.achar_aplicativo(args.nome)
        if chave is None:
            return f"Não conheço o aplicativo {args.nome}. Os cadastrados são: {cadastrados}."
        # O Linux guarda só 15 caracteres do nome do processo, e o pkill -x compara com eles.
        resultado = await executor.executar(["pkill", "-x", cadastros.aplicativos[chave].processo[:15]])
        if resultado.codigo == 1:
            return f"O {chave} não estava aberto."
        return f"Fechei o {chave}."

    def confirmar_fechamento(args: ArgsNome) -> str:
        chave = cadastros.achar_aplicativo(args.nome) or args.nome
        return f"Vou fechar o {chave}, e o que não estiver salvo nele se perde. Confirma?"

    async def listar_programas_abertos(args: Argumentos) -> str:
        rodando = set(processos())
        abertos = [k for k, app in cadastros.aplicativos.items() if app.processo in rodando]
        if not abertos:
            return "Nenhum dos aplicativos cadastrados está aberto."
        return "Abertos agora: " + ", ".join(abertos) + "."

    async def abrir_pasta(args: ArgsPasta) -> str:
        apelido = cadastros.achar_pasta(args.pasta)
        if apelido:
            destino = cadastros.pastas[apelido]
        else:
            destino = Path(args.pasta).expanduser().resolve()
            if not destino.is_relative_to(Path.home().resolve()):
                return "Não abro pastas fora da sua pasta pessoal."
            if not destino.is_dir():
                return f"Não achei a pasta {args.pasta}."
        await executor.iniciar(["xdg-open", str(destino)])
        return f"Abri a pasta {destino.name}."

    async def abrir_arquivo(args: ArgsArquivo) -> str:
        achados = await asyncio.to_thread(_procurar_arquivos, args.nome)
        abriveis = [c for c in achados if not _executa_programa(c)]
        if not abriveis:
            if achados:
                return f"Não abro {achados[0].name}: esse tipo de arquivo executa um programa."
            return f"Não achei arquivo com o nome {args.nome} na sua pasta pessoal."
        if len(abriveis) > 1:
            casa = Path.home()
            recentes = "; ".join(
                f"{c.name}, " + ("na pasta pessoal" if c.parent == casa else f"em {c.parent.relative_to(casa)}")
                for c in abriveis[:3]
            )
            return (
                f"Achei {len(abriveis)} arquivos com esse nome. Os mais recentes: {recentes}. "
                "Diga um pedaço a mais do nome."
            )
        await executor.iniciar(["xdg-open", str(abriveis[0])])
        return f"Abri {abriveis[0].name}."

    async def abrir_site(args: ArgsSite) -> str:
        url = normalizar_site(args.endereco)
        if url is None:
            return f"Não abro esse endereço: {args.endereco}. Só sites http ou https."
        await executor.iniciar(["xdg-open", url])
        return f"Abri {url}."

    async def ajustar_volume(args: ArgsVolume) -> str:
        resultado = await executor.executar(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{args.nivel / 100:.2f}"])
        if resultado.codigo != 0:
            return f"Não consegui ajustar o volume: {resultado.erro.strip()}"
        return f"Volume em {args.nivel} por cento."

    return [
        Ferramenta("hora_e_data", "Informa a hora e a data atuais.", Argumentos, hora_e_data, figura=RELOGIO),
        Ferramenta("abrir_aplicativo", "Abre um aplicativo instalado.", ArgsNome, abrir_aplicativo),
        Ferramenta(
            "fechar_aplicativo", "Fecha um aplicativo aberto.", ArgsNome, fechar_aplicativo,
            risco=Risco.CONFIRMAR, descrever=confirmar_fechamento,
        ),
        Ferramenta("listar_programas_abertos", "Lista os programas abertos no computador.", Argumentos, listar_programas_abertos),
        Ferramenta("abrir_pasta", "Abre uma pasta no gerenciador de arquivos.", ArgsPasta, abrir_pasta),
        Ferramenta(
            "abrir_arquivo", "Procura um arquivo pelo nome na pasta pessoal e abre no programa padrão.",
            ArgsArquivo, abrir_arquivo,
        ),
        Ferramenta("abrir_site", "Abre um site no navegador.", ArgsSite, abrir_site),
        Ferramenta("ajustar_volume", "Ajusta o volume do sistema.", ArgsVolume, ajustar_volume),
    ]
