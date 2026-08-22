"""A dica e o `initial_prompt` do whisper alimentado com os nomes dos projetos.

Ela vale 43 pontos de erro de palavra: medida em 21/08/2026, a mesma voz no mesmo
motor deu 52,3% de erro sem ela e 9,2% com ela, e todos os nomes de projeto sairam
certos. Por isso ela nao pode ser uma lista escrita a mao: no dia em que um projeto
novo aparece, o nome dele volta a sair errado.
"""

from clarisse.ouvinte.dica import montar_dica


def test_a_dica_traz_os_nomes_dos_projetos():
    dica = montar_dica(["omni-api", "compliance-app"])

    assert "omni-api" in dica
    assert "compliance-app" in dica


def test_a_dica_anuncia_que_sao_projetos():
    assert montar_dica(["omni-api"]).startswith("Projetos:")


def test_a_dica_termina_com_o_nome_dela():
    assert montar_dica(["omni-api"]).endswith("Clarisse.")


def test_sem_projeto_a_dica_e_so_o_nome_dela():
    assert montar_dica([]) == "Clarisse."


def test_projeto_repetido_entra_uma_vez():
    dica = montar_dica(["omni-api", "compliance-app", "omni-api"])

    assert dica.count("omni-api") == 1


def test_a_ordem_recebida_e_preservada():
    dica = montar_dica(["velocimetro-tokens", "omni-api"])

    assert dica.index("velocimetro-tokens") < dica.index("omni-api")


def test_a_dica_tem_teto_e_os_primeiros_ganham():
    projetos = [f"projeto-{n}" for n in range(15)]

    dica = montar_dica(projetos, limite=12)

    assert "projeto-11" in dica
    assert "projeto-12" not in dica


def test_nome_vazio_e_ignorado():
    dica = montar_dica(["omni-api", "", "   "])

    assert dica == "Projetos: omni-api. Clarisse."
