"""Voltar para a última lista depois de ler um item dela."""
from clarisse.cartoes import Retorno, UltimaEscolha
from clarisse.ferramentas.registro import Argumentos, Ferramenta


def ferramentas_de_escolha(escolhas: UltimaEscolha) -> list[Ferramenta]:
    async def voltar_para_a_lista(args: Argumentos) -> Retorno | str:
        if escolhas.cartao is None:
            return "Ainda não abri nenhuma lista para voltar."
        return Retorno("Aqui está a lista de novo. Qual você quer que eu leia?", cartao=escolhas.cartao, na_integra=True)

    return [
        Ferramenta(
            "voltar_para_a_lista",
            "Mostra de novo a última lista de manchetes, e-mails ou notas. Use para 'volta', 'volta para a lista', "
            "'volta para as notícias', 'mostra as outras'.",
            Argumentos, voltar_para_a_lista,
        )
    ]
