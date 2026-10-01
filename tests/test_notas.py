"""Busca e leitura das notas do cofre do Obsidian, na máquina."""
import os

import pytest

from clarisse.ferramentas.notas import ferramentas_de_notas


@pytest.fixture
def cofre(tmp_path):
    raiz = tmp_path / "cofre"
    (raiz / "SmartCompass" / "smart-anchor").mkdir(parents=True)
    (raiz / ".obsidian").mkdir()
    (raiz / "SmartCompass" / "smart-anchor" / "smart-anchor.md").write_text(
        "---\ntipo: projeto\ntags: [anchor]\n---\n"
        "# Smart Anchor\n\n"
        "O **deploy** é manual, sem staging. Ver [[omni-api|o Omni]] e [o painel](https://exemplo.com).\n\n"
        "## Pendente\n\n- Conferir o e-mail das 9h.\n- Falar com a [[Geovanna]].\n\n"
        "```bash\nnpm run build\n```\n",
        encoding="utf-8",
    )
    (raiz / "SmartCompass" / "omni.md").write_text("O omni chama o smart anchor uma vez por dia.\n", encoding="utf-8")
    (raiz / "receitas.md").write_text("Bolo de cenoura.\n", encoding="utf-8")
    (raiz / ".obsidian" / "anchor.md").write_text("smart anchor configuração interna\n", encoding="utf-8")
    os.utime(raiz / "SmartCompass" / "omni.md", (1_800_000_000, 1_800_000_000))
    return raiz


def _ferramentas(cofre):
    return {f.nome: f for f in ferramentas_de_notas(cofre)}


async def _chamar(ferramentas, nome, **argumentos):
    f = ferramentas[nome]
    return await f.executar(f.argumentos(**argumentos))


async def test_busca_poe_primeiro_a_nota_com_o_termo_no_nome_e_ignora_a_pasta_do_obsidian(cofre):
    resposta = await _chamar(_ferramentas(cofre), "buscar_nas_notas", termo="Smart Anchor")

    assert [i["titulo"] for i in resposta.cartao["itens"]] == ["smart-anchor", "omni"]
    assert resposta.cartao["tipo"] == "escolha" and resposta.cartao["pedido"] == "lê a nota"
    assert resposta.texto == "Achei 2 notas: 1, smart-anchor. 2, omni. Para eu ler uma, diga o número."
    assert resposta.na_integra


async def test_busca_sem_resultado(cofre):
    resposta = await _chamar(_ferramentas(cofre), "buscar_nas_notas", termo="sicoob")

    assert resposta == "Não achei nada sobre sicoob nas notas."


async def test_le_a_nota_sem_marcacao_de_markdown(cofre):
    ferramentas = _ferramentas(cofre)
    await _chamar(ferramentas, "buscar_nas_notas", termo="smart anchor")

    resposta = await _chamar(ferramentas, "ler_nota", numero=1)

    assert resposta.na_integra
    assert resposta.cartao["rotulo"] == "Nota"
    assert resposta.cartao["titulo"] == "smart-anchor"
    assert resposta.cartao["paragrafos"] == [
        "Smart Anchor",
        "O deploy é manual, sem staging. Ver o Omni e o painel.",
        "Pendente",
        "Conferir o e-mail das 9h.",
        "Falar com a Geovanna.",
        "Trecho de código.",
    ]


async def test_nota_fora_da_lista(cofre):
    ferramentas = _ferramentas(cofre)
    await _chamar(ferramentas, "buscar_nas_notas", termo="smart anchor")

    assert await _chamar(ferramentas, "ler_nota", numero=4) == "Não tenho a nota 4. A lista tem 2."
