import os
from datetime import datetime
from pathlib import Path

import pytest

from clarisse.ferramentas.registro import Risco
from clarisse.ferramentas.sistema import ferramentas_do_sistema


@pytest.fixture
def volumes():
    return []


@pytest.fixture
def ferramentas(cadastros, executor, volumes):
    agora = lambda: datetime(2026, 9, 28, 14, 5)
    return {f.nome: f for f in ferramentas_do_sistema(cadastros, executor, agora=agora, definir_volume=volumes.append)}


async def _rodar(ferramentas, ferramenta, **args):
    f = ferramentas[ferramenta]
    return await f.executar(f.argumentos(**args))


async def test_hora_e_data_em_portugues(ferramentas):
    resposta = await _rodar(ferramentas, "hora_e_data")

    assert resposta == "Hoje é segunda-feira, 28 de setembro de 2026, 14:05."


async def test_abre_aplicativo_cadastrado_pelo_apelido(ferramentas, executor):
    resposta = await _rodar(ferramentas, "abrir_aplicativo", nome="VS Code")

    assert executor.iniciados == [(["code"], None)]
    assert "vscode" in resposta


async def test_nao_abre_aplicativo_fora_do_cadastro(ferramentas, executor):
    resposta = await _rodar(ferramentas, "abrir_aplicativo", nome="spotify")

    assert executor.iniciados == []
    assert "não conheço" in resposta.lower()
    assert "vscode" in resposta


async def test_fechar_aplicativo_pede_confirmacao_e_fecha_pelo_processo(ferramentas, executor):
    fechar = ferramentas["fechar_aplicativo"]
    args = fechar.argumentos(nome="navegador")

    assert fechar.risco_de(args) is Risco.CONFIRMAR
    assert "chrome" in fechar.frase_de_confirmacao(args)
    await fechar.executar(args)
    assert executor.encerrados == ["chrome.exe"]


async def test_fechar_aplicativo_que_nao_estava_aberto(ferramentas, executor):
    executor.quantos_encerrar = 0

    resposta = await _rodar(ferramentas, "fechar_aplicativo", nome="navegador")

    assert "não estava aberto" in resposta


async def test_abre_pasta_pelo_apelido(ferramentas, executor):
    await _rodar(ferramentas, "abrir_pasta", pasta="Downloads")

    assert executor.abertos == [str(Path.home() / "Downloads")]


async def test_abre_pasta_dentro_da_home_pelo_caminho(ferramentas, executor, tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    (tmp_path / "Projetos").mkdir()

    await _rodar(ferramentas, "abrir_pasta", pasta="~/Projetos")

    assert executor.abertos == [str(tmp_path / "Projetos")]


@pytest.mark.parametrize("pasta", ["C:\\Windows", "~/../../Windows", "C:\\"])
async def test_recusa_pasta_fora_da_home(ferramentas, executor, pasta):
    resposta = await _rodar(ferramentas, "abrir_pasta", pasta=pasta)

    assert executor.abertos == []
    assert "não" in resposta.lower()


@pytest.mark.parametrize(
    "endereco,esperado",
    [
        ("github", "https://github.com"),
        ("github.com", "https://github.com"),
        ("https://g1.globo.com/economia", "https://g1.globo.com/economia"),
        ("http://localhost:3000", "http://localhost:3000"),
    ],
)
async def test_abre_site_com_endereco_completado(ferramentas, executor, endereco, esperado):
    await _rodar(ferramentas, "abrir_site", endereco=endereco)

    assert executor.abertos == [esperado]


@pytest.mark.parametrize("endereco", ["file:///etc/passwd", "javascript:alert(1)", "ftp://x.com", "--help"])
async def test_recusa_site_que_nao_e_http(ferramentas, executor, endereco):
    await _rodar(ferramentas, "abrir_site", endereco=endereco)

    assert executor.abertos == []


async def test_ajusta_volume_do_windows(ferramentas, volumes):
    resposta = await _rodar(ferramentas, "ajustar_volume", nivel=30)

    assert volumes == [30]
    assert resposta == "Volume em 30 por cento."


def test_volume_fora_da_faixa_e_invalido(ferramentas):
    with pytest.raises(ValueError):
        ferramentas["ajustar_volume"].argumentos(nivel=150)


async def test_lista_programas_cadastrados_que_estao_abertos(cadastros, executor):
    processos = lambda: ["chrome.exe", "chrome.exe", "powershell.exe", "Code.exe"]
    [lista] = [f for f in ferramentas_do_sistema(cadastros, executor, processos=processos) if f.nome == "listar_programas_abertos"]

    resposta = await lista.executar(lista.argumentos())

    assert "vscode" in resposta and "chrome" in resposta
    assert "powershell" not in resposta


async def test_programa_aberto_casa_sem_diferenciar_maiusculas(cadastros, executor):
    processos = lambda: ["CODE.EXE"]
    [lista] = [f for f in ferramentas_do_sistema(cadastros, executor, processos=processos) if f.nome == "listar_programas_abertos"]

    assert "vscode" in await lista.executar(lista.argumentos())


def _arquivo(pasta, nome, idade=0):
    caminho = pasta / nome
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("x", encoding="utf-8")
    antigo = 1_700_000_000 - idade
    os.utime(caminho, (antigo, antigo))
    return caminho


async def test_abre_o_arquivo_pelo_nome_falado_sem_acento_e_fora_de_ordem(ferramentas, executor, tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    alvo = _arquivo(tmp_path / "Documentos", "Relatório-Setembro-2026.pdf")

    resposta = await _rodar(ferramentas, "abrir_arquivo", nome="setembro relatorio")

    assert executor.abertos == [str(alvo)]
    assert "Relatório-Setembro-2026.pdf" in resposta


async def test_varios_arquivos_nao_abre_e_lista_os_mais_recentes(ferramentas, executor, tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    for i in range(5):
        _arquivo(tmp_path / "Documentos", f"boletos-{i}.xlsx", idade=i * 100)

    resposta = await _rodar(ferramentas, "abrir_arquivo", nome="boletos")

    assert executor.abertos == []
    assert "5" in resposta
    assert "boletos-0.xlsx" in resposta and "boletos-2.xlsx" in resposta
    assert "boletos-4.xlsx" not in resposta


async def test_nao_procura_em_pasta_oculta_nem_em_node_modules(ferramentas, executor, tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    _arquivo(tmp_path / ".cache", "contrato.pdf")
    _arquivo(tmp_path / "projeto" / "node_modules" / "pacote", "contrato.pdf")

    resposta = await _rodar(ferramentas, "abrir_arquivo", nome="contrato")

    assert executor.abertos == []
    assert "não achei" in resposta.lower()


async def test_nao_procura_em_appdata(ferramentas, executor, tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    _arquivo(tmp_path / "AppData" / "Local" / "Programa", "contrato.pdf")

    resposta = await _rodar(ferramentas, "abrir_arquivo", nome="contrato")

    assert executor.abertos == []
    assert "não achei" in resposta.lower()


@pytest.mark.parametrize("nome", ["instalar.bat", "rodar.ps1", "atalho.lnk", "programa.exe", "setup.msi"])
async def test_nao_abre_arquivo_que_executa_programa(ferramentas, executor, tmp_path, monkeypatch, nome):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    _arquivo(tmp_path / "Downloads", nome)

    resposta = await _rodar(ferramentas, "abrir_arquivo", nome=nome.split(".")[0])

    assert executor.abertos == []
    assert "não abro" in resposta.lower()


async def test_arquivo_sem_extensao_abre(ferramentas, executor, tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    alvo = _arquivo(tmp_path / "Downloads", "anotacoes-backup")

    await _rodar(ferramentas, "abrir_arquivo", nome="anotacoes backup")

    assert executor.abertos == [str(alvo)]


async def test_nome_da_pasta_tambem_conta(ferramentas, executor, tmp_path, monkeypatch):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    alvo = _arquivo(tmp_path / "Documentos" / "smart-anchor", "README.md")
    _arquivo(tmp_path / "Documentos" / "omni-api", "README.md")

    await _rodar(ferramentas, "abrir_arquivo", nome="readme do smart anchor")

    assert executor.abertos == [str(alvo)]


@pytest.mark.parametrize("pedido,certo,errado", [
    ("planilha de boletos", "boletos.xlsx", "boletos.ts"),
    ("pdf do contrato", "contrato.pdf", "contrato.docx"),
    ("documento do contrato", "contrato.docx", "contrato.ts"),
])
async def test_tipo_falado_vira_filtro_de_extensao(ferramentas, executor, tmp_path, monkeypatch, pedido, certo, errado):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    alvo = _arquivo(tmp_path / "Documentos", certo)
    _arquivo(tmp_path / "Documentos", errado)

    await _rodar(ferramentas, "abrir_arquivo", nome=pedido)

    assert executor.abertos == [str(alvo)]


async def test_nome_de_sistema_da_empresa_abre_o_endereco_dele_e_nao_um_ponto_com(cadastros, executor):
    from clarisse.sites import Site

    f = {x.nome: x for x in ferramentas_do_sistema(cadastros, executor, sites=lambda: [Site("sc360", "https://sc360.empresa.com/")])}

    await f["abrir_site"].executar(f["abrir_site"].argumentos(endereco="sc360"))

    assert executor.abertos == ["https://sc360.empresa.com/"]


async def test_endereco_com_ponto_continua_indo_direto(cadastros, executor):
    from clarisse.sites import Site

    f = {x.nome: x for x in ferramentas_do_sistema(cadastros, executor, sites=lambda: [Site("github", "https://errado/")])}

    await f["abrir_site"].executar(f["abrir_site"].argumentos(endereco="github.com"))

    assert executor.abertos == ["https://github.com"]


async def test_abrir_aplicativo_com_nome_de_sistema_abre_o_site(cadastros, executor):
    from clarisse.sites import Site

    f = {x.nome: x for x in ferramentas_do_sistema(cadastros, executor, sites=lambda: [Site("kanban", "https://kanban.empresa/")])}

    await f["abrir_aplicativo"].executar(f["abrir_aplicativo"].argumentos(nome="kanban"))

    assert executor.abertos == ["https://kanban.empresa/"]


async def test_abrir_aplicativo_com_nome_de_projeto_pergunta_sem_rodar(cadastros, executor, tmp_path):
    (tmp_path / "omni-app").mkdir()
    f = {x.nome: x for x in ferramentas_do_sistema(cadastros, executor, raizes=[tmp_path])}

    resposta = await f["abrir_aplicativo"].executar(f["abrir_aplicativo"].argumentos(nome="omni app"))

    assert executor.iniciados == []
    assert "local" in resposta and resposta.rstrip().endswith("?")
