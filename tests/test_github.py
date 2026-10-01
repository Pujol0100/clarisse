"""PRs e checagens pelo gh, só leitura."""
import json

from clarisse.ferramentas.github import ferramentas_do_github
from clarisse.ferramentas.processos import Resultado


def _ferramentas(executor, cadastros):
    return {f.nome: f for f in ferramentas_do_github(executor, cadastros)}


async def _chamar(ferramentas, nome, **argumentos):
    f = ferramentas[nome]
    return await f.executar(f.argumentos(**argumentos))


PRS = [
    {"number": 508, "title": "POD interna: motor", "repository": {"name": "omni-api", "nameWithOwner": "smart-corelake/omni-api"}},
    {"number": 9, "title": "Clarisse assistente local", "repository": {"name": "clarisse", "nameWithOwner": "Pujol0100/clarisse"}},
]


async def test_minhas_prs_abertas(executor, cadastros):
    executor.respostas.append(Resultado(0, json.dumps(PRS), ""))

    resposta = await _chamar(_ferramentas(executor, cadastros), "prs_abertas")

    assert executor.executados[0][0] == [
        "gh", "search", "prs", "--author=@me", "--state=open", "--json", "number,title,repository", "--limit", "10",
    ]
    assert resposta.na_integra
    assert resposta.texto == "Você tem 2 PRs abertas: 508 do omni-api, POD interna: motor. 9 do clarisse, Clarisse assistente local."
    assert resposta.cartao == {
        "tipo": "lista", "titulo": "GitHub", "canto": "suas PRs abertas",
        "itens": [["#508", "omni-api · POD interna: motor"], ["#9", "clarisse · Clarisse assistente local"]],
    }


async def test_prs_que_esperam_a_minha_revisao(executor, cadastros):
    executor.respostas.append(Resultado(0, "[]", ""))

    resposta = await _chamar(_ferramentas(executor, cadastros), "prs_abertas", de="para_eu_revisar")

    assert "--review-requested=@me" in executor.executados[0][0]
    assert resposta.texto == "Nenhuma PR esperando a sua revisão."


async def test_situacao_da_pr_conta_as_checagens_pelo_repositorio_do_projeto(executor, cadastros):
    executor.respostas += [
        Resultado(0, '{"nameWithOwner":"smart-corelake/omni-api"}', ""),
        Resultado(1, json.dumps([
            {"bucket": "pass", "name": "testes", "state": "SUCCESS"},
            {"bucket": "fail", "name": "lint", "state": "FAILURE"},
            {"bucket": "pending", "name": "build", "state": "IN_PROGRESS"},
        ]), ""),
    ]

    resposta = await _chamar(_ferramentas(executor, cadastros), "situacao_da_pr", projeto="omni api", numero=508)

    descobrir, checar = executor.executados
    assert descobrir == (["gh", "repo", "view", "--json", "nameWithOwner"], cadastros.projetos["omni-api"])
    assert checar[0] == ["gh", "pr", "checks", "508", "--repo", "smart-corelake/omni-api", "--json", "name,state,bucket"]
    assert resposta.texto == "PR 508 do omni-api: 1 falhou (lint), 1 rodando (build), 1 passou."
    assert resposta.cartao["itens"] == [["falhou", "lint"], ["rodando", "build"], ["passou", "testes"]]


async def test_pr_sem_checagens(executor, cadastros):
    executor.respostas += [
        Resultado(0, '{"nameWithOwner":"smart-corelake/omni-api"}', ""),
        Resultado(1, "", "no checks reported on the 'x' branch"),
    ]

    resposta = await _chamar(_ferramentas(executor, cadastros), "situacao_da_pr", projeto="omni-api", numero=3)

    assert resposta == "A PR 3 do omni-api não tem checagens automáticas."


async def test_projeto_desconhecido_na_situacao_da_pr(executor, cadastros):
    resposta = await _chamar(_ferramentas(executor, cadastros), "situacao_da_pr", projeto="financeiro", numero=3)

    assert "financeiro" in resposta and executor.executados == []


async def test_lista_longa_fala_so_as_cinco_primeiras_e_mostra_todas(executor, cadastros):
    prs = [{"number": n, "title": f"PR {n}", "repository": {"name": "omni-api", "nameWithOwner": "x/omni-api"}} for n in range(1, 9)]
    executor.respostas.append(Resultado(0, json.dumps(prs), ""))

    resposta = await _chamar(_ferramentas(executor, cadastros), "prs_abertas")

    assert resposta.texto.startswith("Você tem 8 PRs abertas. As 5 mais recentes: 1 do omni-api, PR 1.")
    assert "PR 6" not in resposta.texto
    assert len(resposta.cartao["itens"]) == 8
