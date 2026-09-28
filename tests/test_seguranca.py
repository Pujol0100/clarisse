import pytest
from pydantic import Field

from clarisse.ferramentas.registro import Argumentos, Ferramenta, Registro, Risco
from clarisse.seguranca import avaliar, confirma, pede_para_parar


class ArgsGit(Argumentos):
    projeto: str
    operacao: str = Field(pattern="^(status|log|pull)$")


async def _nada(args):
    return ""


@pytest.fixture
def registro():
    r = Registro()
    r.registrar(
        Ferramenta(
            nome="git",
            descricao="git",
            argumentos=ArgsGit,
            executar=_nada,
            risco=lambda a: Risco.CONFIRMAR if a.operacao == "pull" else Risco.SEGURO,
        )
    )
    r.registrar(Ferramenta(nome="formatar", descricao="x", argumentos=Argumentos, executar=_nada, risco=Risco.BLOQUEADO))
    return r


def test_ferramenta_segura_e_executada_com_argumentos_validados(registro):
    decisao = avaliar(registro, "git", {"projeto": "omni-api", "operacao": "status"})

    assert decisao.acao == "executar"
    assert decisao.args.projeto == "omni-api"


def test_ferramenta_de_risco_pede_confirmacao(registro):
    decisao = avaliar(registro, "git", {"projeto": "omni-api", "operacao": "pull"})

    assert decisao.acao == "confirmar"


def test_ferramenta_bloqueada_e_recusada(registro):
    assert avaliar(registro, "formatar", {}).acao == "recusar"


def test_ferramenta_inexistente_e_recusada(registro):
    decisao = avaliar(registro, "rm_rf", {})

    assert decisao.acao == "recusar"
    assert "rm_rf" in decisao.motivo


def test_argumento_invalido_e_recusado_com_motivo(registro):
    decisao = avaliar(registro, "git", {"projeto": "omni-api", "operacao": "push --force"})

    assert decisao.acao == "recusar"
    assert "operacao" in decisao.motivo


def test_argumento_a_mais_e_recusado(registro):
    decisao = avaliar(registro, "git", {"projeto": "x", "operacao": "status", "shell": "rm -rf ~"})

    assert decisao.acao == "recusar"


@pytest.mark.parametrize("fala", ["sim", "Sim, pode.", "pode executar", "confirmo", "pode sim, Clarisse", "manda ver"])
def test_reconhece_confirmacao(fala):
    assert confirma(fala)


@pytest.mark.parametrize("fala", ["não", "sim, não, espera", "simples", "abre o chrome", "", "cancela"])
def test_nao_confunde_outra_fala_com_confirmacao(fala):
    assert not confirma(fala)


@pytest.mark.parametrize("fala", ["para", "Para, Clarisse!", "cancela", "chega", "silêncio", "para de falar", "Clarisse, cancela isso"])
def test_reconhece_pedido_para_parar(fala):
    assert pede_para_parar(fala)


@pytest.mark.parametrize("fala", ["abre o chrome para mim", "que horas são", "prepara o relatório de vendas do mês", ""])
def test_nao_confunde_pedido_com_parada(fala):
    assert not pede_para_parar(fala)
