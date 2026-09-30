import json

import pytest

from clarisse.ferramentas.aplicacoes import Banco, ferramentas_de_aplicacoes
from clarisse.ferramentas.claude import Delegacoes
from clarisse.ferramentas.registro import Risco

BANCOS = {
    "10.0.0.5:65432": Banco(nome="desenvolvimento do smart-anchor", producao=False),
    "10.0.0.5:45432": Banco(nome="produção do smart-anchor", producao=True),
}


def _pacote(pasta, scripts):
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "package.json").write_text(json.dumps({"scripts": scripts}))


def _smart_anchor(raiz, banco="10.0.0.5:65432"):
    projeto = raiz / "smart-anchor"
    _pacote(projeto / "backend", {"dev": "nest start --watch"})
    _pacote(projeto / "frontend", {"dev": "next dev --turbopack -p 3100"})
    host, porta = banco.split(":")
    (projeto / "backend" / ".env").write_text(
        f'DATABASE_URL="postgresql://postgres:senha-secreta@{host}:{porta}/postgres?schema=app"\n'
        'DATABASE_URL_PROD="postgresql://postgres:outra@10.0.0.5:45432/postgres"\n'
    )
    return projeto


class Avisos:
    def __init__(self):
        self.recebidos = []

    async def __call__(self, titulo, texto):
        self.recebidos.append((titulo, texto))


@pytest.fixture
def avisos():
    return Avisos()


@pytest.fixture
def delegacoes(avisos):
    return Delegacoes(avisos)


@pytest.fixture
def montar(executor, delegacoes, tmp_path):
    def _montar(site_no_ar=True):
        async def esperar_site(endereco):
            return site_no_ar

        [f] = ferramentas_de_aplicacoes(executor, delegacoes, raizes=[tmp_path], bancos=BANCOS, esperar_site=esperar_site)
        return f
    return _montar


def test_acha_o_projeto_pelo_nome_falado_e_prefere_o_nome_exato(montar, tmp_path):
    _smart_anchor(tmp_path)
    _pacote(tmp_path / "smart-anchor-redesign", {"dev": "next dev"})
    f = montar()

    frase = f.frase_de_confirmacao(f.argumentos(projeto="smart anchor"))

    assert "smart-anchor" in frase
    assert "redesign" not in frase


def test_confirmacao_diz_as_partes_e_o_banco_reconhecido_sem_a_senha(montar, tmp_path):
    _smart_anchor(tmp_path)
    f = montar()
    args = f.argumentos(projeto="smart-anchor")

    frase = f.frase_de_confirmacao(args)

    assert f.risco_de(args) is Risco.CONFIRMAR
    assert "backend" in frase and "frontend" in frase
    assert "desenvolvimento do smart-anchor" in frase
    assert "senha" not in frase


def test_banco_desconhecido_aparece_com_endereco_e_porta(montar, tmp_path):
    _smart_anchor(tmp_path, banco="192.168.1.9:5432")
    f = montar()

    frase = f.frase_de_confirmacao(f.argumentos(projeto="smart-anchor"))

    assert "não conheço" in frase
    assert "192.168.1.9" in frase and "5432" in frase


async def test_banco_de_producao_recusa_sem_abrir_nada(montar, executor, tmp_path):
    _smart_anchor(tmp_path, banco="10.0.0.5:45432")
    f = montar()
    args = f.argumentos(projeto="smart-anchor")

    resposta = await f.executar(args)

    assert f.risco_de(args) is Risco.SEGURO
    assert executor.iniciados == []
    assert "produção do smart-anchor" in resposta


async def test_abre_um_terminal_visivel_por_parte(montar, executor, tmp_path):
    projeto = _smart_anchor(tmp_path)
    f = montar()

    await f.executar(f.argumentos(projeto="smart-anchor"))

    assert executor.iniciados == [
        (["ptyxis", "--new-window", "-d", str(projeto / "backend"), "--", "npm", "run", "dev"], None),
        (["ptyxis", "--new-window", "-d", str(projeto / "frontend"), "--", "npm", "run", "dev"], None),
    ]


async def test_quando_o_site_responde_abre_o_navegador_e_avisa(montar, executor, delegacoes, avisos, tmp_path):
    _smart_anchor(tmp_path)
    f = montar()

    await f.executar(f.argumentos(projeto="smart-anchor"))
    await delegacoes.aguardar()

    assert (["xdg-open", "http://localhost:3100"], None) in executor.iniciados
    [(_, texto)] = avisos.recebidos
    assert "no ar" in texto


async def test_site_que_nao_responde_vira_aviso_sem_abrir_navegador(montar, executor, delegacoes, avisos, tmp_path):
    _smart_anchor(tmp_path)
    f = montar(site_no_ar=False)

    await f.executar(f.argumentos(projeto="smart-anchor"))
    await delegacoes.aguardar()

    assert not any(a[0] == "xdg-open" for a, _ in executor.iniciados)
    [(_, texto)] = avisos.recebidos
    assert "terminal" in texto.lower()


@pytest.mark.parametrize("script,endereco", [
    ("vite", "http://localhost:5173"),
    ("next dev", "http://localhost:3000"),
    ("vite --port 4000", "http://localhost:4000"),
])
async def test_endereco_do_site_vem_do_script(montar, executor, delegacoes, tmp_path, script, endereco):
    _pacote(tmp_path / "painel", {"dev": script})
    f = montar()

    await f.executar(f.argumentos(projeto="painel"))
    await delegacoes.aguardar()

    assert (["xdg-open", endereco], None) in executor.iniciados


async def test_projeto_sem_script_de_dev_nao_roda(montar, executor, tmp_path):
    _pacote(tmp_path / "biblioteca", {"build": "tsc"})
    f = montar()
    args = f.argumentos(projeto="biblioteca")

    resposta = await f.executar(args)

    assert f.risco_de(args) is Risco.SEGURO
    assert executor.iniciados == []
    assert "não sei rodar" in resposta.lower()


async def test_projeto_que_nao_existe(montar, executor, tmp_path):
    f = montar()

    resposta = await f.executar(f.argumentos(projeto="spotify"))

    assert executor.iniciados == []
    assert "não achei" in resposta.lower()
