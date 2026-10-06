"""A área de trabalho de verdade: só leitura, nada é ativado nem digitado."""
from clarisse.area_de_trabalho import AreaDeTrabalho


def test_lista_janelas_com_id_titulo_e_programa():
    janelas = AreaDeTrabalho().listar()

    assert all(set(j) == {"id", "titulo", "processo"} and j["titulo"] for j in janelas)


def test_janela_de_sistema_nao_entra_na_lista():
    titulos = [j["titulo"] for j in AreaDeTrabalho().listar()]

    assert "Program Manager" not in titulos
