import base64
from pathlib import Path

from clarisse.terminal import em_aspas, terminal


def _comando(argumentos: list[str]) -> str:
    return base64.b64decode(argumentos[argumentos.index("-EncodedCommand") + 1]).decode("utf-16-le")


def test_abre_janela_nova_do_windows_terminal_na_pasta(tmp_path):
    argumentos = terminal(tmp_path, "npm.cmd run dev")

    assert argumentos[:5] == ["wt.exe", "-w", "new", "-d", str(tmp_path)]


def test_powershell_fica_aberto_depois_do_comando(tmp_path):
    argumentos = terminal(tmp_path, "npm.cmd run dev")

    assert argumentos[5:7] == ["powershell.exe", "-NoExit"]


def test_comando_vai_codificado_para_o_terminal_nao_partir_no_ponto_e_virgula(tmp_path):
    comando = "npm.cmd ci; if ($LASTEXITCODE -eq 0) { npm.cmd run dev }"

    argumentos = terminal(Path(tmp_path), comando)

    assert _comando(argumentos) == comando
    assert not any(";" in a for a in argumentos)


def test_texto_entre_aspas_simples_do_powershell():
    assert em_aspas("conserta o login") == "'conserta o login'"


def test_aspas_simples_dentro_do_texto_sao_dobradas():
    assert em_aspas("copo d'água; $env:SEGREDO") == "'copo d''água; $env:SEGREDO'"
