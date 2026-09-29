"""Pede ao serviço de agendas do GNOME (evolution-data-server) que busque o que mudou no Outlook.

Sozinho, ele só sincronizou ao entrar na sessão: em 29/09/2026 a cópia local ficou das 07:46
até as 09:46 sem atualizar, embora configurada para cada 30 minutos.
"""
import asyncio
import configparser
import logging
import re
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger(__name__)

PASTA_DAS_FONTES = Path.home() / ".cache" / "evolution" / "sources"
_SERVICO = "org.gnome.evolution.dataserver.Calendar8"
_FABRICA = "/org/gnome/evolution/dataserver/CalendarFactory"
_OBJETO = re.compile(r"'(/org/gnome/evolution/dataserver/[^']+)'")


def agendas_do_microsoft365(pasta: Path = PASTA_DAS_FONTES) -> list[str]:
    uids = []
    for fonte in pasta.glob("**/*.source"):
        leitor = configparser.ConfigParser(interpolation=None, strict=False)
        leitor.read(fonte, encoding="utf-8")
        if leitor.get("Calendar", "BackendName", fallback=None) == "microsoft365":
            uids.append(fonte.stem)
    return uids


def _gdbus(objeto: str, metodo: str, *argumentos: str) -> list[str]:
    return ["gdbus", "call", "--session", "--dest", _SERVICO, "--object-path", objeto, "--method", metodo, *argumentos]


async def atualizar_agendas(executor, uids: list[str]) -> None:
    for uid in uids:
        aberta = await executor.executar(
            _gdbus(_FABRICA, "org.gnome.evolution.dataserver.CalendarFactory.OpenCalendar", uid), timeout=15
        )
        objeto = _OBJETO.search(aberta.saida)
        if aberta.codigo != 0 or not objeto:
            log.warning("não abri a agenda %s do Linux: %s", uid, aberta.erro.strip()[:200])
            continue
        await executor.executar(_gdbus(objeto.group(1), "org.gnome.evolution.dataserver.Calendar.Open"), timeout=15)
        await executor.executar(_gdbus(objeto.group(1), "org.gnome.evolution.dataserver.Calendar.Refresh"), timeout=15)


async def manter_agendas_atualizadas(executor, achar_uids: Callable[[], list[str]], intervalo: float) -> None:
    while True:
        await atualizar_agendas(executor, achar_uids())
        await asyncio.sleep(intervalo)
