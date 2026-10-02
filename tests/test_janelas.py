import json

import pytest

from clarisse.config import Aplicativo
from clarisse.ferramentas.janelas import ferramentas_de_janelas, ler_janelas
from clarisse.ferramentas.processos import Resultado
from clarisse.ferramentas.registro import Risco

JANELAS = [
    {"wm_class": "chrome-hnpfjngllnobngcgfapefoaidbinmjnm-Default", "title": "WhatsApp Web", "id": 101, "focus": False},
    {"wm_class": "com.microsoft.VSCode", "title": "app.py - omni-api - Visual Studio Code", "id": 102, "focus": False},
    {"wm_class": "com.microsoft.VSCode", "title": "Máquina trava… - clarisse - Visual Studio Code", "id": 103, "focus": False},
    {"wm_class": "org.gnome.Ptyxis", "title": "vinicao@N000275: ~", "id": 104, "focus": True},
    {"wm_class": "google-chrome", "title": "Dokploy - Google Chrome", "id": 105, "focus": False},
    {"wm_class": "org.gnome.Calculator", "title": "Calculadora", "id": 106, "focus": False},
]


def _lista(janelas=JANELAS):
    return Resultado(0, f"({json.dumps(janelas, ensure_ascii=False)!r},)\n", "")


@pytest.fixture
def ferramentas(cadastros, executor):
    return {f.nome: f for f in ferramentas_de_janelas(cadastros, executor, espera=0)}


def _ativou(executor):
    return [a[-1] for a, _ in executor.executados if "org.gnome.Shell.Extensions.Windows.Activate" in a]


def _digitou(executor):
    return [a for a, _ in executor.executados if a[:2] == ["ydotool", "type"]]


def _teclas(executor):
    return [a for a, _ in executor.executados if a[:2] == ["ydotool", "key"]]


def test_le_a_lista_de_janelas_como_o_gdbus_devolve():
    assert [j["id"] for j in ler_janelas(_lista().saida)] == [101, 102, 103, 104, 105, 106]
    assert ler_janelas(_lista().saida)[2]["title"].startswith("Máquina trava")


async def test_traz_o_aplicativo_para_a_frente_pelo_apelido(ferramentas, executor):
    executor.respostas += [_lista(), Resultado(0, "()", "")]
    f = ferramentas["trazer_para_frente"]

    resposta = await f.executar(f.argumentos(aplicativo="vs code"))

    assert _ativou(executor) == ["102"]
    assert "Visual Studio Code" in resposta


async def test_titulo_escolhe_entre_varias_janelas_do_mesmo_aplicativo(ferramentas, executor):
    executor.respostas += [_lista(), Resultado(0, "()", "")]
    f = ferramentas["trazer_para_frente"]

    await f.executar(f.argumentos(aplicativo="vs code", titulo="clarisse"))

    assert _ativou(executor) == ["103"]


async def test_acha_janela_que_nao_esta_no_cadastro_pelo_titulo(ferramentas, executor):
    executor.respostas += [_lista(), Resultado(0, "()", "")]
    f = ferramentas["trazer_para_frente"]

    await f.executar(f.argumentos(aplicativo="whatsapp"))

    assert _ativou(executor) == ["101"]


async def test_app_do_chrome_nao_passa_na_frente_do_proprio_chrome(ferramentas, executor):
    executor.respostas += [_lista(), Resultado(0, "()", "")]
    f = ferramentas["trazer_para_frente"]

    await f.executar(f.argumentos(aplicativo="navegador"))

    assert _ativou(executor) == ["105"]



async def test_acha_pelo_titulo_o_aplicativo_cadastrado_cuja_janela_tem_outro_nome(ferramentas, executor, cadastros):
    cadastros.aplicativos["calculadora"] = Aplicativo(abrir=["gnome-calculator"], processo="gnome-calculator", apelidos=[])
    executor.respostas += [_lista(), Resultado(0, "()", "")]
    f = ferramentas["trazer_para_frente"]

    await f.executar(f.argumentos(aplicativo="calculadora"))

    assert _ativou(executor) == ["106"]

async def test_janela_que_nao_existe_nao_ativa_nada_e_diz_quais_estao_abertas(ferramentas, executor):
    executor.respostas += [_lista()]
    f = ferramentas["trazer_para_frente"]

    resposta = await f.executar(f.argumentos(aplicativo="spotify"))

    assert _ativou(executor) == []
    assert "WhatsApp Web" in resposta


async def test_sem_a_extensao_explica_o_que_falta(ferramentas, executor):
    executor.respostas += [Resultado(1, "", "GDBus.Error:org.freedesktop.DBus.Error.UnknownMethod")]
    f = ferramentas["trazer_para_frente"]

    resposta = await f.executar(f.argumentos(aplicativo="vs code"))

    assert "window calls" in resposta.lower()


async def test_digitar_pede_confirmacao_com_o_texto_e_o_destino(ferramentas):
    f = ferramentas["digitar_texto"]
    args = f.argumentos(aplicativo="vs code", texto="obrigado")

    assert f.risco_de(args) is Risco.CONFIRMAR
    frase = f.frase_de_confirmacao(args)
    assert "obrigado" in frase and "vs code" in frase


async def test_digitar_traz_a_janela_para_a_frente_e_cola_o_texto(ferramentas, executor):
    executor.respostas += [_lista(), Resultado(0, "()", ""), Resultado(0, "", "")]
    f = ferramentas["digitar_texto"]

    resposta = await f.executar(f.argumentos(aplicativo="vs code", texto="não; rm -rf ~", titulo="clarisse"))

    assert _ativou(executor) == ["103"]
    assert executor.iniciados == [(["wl-copy", "--", "não; rm -rf ~"], None)]
    assert _teclas(executor) == [["ydotool", "key", "29:1", "47:1", "47:0", "29:0"]]
    assert "clarisse" in resposta


async def test_no_terminal_cola_com_ctrl_shift_v(ferramentas, executor):
    executor.respostas += [_lista(), Resultado(0, "()", ""), Resultado(0, "", "")]
    f = ferramentas["digitar_texto"]

    await f.executar(f.argumentos(aplicativo="ptyxis", texto="ls"))

    assert _teclas(executor) == [["ydotool", "key", "29:1", "42:1", "47:1", "47:0", "42:0", "29:0"]]


async def test_nao_digita_se_nao_achou_a_janela(ferramentas, executor):
    executor.respostas += [_lista()]
    f = ferramentas["digitar_texto"]

    await f.executar(f.argumentos(aplicativo="spotify", texto="oi"))

    assert executor.iniciados == []
    assert _teclas(executor) == []


async def test_teclado_virtual_desligado_vira_mensagem(ferramentas, executor):
    executor.respostas += [
        _lista(), Resultado(0, "()", ""),
        # Com o serviço parado o ydotool 1.0.4 sai com 2 e escreve o aviso na saída normal.
        Resultado(2, "failed to connect socket `/run/user/1000/.ydotool_socket': Connection refused\n", ""),
    ]
    f = ferramentas["digitar_texto"]

    resposta = await f.executar(f.argumentos(aplicativo="vs code", texto="oi"))

    assert "teclado virtual" in resposta.lower()


async def test_atalho_de_salvar_aperta_ctrl_s_na_janela_pedida(ferramentas, executor):
    executor.respostas += [_lista(), Resultado(0, "()", ""), Resultado(0, "", "")]
    f = ferramentas["apertar_atalho"]

    await f.executar(f.argumentos(atalho="salvar", aplicativo="vs code"))

    assert _ativou(executor) == ["102"]
    assert _teclas(executor) == [["ydotool", "key", "29:1", "31:1", "31:0", "29:0"]]



async def test_atalho_so_com_titulo_vai_para_a_janela_do_titulo(ferramentas, executor):
    executor.respostas += [_lista(), Resultado(0, "()", ""), Resultado(0, "", "")]
    f = ferramentas["apertar_atalho"]

    await f.executar(f.argumentos(atalho="salvar", titulo="clarisse"))

    assert _ativou(executor) == ["103"]

async def test_atalho_sem_aplicativo_vai_para_a_janela_da_frente(ferramentas, executor):
    f = ferramentas["apertar_atalho"]

    await f.executar(f.argumentos(atalho="enter"))

    assert _ativou(executor) == []
    assert _teclas(executor) == [["ydotool", "key", "28:1", "28:0"]]


@pytest.mark.parametrize("atalho,risco", [("fechar_aba", Risco.CONFIRMAR), ("fechar_janela", Risco.CONFIRMAR), ("salvar", Risco.SEGURO)])
def test_so_atalhos_que_perdem_coisa_pedem_confirmacao(ferramentas, atalho, risco):
    f = ferramentas["apertar_atalho"]

    assert f.risco_de(f.argumentos(atalho=atalho)) is risco


def test_atalho_fora_da_lista_e_invalido(ferramentas):
    with pytest.raises(ValueError):
        ferramentas["apertar_atalho"].argumentos(atalho="ctrl+alt+del")


def test_frase_do_atalho_so_avisa_perda_quando_fecha(ferramentas):
    f = ferramentas["apertar_atalho"]

    assert "se perde" not in f.frase_de_confirmacao(f.argumentos(atalho="enter", aplicativo="chrome"))
    assert "se perde" in f.frase_de_confirmacao(f.argumentos(atalho="fechar_aba", aplicativo="chrome"))
