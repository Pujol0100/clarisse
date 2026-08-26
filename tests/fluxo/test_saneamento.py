"""O que sai do motor antes de ser colado na janela em foco.

A regra que carrega risco de verdade e a quebra de linha: o texto e colado onde o
cursor estiver, e uma quebra de linha no prompt do Claude Code **envia** a
mensagem. O desenho inteiro do Ouvinte se apoia em digitar para revisao, nunca
enviar — entao quebra de linha nao passa daqui.
"""

from clarisse.ouvinte.motor import sanear


def test_apara_espaco_das_pontas():
    assert sanear('  bom dia  ') == 'bom dia'


def test_colapsa_espaco_repetido():
    assert sanear('bom     dia') == 'bom dia'


def test_troca_quebra_de_linha_por_espaco():
    assert sanear('bom dia\nroda os testes') == 'bom dia roda os testes'


def test_troca_quebra_de_linha_do_windows_por_um_espaco_so():
    assert sanear('bom dia\r\nroda os testes') == 'bom dia roda os testes'


def test_troca_tabulacao_por_espaco():
    assert sanear('bom\tdia') == 'bom dia'


def test_texto_so_com_espaco_vira_vazio():
    assert sanear('   \n\t  ') == ''


def test_texto_vazio_continua_vazio():
    assert sanear('') == ''


def test_preserva_acento_e_pontuacao():
    assert sanear('Clarisse, roda os testes?') == 'Clarisse, roda os testes?'


def test_preserva_o_hifen_do_nome_do_projeto():
    assert sanear('resume o voz-ao-claude') == 'resume o voz-ao-claude'
