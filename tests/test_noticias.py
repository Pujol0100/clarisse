from pathlib import Path

import httpx
import pytest

from clarisse.ferramentas.noticias import FEEDS, ferramentas_de_noticias, paragrafos_da_materia

EXEMPLO = (Path(__file__).parent / "dados" / "g1-exemplo.xml").read_text(encoding="utf-8")


def _rss(*titulos: str) -> str:
    itens = "".join(f"<item><title>{t}</title><link>https://g1.globo.com/x</link></item>" for t in titulos)
    return f"<?xml version='1.0' encoding='UTF-8'?><rss version='2.0'><channel><title>g1</title>{itens}</channel></rss>"


def _montar(responder):
    cliente = httpx.AsyncClient(transport=httpx.MockTransport(responder))
    return {f.nome: f for f in ferramentas_de_noticias(cliente)}


def _feed_de_exemplo(pedidos=None):
    def responder(pedido):
        if pedidos is not None:
            pedidos.append(str(pedido.url))
        return httpx.Response(200, text=EXEMPLO)
    return responder


async def _chamar(ferramentas, nome, **argumentos):
    f = ferramentas[nome]
    return await f.executar(f.argumentos(**argumentos))


async def test_devolve_as_cinco_primeiras_manchetes_do_feed_geral():
    pedidos = []

    def responder(pedido):
        pedidos.append(str(pedido.url))
        return httpx.Response(200, text=_rss(*[f"Manchete {i}" for i in range(1, 9)]))

    resposta = (await _chamar(_montar(responder), "noticias_do_dia")).texto

    assert pedidos == [FEEDS["geral"]]
    assert "Manchete 1" in resposta and "Manchete 5" in resposta
    assert "Manchete 6" not in resposta


async def test_tema_escolhe_o_feed_sem_acento_e_caixa():
    pedidos = []

    await _chamar(_montar(_feed_de_exemplo(pedidos)), "noticias_do_dia", tema="Tecnologia")

    assert pedidos == [FEEDS["tecnologia"]]


async def test_tema_desconhecido_cai_no_geral():
    pedidos = []

    await _chamar(_montar(_feed_de_exemplo(pedidos)), "noticias_do_dia", tema="culinária")

    assert pedidos == [FEEDS["geral"]]


@pytest.mark.parametrize("resposta_http", [httpx.Response(503), httpx.Response(200, text="<html>não é rss")])
async def test_falha_do_feed_vira_mensagem(resposta_http):
    resposta = await _chamar(_montar(lambda p: resposta_http), "noticias_do_dia")

    assert "não consegui" in resposta.lower()


async def test_falha_de_rede_vira_mensagem():
    def responder(pedido):
        raise httpx.ConnectError("sem rede")

    resposta = await _chamar(_montar(responder), "noticias_do_dia")

    assert "não consegui" in resposta.lower()


async def test_manchetes_vem_numeradas_no_cartao_e_no_texto():
    resposta = await _chamar(_montar(_feed_de_exemplo()), "noticias_do_dia", tema="tecnologia")

    assert resposta.cartao["tipo"] == "noticias"
    assert resposta.cartao["canto"] == "tecnologia"
    assert resposta.cartao["itens"][:2] == [
        {"numero": 1, "titulo": "Cidade fictícia testa ônibus sem motorista no centro"},
        {"numero": 2, "titulo": "Aplicativo de mensagens fictício ganha nomes de usuário"},
    ]
    assert "1. Cidade fictícia testa ônibus" in resposta.texto
    assert "número" in resposta.texto


def test_materia_fica_so_com_os_paragrafos_de_frase():
    descricao = (
        ' <img src="x.jpg" /><br />    Título de vídeo relacionado sem ponto\n'
        "A polícia informou nesta quinta-feira que prendeu o suspeito.\n"
        "Ele é suspeito de coordenar o grupo, informou a porta-voz.\n"
        "*Com informações da Reuters.\n"
        "Cybercrime; hacker; crimes digitais\n"
        "Kevin Horvart/Unplash  "
    )

    assert paragrafos_da_materia(descricao) == [
        "A polícia informou nesta quinta-feira que prendeu o suspeito.",
        "Ele é suspeito de coordenar o grupo, informou a porta-voz.",
    ]


async def test_le_a_noticia_pelo_numero_da_ultima_lista():
    ferramentas = _montar(_feed_de_exemplo())
    await _chamar(ferramentas, "noticias_do_dia", tema="tecnologia")

    resposta = await _chamar(ferramentas, "ler_noticia", numero=1)

    assert resposta.na_integra
    assert resposta.cartao == {
        "tipo": "leitura",
        "titulo": "Cidade fictícia testa ônibus sem motorista no centro",
        "subtitulo": "Teste dura três meses e usa duas linhas de exemplo.",
        "imagem": "https://s2-g1.glbimg.com/exemplo/onibus.jpg",
        "fonte": "g1 · tecnologia",
        "paragrafos": [
            "A prefeitura de uma cidade fictícia começou nesta quinta-feira um teste com ônibus sem motorista.",
            "Os veículos circulam em duas linhas do centro, sempre com um fiscal a bordo, segundo a prefeitura.",
            "O teste dura três meses e a tarifa continua a mesma das outras linhas.",
        ],
    }
    assert resposta.texto.startswith("Cidade fictícia testa ônibus sem motorista no centro.\n\nA prefeitura")


async def test_le_a_noticia_por_uma_palavra_do_titulo_sem_acento():
    ferramentas = _montar(_feed_de_exemplo())
    await _chamar(ferramentas, "noticias_do_dia", tema="tecnologia")

    resposta = await _chamar(ferramentas, "ler_noticia", assunto="onibus")

    assert resposta.cartao["titulo"] == "Cidade fictícia testa ônibus sem motorista no centro"


async def test_sem_lista_guardada_busca_as_manchetes_gerais():
    pedidos = []

    resposta = await _chamar(_montar(_feed_de_exemplo(pedidos)), "ler_noticia", numero=2)

    assert pedidos == [FEEDS["geral"]]
    assert resposta.cartao["titulo"] == "Aplicativo de mensagens fictício ganha nomes de usuário"
    assert resposta.cartao["fonte"] == "g1 · geral"


async def test_numero_fora_da_lista_avisa_quantas_tem():
    ferramentas = _montar(_feed_de_exemplo())
    await _chamar(ferramentas, "noticias_do_dia")

    resposta = await _chamar(ferramentas, "ler_noticia", numero=9)

    assert resposta == "Não tenho a notícia 9. A lista tem 3."


async def test_noticia_sem_texto_no_feed_avisa_em_vez_de_ler_vazio():
    ferramentas = _montar(_feed_de_exemplo())
    await _chamar(ferramentas, "noticias_do_dia")

    resposta = await _chamar(ferramentas, "ler_noticia", numero=3)

    assert resposta == "Essa notícia não veio com o texto no feed do g1. Posso abrir no navegador, se quiser."
