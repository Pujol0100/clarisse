import pytest

from clarisse.config import Aplicativo
from clarisse.ferramentas.janelas import ferramentas_de_janelas
from clarisse.ferramentas.registro import Risco

JANELAS = [
    {"id": 101, "titulo": "WhatsApp", "processo": "chrome.exe"},
    {"id": 102, "titulo": "app.py - omni-api - Visual Studio Code", "processo": "Code.exe"},
    {"id": 103, "titulo": "Máquina trava… - clarisse - Visual Studio Code", "processo": "Code.exe"},
    {"id": 104, "titulo": "Windows PowerShell", "processo": "WindowsTerminal.exe"},
    {"id": 105, "titulo": "Dokploy - Google Chrome", "processo": "chrome.exe"},
    {"id": 106, "titulo": "Calculadora", "processo": "CalculatorApp.exe"},
]


@pytest.fixture
def ferramentas(cadastros, area):
    area.janelas = JANELAS
    return {f.nome: f for f in ferramentas_de_janelas(cadastros, area, espera=0)}


async def test_traz_o_aplicativo_para_a_frente_pelo_apelido(ferramentas, area):
    f = ferramentas["trazer_para_frente"]

    resposta = await f.executar(f.argumentos(aplicativo="vs code"))

    assert area.ativadas == [102]
    assert "Visual Studio Code" in resposta


async def test_titulo_escolhe_entre_varias_janelas_do_mesmo_aplicativo(ferramentas, area):
    f = ferramentas["trazer_para_frente"]

    await f.executar(f.argumentos(aplicativo="vs code", titulo="clarisse"))

    assert area.ativadas == [103]


async def test_acha_janela_que_nao_esta_no_cadastro_pelo_titulo(ferramentas, area):
    f = ferramentas["trazer_para_frente"]

    await f.executar(f.argumentos(aplicativo="whatsapp"))

    assert area.ativadas == [101]


async def test_app_do_chrome_nao_passa_na_frente_do_proprio_chrome(ferramentas, area):
    f = ferramentas["trazer_para_frente"]

    await f.executar(f.argumentos(aplicativo="navegador"))

    assert area.ativadas == [105]


async def test_acha_pelo_processo_o_aplicativo_cadastrado_cuja_janela_tem_outro_nome(ferramentas, area, cadastros):
    cadastros.aplicativos["calc"] = Aplicativo(abrir=["calc.exe"], processo="CalculatorApp.exe", apelidos=[])
    f = ferramentas["trazer_para_frente"]

    await f.executar(f.argumentos(aplicativo="calc"))

    assert area.ativadas == [106]


async def test_janela_que_nao_existe_nao_ativa_nada_e_diz_quais_estao_abertas(ferramentas, area):
    f = ferramentas["trazer_para_frente"]

    resposta = await f.executar(f.argumentos(aplicativo="spotify"))

    assert area.ativadas == []
    assert "WhatsApp" in resposta


async def test_digitar_pede_confirmacao_com_o_texto_e_o_destino(ferramentas):
    f = ferramentas["digitar_texto"]
    args = f.argumentos(aplicativo="vs code", texto="obrigado")

    assert f.risco_de(args) is Risco.CONFIRMAR
    frase = f.frase_de_confirmacao(args)
    assert "obrigado" in frase and "vs code" in frase


async def test_digitar_traz_a_janela_para_a_frente_e_cola_o_texto(ferramentas, area):
    f = ferramentas["digitar_texto"]

    resposta = await f.executar(f.argumentos(aplicativo="vs code", texto="não; del /q *", titulo="clarisse"))

    assert area.ativadas == [103]
    assert area.coladas == ["não; del /q *"]
    assert area.apertadas == ["^v"]
    assert "clarisse" in resposta


async def test_no_terminal_tambem_cola_com_ctrl_v(ferramentas, area):
    f = ferramentas["digitar_texto"]

    await f.executar(f.argumentos(aplicativo="powershell", texto="dir"))

    assert area.ativadas == [104]
    assert area.apertadas == ["^v"]


async def test_nao_digita_se_nao_achou_a_janela(ferramentas, area):
    f = ferramentas["digitar_texto"]

    await f.executar(f.argumentos(aplicativo="spotify", texto="oi"))

    assert area.coladas == []
    assert area.apertadas == []


async def test_atalho_de_salvar_aperta_ctrl_s_na_janela_pedida(ferramentas, area):
    f = ferramentas["apertar_atalho"]

    await f.executar(f.argumentos(atalho="salvar", aplicativo="vs code"))

    assert area.ativadas == [102]
    assert area.apertadas == ["^s"]


async def test_atalho_so_com_titulo_vai_para_a_janela_do_titulo(ferramentas, area):
    f = ferramentas["apertar_atalho"]

    await f.executar(f.argumentos(atalho="salvar", titulo="clarisse"))

    assert area.ativadas == [103]


async def test_atalho_sem_aplicativo_vai_para_a_janela_da_frente(ferramentas, area):
    f = ferramentas["apertar_atalho"]

    await f.executar(f.argumentos(atalho="enter"))

    assert area.ativadas == []
    assert area.apertadas == ["{ENTER}"]


async def test_fechar_janela_aperta_alt_f4(ferramentas, area):
    f = ferramentas["apertar_atalho"]

    await f.executar(f.argumentos(atalho="fechar_janela"))

    assert area.apertadas == ["%{F4}"]


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
