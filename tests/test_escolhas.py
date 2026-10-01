"""Voltar para a última lista (manchetes, e-mails, notas) depois de ler um item."""
from clarisse.cartoes import UltimaEscolha
from clarisse.ferramentas.escolhas import ferramentas_de_escolha


async def _chamar(escolhas, nome):
    f = {f.nome: f for f in ferramentas_de_escolha(escolhas)}[nome]
    return await f.executar(f.argumentos())


async def _voltar(escolhas):
    return await _chamar(escolhas, "voltar_para_a_lista")


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


async def test_le_os_titulos_da_lista_so_quando_pedem():
    escolhas = UltimaEscolha()
    escolhas.guardar({"tipo": "escolha", "titulo": "E-mail", "pedido": "lê o e-mail", "itens": [
        {"numero": 1, "titulo": "Proposta", "falado": "de Ana: Proposta"},
        {"numero": 2, "titulo": "Manchete sem jeito especial de falar"},
    ]})

    resposta = await _chamar(escolhas, "ler_titulos_da_lista")

    assert resposta.texto == "1, de Ana: Proposta. 2, Manchete sem jeito especial de falar. Qual você quer que eu leia?"
    assert resposta.na_integra


async def test_ler_titulos_sem_lista():
    assert await _chamar(UltimaEscolha(), "ler_titulos_da_lista") == "Ainda não abri nenhuma lista."
