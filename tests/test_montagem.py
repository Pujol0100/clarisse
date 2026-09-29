import stat

import httpx

from clarisse.config import Ajustes
from clarisse.ferramentas.claude import Delegacoes
from clarisse.montagem import gravar_chave, montar_registro


async def _avisar(titulo, texto):
    pass


def test_registro_tem_todas_as_ferramentas_do_desenho(cadastros, executor, tmp_path):
    ajustes = Ajustes(_env_file=None, pasta_dados=tmp_path)

    registro = montar_registro(ajustes, cadastros, executor, httpx.AsyncClient(), Delegacoes(_avisar))

    assert set(registro.nomes()) == {
        "hora_e_data", "abrir_aplicativo", "fechar_aplicativo", "listar_programas_abertos",
        "abrir_pasta", "abrir_site", "ajustar_volume",
        "abrir_projeto_vscode", "git",
        "abrir_claude_na_tela", "pedir_ao_claude", "consultar_agenda", "criar_compromisso",
        "mandar_para_conversa_do_claude",
        "noticias_do_dia", "previsao_do_tempo",
    }


def test_chave_gravada_so_para_o_dono(tmp_path):
    caminho = tmp_path / "config" / "clarisse" / "chave"

    gravar_chave(caminho, "segredo-da-sessao")
    gravar_chave(caminho, "outra-sessao")

    assert caminho.read_text() == "outra-sessao"
    assert stat.S_IMODE(caminho.stat().st_mode) == 0o600
