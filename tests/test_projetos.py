import pytest

from clarisse.ferramentas.processos import Resultado
from clarisse.ferramentas.projetos import ferramentas_de_projetos
from clarisse.ferramentas.registro import Registro, Risco


@pytest.fixture
def ferramentas(cadastros, executor):
    return {f.nome: f for f in ferramentas_de_projetos(cadastros, executor)}


async def test_abre_projeto_cadastrado_no_vscode(ferramentas, cadastros, executor):
    f = ferramentas["abrir_projeto_vscode"]

    resposta = await f.executar(f.argumentos(projeto="Omni API"))

    assert executor.iniciados == [(["code", str(cadastros.projetos["omni-api"])], None)]
    assert "omni-api" in resposta


async def test_projeto_desconhecido_nao_abre_e_lista_os_cadastrados(ferramentas, executor):
    f = ferramentas["abrir_projeto_vscode"]

    resposta = await f.executar(f.argumentos(projeto="sienge"))

    assert executor.iniciados == []
    assert "omni-api" in resposta and "smart-cep" in resposta


def test_esquema_do_projeto_lista_os_cadastrados(ferramentas):
    registro = Registro()
    registro.registrar(ferramentas["abrir_projeto_vscode"])

    [esquema] = registro.esquemas()

    assert esquema["function"]["parameters"]["properties"]["projeto"]["enum"] == ["omni-api", "smart-cep"]


async def test_git_status_e_seguro_e_roda_na_pasta_do_projeto(ferramentas, cadastros, executor):
    f = ferramentas["git"]
    args = f.argumentos(projeto="omni-api", operacao="status")
    executor.respostas.append(Resultado(0, "## main...origin/main\n M app.py\n", ""))

    resposta = await f.executar(args)

    assert f.risco_de(args) is Risco.SEGURO
    assert executor.executados[0][0] == ["git", "-C", str(cadastros.projetos["omni-api"]), "status", "--short", "--branch"]
    assert "M app.py" in resposta


async def test_git_pull_pede_confirmacao_e_so_avanca_sem_mesclar(ferramentas, cadastros, executor):
    f = ferramentas["git"]
    args = f.argumentos(projeto="omni-api", operacao="pull")

    assert f.risco_de(args) is Risco.CONFIRMAR
    assert "omni-api" in f.frase_de_confirmacao(args)
    await f.executar(args)
    assert executor.executados[0][0] == ["git", "-C", str(cadastros.projetos["omni-api"]), "pull", "--ff-only"]


def test_git_recusa_operacao_fora_da_lista(ferramentas):
    with pytest.raises(ValueError):
        ferramentas["git"].argumentos(projeto="omni-api", operacao="push")


async def test_falha_do_git_vira_mensagem(ferramentas, executor):
    f = ferramentas["git"]
    executor.respostas.append(Resultado(128, "", "fatal: not a git repository"))

    resposta = await f.executar(f.argumentos(projeto="omni-api", operacao="log"))

    assert "not a git repository" in resposta
