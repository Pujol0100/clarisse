"""Voltar para a última lista (manchetes, e-mails, notas) depois de ler um item."""
from clarisse.cartoes import UltimaEscolha
from clarisse.ferramentas.escolhas import ferramentas_de_escolha


async def _voltar(escolhas):
    [f] = ferramentas_de_escolha(escolhas)
    return await f.executar(f.argumentos())


async def test_volta_a_mostrar_a_ultima_lista():
    escolhas = UltimaEscolha()
    lista = {"tipo": "escolha", "titulo": "Notícias", "pedido": "lê a notícia", "itens": [{"numero": 1, "titulo": "x"}]}
    escolhas.guardar(lista)

    resposta = await _voltar(escolhas)

    assert resposta.cartao == lista
    assert resposta.texto == "Aqui está a lista de novo. Qual você quer que eu leia?"
    assert resposta.na_integra


async def test_sem_lista_ainda():
    assert await _voltar(UltimaEscolha()) == "Ainda não abri nenhuma lista para voltar."
