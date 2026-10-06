import base64
from pathlib import Path

from clarisse.terminal import em_aspas, terminal


def _comando(argumentos: list[str]) -> str:
    return base64.b64decode(argumentos[argumentos.index("-EncodedCommand") + 1]).decode("utf-16-le")


def test_comando_vai_codificado_para_o_terminal_nao_partir_no_ponto_e_virgula(tmp_path):
    comando = "npm.cmd ci; if ($LASTEXITCODE -eq 0) { npm.cmd run dev }"

    argumentos = terminal(Path(tmp_path), comando)

    assert _comando(argumentos) == comando
    assert not any(";" in a for a in argumentos)


def test_aspas_simples_dentro_do_texto_sao_dobradas():
    assert em_aspas("copo d'água; $env:SEGREDO") == "'copo d''água; $env:SEGREDO'"
