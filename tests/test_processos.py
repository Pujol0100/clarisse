import os
import shutil
import sys
import time
from pathlib import Path

import psutil
import pytest

from clarisse.ferramentas import processos
from clarisse.ferramentas.processos import Executor, ambiente_minimo


@pytest.fixture
def executor():
    return Executor()


async def test_executa_lista_de_argumentos_e_devolve_saida(executor):
    resultado = await executor.executar([sys.executable, "-c", "print('olá')"])

    assert resultado.codigo == 0
    assert resultado.saida.strip() == "olá"


async def test_codigo_de_erro_e_devolvido(executor):
    resultado = await executor.executar([sys.executable, "-c", "import sys; sys.exit(3)"])

    assert resultado.codigo == 3


async def test_recusa_string_para_nao_passar_por_shell(executor):
    with pytest.raises(TypeError):
        await executor.executar("dir & del /q *")


async def test_argumento_com_caracteres_de_shell_chega_literal(executor):
    resultado = await executor.executar([sys.executable, "-c", "import sys; print(sys.argv[1])", "a; echo INJETADO"])

    assert resultado.saida.strip() == "a; echo INJETADO"


async def test_estoura_o_tempo_e_mata_o_processo(executor):
    inicio = time.monotonic()
    resultado = await executor.executar([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.5)

    assert resultado.estourou_tempo
    assert time.monotonic() - inicio < 5


async def test_estourar_o_tempo_encerra_tambem_os_filhos(executor, tmp_path):
    arquivo_do_neto = tmp_path / "neto.txt"
    codigo = (
        "import subprocess, sys, time\n"
        "neto = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
        f"open(r'{arquivo_do_neto}', 'w').write(str(neto.pid))\n"
        "time.sleep(30)\n"
    )

    resultado = await executor.executar([sys.executable, "-c", codigo], timeout=3)

    neto = int(arquivo_do_neto.read_text(encoding="utf-8"))
    assert resultado.estourou_tempo
    assert not psutil.pid_exists(neto) or psutil.Process(neto).status() == psutil.STATUS_ZOMBIE


async def test_roda_na_pasta_pedida(executor, tmp_path):
    resultado = await executor.executar([sys.executable, "-c", "import os; print(os.getcwd())"], pasta=tmp_path)

    assert resultado.saida.strip() == str(tmp_path)


async def test_iniciar_solta_o_programa_sem_esperar(executor):
    inicio = time.monotonic()
    await executor.iniciar([sys.executable, "-c", "import time; time.sleep(3)"])

    assert time.monotonic() - inicio < 1


async def test_acha_programa_cmd_pelo_nome(executor, tmp_path, monkeypatch):
    (tmp_path / "eco.cmd").write_text("@echo %1\r\n", encoding="utf-8")
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")

    resultado = await executor.executar(["eco", "oi"])

    assert resultado.saida.strip() == "oi"


async def test_recusa_caractere_do_cmd_em_programa_cmd(executor, tmp_path, monkeypatch):
    (tmp_path / "eco.cmd").write_text("@echo %1\r\n", encoding="utf-8")
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ['PATH']}")

    with pytest.raises(ValueError):
        await executor.executar(["eco", "a&calc"])


def _ping_com_outro_nome(pasta: Path) -> Path:
    copia = pasta / "clarisse-ping.exe"
    shutil.copy(Path(os.environ["SYSTEMROOT"]) / "System32" / "PING.EXE", copia)
    return copia


async def test_encerrar_fecha_o_programa_pelo_nome(executor, tmp_path):
    ping = _ping_com_outro_nome(tmp_path)
    await executor.iniciar([str(ping), "-n", "30", "127.0.0.1"])
    time.sleep(0.5)

    encerrados = await executor.encerrar("CLARISSE-PING.EXE")

    time.sleep(0.5)
    assert encerrados == 1
    assert not any(p.info["name"] == "clarisse-ping.exe" for p in psutil.process_iter(["name"]))


async def test_encerrar_programa_que_nao_esta_aberto_devolve_zero(executor):
    assert await executor.encerrar("programa-que-nao-existe.exe") == 0


async def test_abrir_entrega_ao_programa_padrao_do_windows(executor, monkeypatch):
    abertos = []
    monkeypatch.setattr(processos.os, "startfile", abertos.append)

    await executor.abrir("https://exemplo.com.br")

    assert abertos == ["https://exemplo.com.br"]


def test_ambiente_minimo_tira_segredos(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setenv("DB_PASSWORD", "x")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "x")

    env = ambiente_minimo()

    assert not {"OPENAI_API_KEY", "GITHUB_TOKEN", "DB_PASSWORD", "AWS_SECRET_ACCESS_KEY"} & env.keys()
    assert env["USERPROFILE"] == os.environ["USERPROFILE"]
    assert {"PATH", "SYSTEMROOT", "APPDATA", "LOCALAPPDATA"} <= env.keys()


def test_ambiente_minimo_nao_leva_variavel_do_linux(monkeypatch):
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")
    monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")

    env = ambiente_minimo()

    assert not {"XDG_RUNTIME_DIR", "WAYLAND_DISPLAY"} & env.keys()


async def test_programa_executado_nao_recebe_segredos_do_ambiente(executor, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "segredo-que-nao-pode-vazar")

    resultado = await executor.executar([sys.executable, "-c", "import os; print(sorted(os.environ))"])

    assert "GITHUB_TOKEN" not in resultado.saida
    assert "USERPROFILE" in resultado.saida


async def test_variavel_extra_chega_ao_programa_sem_trazer_segredos(executor, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "segredo-que-nao-pode-vazar")

    resultado = await executor.executar(
        [sys.executable, "-c", "import os; print(os.environ.get('CLARISSE_EXTRA'), 'GITHUB_TOKEN' in os.environ)"],
        ambiente={"CLARISSE_EXTRA": "sim"},
    )

    assert resultado.saida.split() == ["sim", "False"]
