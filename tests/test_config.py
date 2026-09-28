import json
from pathlib import Path

from clarisse.config import Ajustes, carregar_cadastros


def test_ajustes_tem_padroes_sem_arquivo_env():
    ajustes = Ajustes(_env_file=None)

    assert ajustes.modelo == "gemma4:e4b-it-qat"
    assert ajustes.porta == 8765
    assert ajustes.ollama_url == "http://127.0.0.1:11434"


def test_ajustes_lidos_do_ambiente(monkeypatch):
    monkeypatch.setenv("CLARISSE_MODELO", "outro-modelo")
    monkeypatch.setenv("CLARISSE_PORTA", "9000")

    ajustes = Ajustes(_env_file=None)

    assert ajustes.modelo == "outro-modelo"
    assert ajustes.porta == 9000


def _grava(pasta: Path, nome: str, conteudo: dict):
    (pasta / nome).write_text(json.dumps(conteudo), encoding="utf-8")


def test_cadastros_lidos_da_pasta_com_til_expandido(tmp_path):
    _grava(tmp_path, "projetos.json", {"omni-api": "~/codigo/omni-api"})
    _grava(tmp_path, "pastas.json", {"downloads": "~/Downloads"})
    _grava(
        tmp_path,
        "aplicativos.json",
        {"chrome": {"abrir": ["google-chrome"], "processo": "chrome", "apelidos": ["navegador"]}},
    )

    cadastros = carregar_cadastros(tmp_path)

    assert cadastros.projetos["omni-api"] == Path.home() / "codigo/omni-api"
    assert cadastros.pastas["downloads"] == Path.home() / "Downloads"
    assert cadastros.aplicativos["chrome"].abrir == ["google-chrome"]


def test_cadastro_ausente_vira_vazio(tmp_path):
    cadastros = carregar_cadastros(tmp_path)

    assert cadastros.projetos == {}
    assert cadastros.aplicativos == {}
    assert cadastros.pastas == {}


def test_acha_aplicativo_pelo_apelido_sem_diferenciar_acento_e_caixa(tmp_path):
    _grava(
        tmp_path,
        "aplicativos.json",
        {"vscode": {"abrir": ["code"], "processo": "code", "apelidos": ["Visual Studio Code", "vs code"]}},
    )
    cadastros = carregar_cadastros(tmp_path)

    assert cadastros.achar_aplicativo("VS Code") == "vscode"
    assert cadastros.achar_aplicativo("visual studio code") == "vscode"
    assert cadastros.achar_aplicativo("vscode") == "vscode"
    assert cadastros.achar_aplicativo("spotify") is None


def test_acha_projeto_com_espaco_no_lugar_do_hifen(tmp_path):
    _grava(tmp_path, "projetos.json", {"omni-api": "/tmp/omni-api"})
    cadastros = carregar_cadastros(tmp_path)

    assert cadastros.achar_projeto("Omni API") == "omni-api"
    assert cadastros.achar_projeto("omni-api") == "omni-api"
    assert cadastros.achar_projeto("sienge") is None


def test_acha_pasta_pelo_apelido_sem_acento(tmp_path):
    _grava(tmp_path, "pastas.json", {"área de trabalho": "~/Área de trabalho"})
    cadastros = carregar_cadastros(tmp_path)

    assert cadastros.achar_pasta("area de trabalho") == "área de trabalho"
    assert cadastros.achar_pasta("musicas") is None
