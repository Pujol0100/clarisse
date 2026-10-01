"""Cada ferramenta diz em qual nó da constelação ela acende, e a tela conhece todos esses nós."""
import re
from pathlib import Path

import httpx

from clarisse.cartoes import GRUPOS
from clarisse.config import Ajustes
from clarisse.ferramentas.claude import Delegacoes
from clarisse.montagem import montar_registro

APP = Path(__file__).resolve().parent.parent / "web" / "app.js"


def _registro(cadastros, executor, tmp_path):
    async def _avisar(titulo, texto):
        pass

    return montar_registro(
        Ajustes(_env_file=None, pasta_dados=tmp_path), cadastros, executor, httpx.AsyncClient(), Delegacoes(_avisar),
    )


def test_cada_ferramenta_acende_um_no_que_a_tela_desenha(cadastros, executor, tmp_path):
    registro = _registro(cadastros, executor, tmp_path)
    nos_da_tela = set(re.findall(r'grupo: "([a-z]+)"', APP.read_text(encoding="utf-8")))

    grupos = {nome: registro.obter(nome).grupo for nome in registro.nomes()}

    assert {n: g for n, g in grupos.items() if g not in GRUPOS} == {}
    assert set(grupos.values()) <= nos_da_tela


def test_grupos_das_ferramentas_principais(cadastros, executor, tmp_path):
    registro = _registro(cadastros, executor, tmp_path)
    grupo = lambda nome: registro.obter(nome).grupo  # noqa: E731

    assert grupo("previsao_do_tempo") == "clima"
    assert grupo("noticias_do_dia") == "noticias"
    assert grupo("git") == grupo("abrir_projeto_vscode") == "codigo"
    assert grupo("ler_resposta_do_claude") == grupo("abrir_claude_na_tela") == "claude"
    assert grupo("abrir_site") == "navegador"
    assert grupo("digitar_texto") == grupo("apertar_atalho") == "janelas"
    assert grupo("hora_e_data") == grupo("ajustar_volume") == "sistema"
