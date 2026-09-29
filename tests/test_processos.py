import os
import sys
import time

import pytest

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
        await executor.executar("ls; rm -rf ~")


async def test_argumento_com_caracteres_de_shell_chega_literal(executor):
    resultado = await executor.executar([sys.executable, "-c", "import sys; print(sys.argv[1])", "a; echo INJETADO"])

    assert resultado.saida.strip() == "a; echo INJETADO"


async def test_estoura_o_tempo_e_mata_o_processo(executor):
    inicio = time.monotonic()
    resultado = await executor.executar([sys.executable, "-c", "import time; time.sleep(30)"], timeout=0.5)

    assert resultado.estourou_tempo
    assert time.monotonic() - inicio < 5


async def test_roda_na_pasta_pedida(executor, tmp_path):
    resultado = await executor.executar([sys.executable, "-c", "import os; print(os.getcwd())"], pasta=tmp_path)

    assert resultado.saida.strip() == str(tmp_path)


async def test_iniciar_solta_o_programa_sem_esperar(executor):
    inicio = time.monotonic()
    await executor.iniciar([sys.executable, "-c", "import time; time.sleep(3)"])

    assert time.monotonic() - inicio < 1


def test_ambiente_minimo_tira_segredos(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "x")
    monkeypatch.setenv("GITHUB_TOKEN", "x")
    monkeypatch.setenv("DB_PASSWORD", "x")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "x")

    env = ambiente_minimo()

    assert not {"OPENAI_API_KEY", "GITHUB_TOKEN", "DB_PASSWORD", "AWS_SECRET_ACCESS_KEY"} & env.keys()
    assert env["HOME"] == os.environ["HOME"]
    assert "PATH" in env


async def test_programa_executado_nao_recebe_segredos_do_ambiente(executor, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "segredo-que-nao-pode-vazar")

    resultado = await executor.executar([sys.executable, "-c", "import os; print(sorted(os.environ))"])

    assert "GITHUB_TOKEN" not in resultado.saida
    assert "HOME" in resultado.saida
