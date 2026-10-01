"""A última lista (manchetes, e-mails, notas): voltar a ela depois de ler um item, e ouvir os títulos.

Ao abrir uma lista, a Clarisse só pergunta qual ler; os títulos ela lê só quando pedem."""
from clarisse.cartoes import Retorno, UltimaEscolha
from clarisse.ferramentas.registro import Argumentos, Ferramenta


def ferramentas_de_escolha(escolhas: UltimaEscolha) -> list[Ferramenta]:
    async def voltar_para_a_lista(args: Argumentos) -> Retorno | str:
        if escolhas.cartao is None:
            return "Ainda não abri nenhuma lista para voltar."
        return Retorno("Aqui está a lista de novo. Qual você quer que eu leia?", cartao=escolhas.cartao, na_integra=True)

    async def ler_titulos_da_lista(args: Argumentos) -> Retorno | str:
        if escolhas.cartao is None:
            return "Ainda não abri nenhuma lista."
        titulos = " ".join(
            f"{item['numero']}, {item.get('falado') or item['titulo']}." for item in escolhas.cartao.get("itens", [])
        )
        return Retorno(f"{titulos} Qual você quer que eu leia?", na_integra=True)

    return [
        Ferramenta(
            "ler_titulos_da_lista",
            "Lê em voz alta os títulos da última lista (manchetes, e-mails, notas). Use só quando o usuário pedir "
            "para ouvir: 'lê os títulos', 'lê as manchetes', 'quais são?', 'de quem são os e-mails?'.",
            Argumentos, ler_titulos_da_lista,
        ),
        Ferramenta(
            "voltar_para_a_lista",
            "Mostra de novo a última lista de manchetes, e-mails ou notas. Use para 'volta', 'volta para a lista', "
            "'volta para as notícias', 'mostra as outras'.",
            Argumentos, voltar_para_a_lista,
        )
    ]
