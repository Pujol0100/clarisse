import pytest

from clarisse.figuras import figura_do_tempo


@pytest.mark.parametrize(
    "codigo,figura",
    [
        (0, "sol"), (1, "sol"),
        (2, "nuvem"), (3, "nuvem"), (45, "nuvem"), (48, "nuvem"),
        (51, "chuva"), (55, "chuva"), (61, "chuva"), (65, "chuva"), (80, "chuva"), (82, "chuva"),
        (95, "trovoada"), (96, "trovoada"), (99, "trovoada"),
        (71, "nuvem"), (1234, "nuvem"),
    ],
)
def test_codigo_do_tempo_vira_figura(codigo, figura):
    assert figura_do_tempo(codigo) == figura


def test_cada_ferramenta_declara_a_figura_do_desenho(cadastros, executor, tmp_path):
    import httpx

    from clarisse.config import Ajustes
    from clarisse.ferramentas.claude import Delegacoes
    from clarisse.montagem import montar_registro

    async def _avisar(titulo, texto):
        pass

    registro = montar_registro(Ajustes(_env_file=None, pasta_dados=tmp_path), cadastros, executor, httpx.AsyncClient(), Delegacoes(_avisar))
    figuras = {nome: registro.obter(nome).figura for nome in registro.nomes()}

    assert figuras["hora_e_data"] == "relogio"
    assert figuras["consultar_agenda"] == figuras["criar_compromisso"] == "calendario"
    assert figuras["noticias_do_dia"] == "jornal"
    assert figuras["git"] == figuras["abrir_projeto_vscode"] == "codigo"
    assert figuras["abrir_claude_na_tela"] == figuras["pedir_ao_claude"] == "codigo"
    assert figuras["mandar_para_conversa_do_claude"] == "mensagem"
    assert figuras["abrir_site"] is None
