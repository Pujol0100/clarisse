import json

import pytest

from clarisse.ferramentas.aplicacoes import Banco, ferramentas_de_aplicacoes
from clarisse.sites import Site
from clarisse.ferramentas.claude import Delegacoes
from clarisse.ferramentas.registro import Risco

BANCOS = {
    "10.0.0.5:65432": Banco(nome="desenvolvimento do smart-anchor", producao=False),
    "10.0.0.5:45432": Banco(nome="produção do smart-anchor", producao=True),
}


def _pacote(pasta, scripts, instalado=True, trava=True):
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "package.json").write_text(json.dumps({"scripts": scripts}), encoding="utf-8")
    if trava:
        (pasta / "package-lock.json").write_text("{}", encoding="utf-8")
    if instalado:
        (pasta / "node_modules").mkdir(exist_ok=True)


def _smart_anchor(raiz, banco="10.0.0.5:65432"):
    projeto = raiz / "smart-anchor"
    _pacote(projeto / "backend", {"dev": "nest start --watch"})
    _pacote(projeto / "frontend", {"dev": "next dev --turbopack -p 3100"})
    host, porta = banco.split(":")
    (projeto / "backend" / ".env").write_text(
        f'DATABASE_URL="postgresql://postgres:senha-secreta@{host}:{porta}/postgres?schema=app"\n'
        'DATABASE_URL_PROD="postgresql://postgres:outra@10.0.0.5:45432/postgres"\n'
        # Variáveis de scripts de sincronização: apontam para produção, mas o servidor de dev não as usa.
        'SYNC_URL_ORIGEM="postgresql://postgres:outra@10.0.0.5:45432/postgres"\n'
        "PD_DB_HOST=10.0.0.5\n"
        "PD_DB_PORT=45432\n", encoding="utf-8")
    return projeto


def _comando(argumentos):
    """O que roda dentro do terminal: ptyxis ... -- bash -c "<comando>"."""
    assert argumentos[-3:-1] == ["bash", "-c"]
    return argumentos[-1]


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
def esperas():
    return []


SITES = [
    Site("omni", "https://omni.exemplo.com/"),
    Site("kanban", "https://kanban.exemplo.com/", ["quadro"]),
    Site("dokploy do omni", "https://painel-omni.exemplo.com/"),
    Site("dokploy da store", "https://painel-store.exemplo.com/"),
]


@pytest.fixture
def todas(executor, delegacoes, tmp_path, esperas, cadastros):
    def _montar(site_no_ar=True):
        async def esperar_site(endereco, limite):
            esperas.append(limite)
            return site_no_ar

        ferramentas = ferramentas_de_aplicacoes(
            executor, delegacoes, raizes=[tmp_path], bancos=BANCOS, esperar_site=esperar_site,
            cadastros=cadastros, sites=lambda: SITES,
        )
        return {f.nome: f for f in ferramentas}
    return _montar


@pytest.fixture
def montar(todas):
    return lambda site_no_ar=True: todas(site_no_ar)["rodar_aplicacao"]


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

    assert [a[:4] for a, _ in executor.iniciados] == [
        ["ptyxis", "--new-window", "-d", str(projeto / "backend")],
        ["ptyxis", "--new-window", "-d", str(projeto / "frontend")],
    ]
    assert all(_comando(a).startswith("npm run dev;") for a, _ in executor.iniciados)


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


async def test_esperar_site_tenta_ate_o_servidor_responder():
    import httpx

    from clarisse.ferramentas.aplicacoes import esperar_site

    tentativas = []

    def responder(pedido):
        tentativas.append(pedido.url)
        if len(tentativas) < 3:
            raise httpx.ConnectError("ainda subindo")
        return httpx.Response(404)

    cliente = httpx.AsyncClient(transport=httpx.MockTransport(responder))

    assert await esperar_site("http://localhost:3100", cliente, limite=5, intervalo=0) is True
    assert len(tentativas) == 3


async def test_esperar_site_desiste_no_limite():
    import httpx

    from clarisse.ferramentas.aplicacoes import esperar_site

    def responder(pedido):
        raise httpx.ConnectError("nunca sobe")

    cliente = httpx.AsyncClient(transport=httpx.MockTransport(responder))

    assert await esperar_site("http://localhost:3100", cliente, limite=0.05, intervalo=0.01) is False



def test_banco_no_estilo_db_host_e_db_port(montar, tmp_path):
    _pacote(tmp_path / "omni-app", {"dev": "vite"})
    (tmp_path / "omni-app" / ".env").write_text("DB_HOST=10.0.0.5\nDB_PORT=65432\nDB_PASSWORD=segredo\n", encoding="utf-8")
    f = montar()

    frase = f.frase_de_confirmacao(f.argumentos(projeto="omni-app"))

    assert "desenvolvimento do smart-anchor" in frase
    assert "segredo" not in frase


def test_banco_local_da_maquina_e_dito_como_local(montar, tmp_path):
    _pacote(tmp_path / "sc360", {"dev": "next dev"})
    (tmp_path / "sc360" / ".env").write_text('DATABASE_URL="postgresql://u:p@localhost:5440/sc360"\n', encoding="utf-8")
    f = montar()

    frase = f.frase_de_confirmacao(f.argumentos(projeto="sc360"))

    assert "local desta máquina" in frase


async def test_usa_start_dev_quando_nao_ha_dev(montar, executor, tmp_path):
    _pacote(tmp_path / "omni-api", {"start:dev": "turbo run dev", "build": "turbo build"})
    f = montar()

    await f.executar(f.argumentos(projeto="omni api"))

    [(argumentos, _)] = executor.iniciados
    assert argumentos[3] == str(tmp_path / "omni-api")
    assert _comando(argumentos).startswith("npm run start:dev;")



async def test_sem_dependencias_instala_com_npm_ci_antes_de_rodar(montar, executor, delegacoes, esperas, tmp_path):
    projeto = tmp_path / "smart-anchor"
    _pacote(projeto / "backend", {"dev": "nest start --watch"}, instalado=False)
    _pacote(projeto / "frontend", {"dev": "next dev -p 3100"})
    f = montar()
    args = f.argumentos(projeto="smart-anchor")

    frase = f.frase_de_confirmacao(args)
    resposta = await f.executar(args)
    await delegacoes.aguardar()

    assert f.risco_de(args) is Risco.CONFIRMAR
    assert "instalar as dependências" in frase
    assert "minutos" in resposta
    backend, frontend = (a for a, _ in executor.iniciados[:2])
    assert backend[3] == str(projeto / "backend") and _comando(backend).startswith("npm ci && npm run dev;")
    assert frontend[3] == str(projeto / "frontend") and _comando(frontend).startswith("npm run dev;")
    assert esperas == [600]


async def test_sem_package_lock_instala_com_npm_install(montar, executor, tmp_path):
    _pacote(tmp_path / "painel", {"dev": "vite"}, instalado=False, trava=False)
    f = montar()

    await f.executar(f.argumentos(projeto="painel"))

    assert _comando(executor.iniciados[0][0]).startswith("npm install && npm run dev;")


async def test_com_dependencias_espera_o_site_so_dois_minutos(montar, delegacoes, esperas, tmp_path):
    _smart_anchor(tmp_path)
    f = montar()

    await f.executar(f.argumentos(projeto="smart-anchor"))
    await delegacoes.aguardar()

    assert esperas == [120]


async def test_dependencias_na_raiz_do_projeto_valem_para_as_partes(montar, executor, tmp_path):
    projeto = tmp_path / "monorepo"
    _pacote(projeto / "web", {"dev": "vite"}, instalado=False)
    (projeto / "node_modules").mkdir()
    f = montar()

    await f.executar(f.argumentos(projeto="monorepo"))

    assert len(executor.iniciados) == 1



async def test_terminal_fica_aberto_mostrando_o_erro_quando_o_servidor_para(montar, executor, tmp_path):
    _pacote(tmp_path / "painel", {"dev": "vite"})
    f = montar()

    await f.executar(f.argumentos(projeto="painel"))

    comando = _comando(executor.iniciados[0][0])
    assert comando.startswith("npm run dev;")
    assert comando.rstrip().endswith("read")



async def test_abrir_programa_instalado(todas, executor):
    f = todas()["abrir"]
    args = f.argumentos(nome="vs code")

    await f.executar(args)

    assert f.risco_de(args) is Risco.SEGURO
    assert executor.iniciados == [(["code"], None)]


async def test_abrir_sistema_da_internet_pelo_apelido(todas, executor):
    f = todas()["abrir"]

    resposta = await f.executar(f.argumentos(nome="quadro"))

    assert executor.iniciados == [(["xdg-open", "https://kanban.exemplo.com/"], None)]
    assert "kanban" in resposta


async def test_nome_que_e_site_e_projeto_pergunta_sem_abrir_nada(todas, executor, tmp_path):
    _pacote(tmp_path / "omni", {"dev": "vite"})
    f = todas()["abrir"]
    args = f.argumentos(nome="omni")

    resposta = await f.executar(args)

    assert f.risco_de(args) is Risco.SEGURO
    assert executor.iniciados == []
    assert "site" in resposta and "local" in resposta and resposta.rstrip().endswith("?")


async def test_escolhido_o_site_abre_o_site(todas, executor, tmp_path):
    _pacote(tmp_path / "omni", {"dev": "vite"})
    f = todas()["abrir"]

    await f.executar(f.argumentos(nome="omni", onde="site"))

    assert executor.iniciados == [(["xdg-open", "https://omni.exemplo.com/"], None)]


async def test_escolhido_o_local_roda_o_projeto_com_confirmacao(todas, executor, tmp_path):
    _pacote(tmp_path / "omni", {"dev": "vite"})
    f = todas()["abrir"]
    args = f.argumentos(nome="omni", onde="local")

    assert f.risco_de(args) is Risco.CONFIRMAR
    assert "Vou rodar o omni" in f.frase_de_confirmacao(args)
    await f.executar(args)
    assert executor.iniciados[0][0][:4] == ["ptyxis", "--new-window", "-d", str(tmp_path / "omni")]


async def test_projeto_sem_site_roda_local_com_confirmacao(todas, executor, tmp_path):
    projeto = _smart_anchor(tmp_path)
    f = todas()["abrir"]
    args = f.argumentos(nome="smart anchor")

    assert f.risco_de(args) is Risco.CONFIRMAR
    await f.executar(args)
    assert executor.iniciados[0][0][3] == str(projeto / "backend")


async def test_varios_sites_com_o_nome_pergunta_qual(todas, executor):
    f = todas()["abrir"]

    resposta = await f.executar(f.argumentos(nome="dokploy"))

    assert executor.iniciados == []
    assert "dokploy do omni" in resposta and "dokploy da store" in resposta


async def test_nome_desconhecido(todas, executor):
    f = todas()["abrir"]

    resposta = await f.executar(f.argumentos(nome="spotify"))

    assert executor.iniciados == []
    assert "não conheço" in resposta.lower()


async def test_pedido_de_site_que_so_existe_como_projeto_nao_roda_o_projeto(todas, executor, tmp_path):
    _smart_anchor(tmp_path)
    f = todas()["abrir"]
    args = f.argumentos(nome="smart anchor", onde="site")

    resposta = await f.executar(args)

    assert f.risco_de(args) is Risco.SEGURO
    assert executor.iniciados == []
    assert "não conheço o site" in resposta.lower()
