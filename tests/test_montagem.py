import json
import re
import stat
from pathlib import Path

import httpx

from clarisse import montagem
from clarisse.config import Ajustes
from clarisse.ferramentas.claude import Delegacoes
from clarisse.montagem import gravar_chave, montar_registro


async def _avisar(titulo, texto):
    pass


LOCAIS = {
    "hora_e_data", "abrir_aplicativo", "fechar_aplicativo", "listar_programas_abertos",
    "abrir_pasta", "abrir_arquivo", "abrir_site", "ajustar_volume",
    "abrir_projeto_vscode", "git",
    "abrir_claude_na_tela", "ler_resposta_do_claude",
    "noticias_do_dia", "ler_noticia", "previsao_do_tempo",
    "trazer_para_frente", "digitar_texto", "apertar_atalho", "rodar_aplicacao", "abrir",
    "consultar_agenda", "emails_nao_lidos", "ler_email",
    "prs_abertas", "situacao_da_pr", "situacao_do_sistema",
}
DELEGAM_AO_CLAUDE = {
    "pedir_ao_claude", "criar_compromisso",
    "mandar_para_conversa_do_claude", "fazer_no_navegador", "fazer_em_etapas",
}


def test_com_o_claude_ligado_o_registro_tem_tudo(cadastros, executor, tmp_path):
    ajustes = Ajustes(_env_file=None, pasta_dados=tmp_path, usar_claude=True)

    registro = montar_registro(ajustes, cadastros, executor, httpx.AsyncClient(), Delegacoes(_avisar))

    assert set(registro.nomes()) == LOCAIS | DELEGAM_AO_CLAUDE


def test_sem_o_claude_fica_so_o_que_roda_aqui_e_continua_abrindo_e_lendo_o_claude(cadastros, executor, tmp_path):
    ajustes = Ajustes(_env_file=None, pasta_dados=tmp_path)

    registro = montar_registro(ajustes, cadastros, executor, httpx.AsyncClient(), Delegacoes(_avisar))

    assert not ajustes.usar_claude
    assert set(registro.nomes()) == LOCAIS


def test_chave_gravada_so_para_o_dono(tmp_path):
    caminho = tmp_path / "config" / "clarisse" / "chave"

    gravar_chave(caminho, "segredo-da-sessao")
    gravar_chave(caminho, "outra-sessao")

    assert caminho.read_text() == "outra-sessao"
    assert stat.S_IMODE(caminho.stat().st_mode) == 0o600


def test_playwright_do_navegador_tem_versao_fixa(tmp_path, monkeypatch):
    monkeypatch.setattr(montagem, "PASTA_NEUTRA_DO_CLAUDE", tmp_path)

    config = json.loads(montagem._config_do_navegador().read_text())

    pacote = config["mcpServers"]["playwright"]["args"][-1]
    assert re.fullmatch(r"@playwright/mcp@\d+\.\d+\.\d+", pacote)


def test_claude_abre_o_servidor_mcp_da_clarisse_com_o_python_do_projeto(tmp_path, monkeypatch):
    import sys

    monkeypatch.setattr(montagem, "PASTA_NEUTRA_DO_CLAUDE", tmp_path)

    servidor = json.loads(montagem._config_da_clarisse(porta=8765).read_text())["mcpServers"]["clarisse"]

    assert servidor["command"] == sys.executable
    assert servidor["args"] == ["-m", "clarisse.mcp_servidor"]
    assert servidor["env"]["CLARISSE_PORTA"] == "8765"
    assert (Path(servidor["env"]["PYTHONPATH"]) / "clarisse" / "mcp_servidor.py").is_file()


def test_notas_do_obsidian_so_entram_com_o_cofre_configurado(cadastros, executor, tmp_path):
    cofre = tmp_path / "cofre"
    cofre.mkdir()

    sem = montar_registro(Ajustes(_env_file=None, pasta_dados=tmp_path), cadastros, executor, httpx.AsyncClient(), Delegacoes(_avisar))
    com = montar_registro(
        Ajustes(_env_file=None, pasta_dados=tmp_path, cofre_de_notas=cofre), cadastros, executor, httpx.AsyncClient(), Delegacoes(_avisar),
    )

    assert set(com.nomes()) - set(sem.nomes()) == {"buscar_nas_notas", "ler_nota"}
