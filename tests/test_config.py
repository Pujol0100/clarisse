import json
import os
from pathlib import Path

from clarisse.config import Ajustes, carregar_cadastros


def _grava(pasta: Path, nome: str, conteudo: dict):
    (pasta / nome).write_text(json.dumps(conteudo), encoding="utf-8")


def test_cadastros_lidos_da_pasta_com_til_expandido(tmp_path):
    _grava(tmp_path, "projetos.json", {"omni-api": "~/codigo/omni-api"})
    _grava(tmp_path, "pastas.json", {"downloads": "~/Downloads"})
    _grava(
        tmp_path,
        "aplicativos.json",
        {"chrome": {"abrir": ["chrome.exe"], "processo": "chrome.exe", "apelidos": ["navegador"]}},
    )

    cadastros = carregar_cadastros(tmp_path)

    assert cadastros.projetos["omni-api"] == Path.home() / "codigo/omni-api"
    assert cadastros.pastas["downloads"] == Path.home() / "Downloads"
    assert cadastros.aplicativos["chrome"].abrir == ["chrome.exe"]


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
    _grava(tmp_path, "projetos.json", {"omni-api": "C:/codigo/omni-api"})
    cadastros = carregar_cadastros(tmp_path)

    assert cadastros.achar_projeto("Omni API") == "omni-api"
    assert cadastros.achar_projeto("omni-api") == "omni-api"
    assert cadastros.achar_projeto("sienge") is None


def test_acha_pasta_pelo_apelido_sem_acento(tmp_path):
    _grava(tmp_path, "pastas.json", {"área de trabalho": "~/Área de trabalho"})
    cadastros = carregar_cadastros(tmp_path)

    assert cadastros.achar_pasta("area de trabalho") == "área de trabalho"
    assert cadastros.achar_pasta("musicas") is None


def test_ollama_padrao_e_o_do_instalador_do_windows():
    binario = Path(Ajustes(_env_file=None).ollama_bin).expanduser()

    assert binario == Path(os.environ["LOCALAPPDATA"]) / "Programs" / "Ollama" / "ollama.exe"


EXEMPLOS = Path(__file__).resolve().parent.parent / "config"


def _exemplo(nome: str) -> dict:
    return json.loads((EXEMPLOS / f"{nome}.exemplo.json").read_text(encoding="utf-8"))


def test_aplicativos_de_exemplo_sao_programas_do_windows():
    aplicativos = _exemplo("aplicativos")

    assert all(app["processo"].lower().endswith(".exe") for app in aplicativos.values())
    assert all(Path(app["abrir"][0]).is_absolute() or app["abrir"][0].lower().endswith(".exe") or app["abrir"][0] == "code"
               for app in aplicativos.values())


def test_explorador_nao_e_aplicativo_porque_fechar_derrubaria_a_barra_de_tarefas():
    assert all(app["processo"].lower() != "explorer.exe" for app in _exemplo("aplicativos").values())


def test_pastas_e_projetos_de_exemplo_usam_os_nomes_do_windows():
    caminhos = [*_exemplo("pastas").values(), *_exemplo("projetos").values()]

    assert all(c.startswith(("~/Downloads", "~/Documents", "~/Desktop")) for c in caminhos)
