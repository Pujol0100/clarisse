"""Descobre as sessoes do Claude Code em disco e resolve nome de projeto.

O nome do projeto sai do campo cwd gravado dentro da transcricao, nao do nome da
pasta. A pasta e higienizada com hifens - C--Users-eu-Documents-api-gestora - e
nao da para separar o hifen do caminho do hifen do nome. O cwd e exato.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

LINHAS_PROCURADAS_PELO_CWD = 50


@dataclass(frozen=True)
class Sessao:
    projeto: str
    caminho: str
    sessao_id: str
    modificado_em: float


def _nome_do_caminho(cwd: str) -> str:
    """O ultimo pedaco do caminho, aceitando os dois separadores.

    PureWindowsPath entende barra normal e barra invertida, entao serve tanto
    para o cwd gravado no Windows quanto para um caminho estilo Unix, sem
    expressao regular e sem escape.
    """
    return PureWindowsPath(cwd).name


def _projeto_do_arquivo(caminho: Path) -> str:
    try:
        with open(caminho, encoding='utf-8', errors='replace') as arquivo:
            for numero, linha in enumerate(arquivo):
                if numero >= LINHAS_PROCURADAS_PELO_CWD:
                    break
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    registro = json.loads(linha)
                except json.JSONDecodeError:
                    continue
                if isinstance(registro, dict) and registro.get('cwd'):
                    return _nome_do_caminho(registro['cwd'])
    except OSError:
        return ''
    return ''


def listar_sessoes(raiz: str) -> list[Sessao]:
    """Devolve as sessoes encontradas, da atividade mais recente para a mais antiga."""
    pasta_raiz = Path(raiz)
    if not pasta_raiz.is_dir():
        return []

    encontradas = []
    for arquivo in pasta_raiz.glob('*/*.jsonl'):
        projeto = _projeto_do_arquivo(arquivo)
        if not projeto:
            continue
        encontradas.append(Sessao(
            projeto=projeto,
            caminho=str(arquivo),
            sessao_id=arquivo.stem,
            modificado_em=arquivo.stat().st_mtime,
        ))

    encontradas.sort(key=lambda s: s.modificado_em, reverse=True)
    return encontradas


def projetos_que_casam(sessoes: list[Sessao], termo: str) -> list[str]:
    """Nomes de projeto que casam com o termo, sem repetir, mais ativo primeiro.

    Nome exato ganha sozinho: pedir omni-api nao pode devolver omni-api-legado
    junto e virar uma pergunta que o usuario ja respondeu.
    """
    procurado = (termo or '').strip().lower()
    if not procurado:
        return []

    # A deduplicacao ignora a caixa porque no Windows omni-api e OMNI-API sao a
    # mesma pasta. Vence a grafia da sessao mais recente, que e a primeira da
    # lista.
    nomes = []
    vistos = set()
    for sessao in sessoes:
        chave = sessao.projeto.lower()
        if chave not in vistos:
            vistos.add(chave)
            nomes.append(sessao.projeto)

    exatos = [n for n in nomes if n.lower() == procurado]
    if exatos:
        return exatos
    return [n for n in nomes if procurado in n.lower()]


def sessao_mais_recente(sessoes: list[Sessao], projeto: str) -> Sessao | None:
    """A sessao daquele projeto que se moveu por ultimo, ou None.

    A comparacao ignora a caixa, pelo mesmo motivo da deduplicacao acima.
    """
    procurado = (projeto or '').lower()
    for sessao in sessoes:
        if sessao.projeto.lower() == procurado:
            return sessao
    return None
