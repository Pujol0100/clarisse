from datetime import datetime
from pathlib import Path

import pytest

from clarisse.config import Aplicativo
from clarisse.ferramentas.processos import Resultado
from clarisse.ferramentas.registro import Risco
from clarisse.ferramentas.sistema import ferramentas_do_sistema


@pytest.fixture
def ferramentas(cadastros, executor):
    agora = lambda: datetime(2026, 9, 28, 14, 5)
    return {f.nome: f for f in ferramentas_do_sistema(cadastros, executor, agora=agora)}


async def _rodar(ferramentas, ferramenta, **args):
    f = ferramentas[ferramenta]
    return await f.executar(f.argumentos(**args))


async def test_hora_e_data_em_portugues(ferramentas):
    resposta = await _rodar(ferramentas, "hora_e_data")

    assert resposta == "Hoje é segunda-feira, 28 de setembro de 2026, 14:05."


async def test_abre_aplicativo_cadastrado_pelo_apelido(ferramentas, executor):
    resposta = await _rodar(ferramentas, "abrir_aplicativo", nome="VS Code")

    assert executor.iniciados == [(["code"], None)]
    assert "vscode" in resposta


async def test_nao_abre_aplicativo_fora_do_cadastro(ferramentas, executor):
    resposta = await _rodar(ferramentas, "abrir_aplicativo", nome="spotify")

    assert executor.iniciados == []
    assert "não conheço" in resposta.lower()
    assert "vscode" in resposta


async def test_fechar_aplicativo_pede_confirmacao_e_fecha_pelo_processo(ferramentas, executor):
    fechar = ferramentas["fechar_aplicativo"]
    args = fechar.argumentos(nome="navegador")

    assert fechar.risco_de(args) is Risco.CONFIRMAR
    assert "chrome" in fechar.frase_de_confirmacao(args)
    await fechar.executar(args)
    assert executor.executados == [(["pkill", "-x", "chrome"], None)]



async def test_fechar_aplicativo_de_nome_longo_usa_os_15_caracteres_que_o_linux_guarda(ferramentas, executor, cadastros):
    cadastros.aplicativos["calculadora"] = Aplicativo(abrir=["gnome-calculator"], processo="gnome-calculator", apelidos=[])

    await _rodar(ferramentas, "fechar_aplicativo", nome="calculadora")

    assert executor.executados == [(["pkill", "-x", "gnome-calculato"], None)]

async def test_abre_pasta_pelo_apelido(ferramentas, executor):
    await _rodar(ferramentas, "abrir_pasta", pasta="Downloads")

    assert executor.iniciados == [(["xdg-open", str(Path.home() / "Downloads")], None)]


async def test_abre_pasta_dentro_da_home_pelo_caminho(ferramentas, executor, tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "Projetos").mkdir()

    await _rodar(ferramentas, "abrir_pasta", pasta="~/Projetos")

    assert executor.iniciados == [(["xdg-open", str(tmp_path / "Projetos")], None)]


@pytest.mark.parametrize("pasta", ["/etc", "~/../../etc", "/root"])
async def test_recusa_pasta_fora_da_home(ferramentas, executor, pasta):
    resposta = await _rodar(ferramentas, "abrir_pasta", pasta=pasta)

    assert executor.iniciados == []
    assert "não" in resposta.lower()


@pytest.mark.parametrize(
    "endereco,esperado",
    [
        ("github", "https://github.com"),
        ("github.com", "https://github.com"),
        ("https://g1.globo.com/economia", "https://g1.globo.com/economia"),
        ("http://localhost:3000", "http://localhost:3000"),
    ],
)
async def test_abre_site_com_endereco_completado(ferramentas, executor, endereco, esperado):
    await _rodar(ferramentas, "abrir_site", endereco=endereco)

    assert executor.iniciados == [(["xdg-open", esperado], None)]


@pytest.mark.parametrize("endereco", ["file:///etc/passwd", "javascript:alert(1)", "ftp://x.com", "--help"])
async def test_recusa_site_que_nao_e_http(ferramentas, executor, endereco):
    await _rodar(ferramentas, "abrir_site", endereco=endereco)

    assert executor.iniciados == []


async def test_ajusta_volume_pelo_wpctl(ferramentas, executor):
    await _rodar(ferramentas, "ajustar_volume", nivel=30)

    assert executor.executados == [(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "0.30"], None)]


def test_volume_fora_da_faixa_e_invalido(ferramentas):
    with pytest.raises(ValueError):
        ferramentas["ajustar_volume"].argumentos(nivel=150)


async def test_lista_programas_cadastrados_que_estao_abertos(cadastros, executor):
    processos = lambda: ["chrome", "chrome", "bash", "code"]
    [lista] = [f for f in ferramentas_do_sistema(cadastros, executor, processos=processos) if f.nome == "listar_programas_abertos"]

    resposta = await lista.executar(lista.argumentos())

    assert "vscode" in resposta and "chrome" in resposta
    assert "bash" not in resposta


async def test_falha_do_programa_vira_mensagem(ferramentas, executor):
    executor.respostas.append(Resultado(1, "", "wpctl: not found"))

    resposta = await _rodar(ferramentas, "ajustar_volume", nivel=10)

    assert "não consegui" in resposta.lower()
