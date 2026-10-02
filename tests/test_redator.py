"""O e-mail é escrito numa chamada própria ao modelo local, separada da escolha da ferramenta."""
from clarisse.llm import RespostaDoModelo
from clarisse.redator import redigir_email


class ModeloQueEscreve:
    def __init__(self, texto):
        self.texto = texto
        self.recebidas = []

    async def conversar(self, mensagens, ferramentas):
        self.recebidas.append((mensagens, ferramentas))
        return RespostaDoModelo(self.texto, [], {"role": "assistant", "content": self.texto})


async def test_separa_o_assunto_do_texto_e_nao_oferece_ferramenta():
    modelo = ModeloQueEscreve("Assunto: Proposta revisada\n\nOi, Ana.\n\nA proposta chega amanhã de manhã.\n\nAbraço,\nVinicius")

    assunto, texto = await redigir_email(modelo, "a proposta revisada chega amanhã de manhã", "Ana Souza", "Vinicius")

    assert assunto == "Proposta revisada"
    assert texto == "Oi, Ana.\n\nA proposta chega amanhã de manhã.\n\nAbraço,\nVinicius"
    [(mensagens, ferramentas)] = modelo.recebidas
    assert ferramentas == []
    pedido = mensagens[-1]["content"]
    assert "a proposta revisada chega amanhã de manhã" in pedido and "Ana Souza" in pedido
    assert "Vinicius" in mensagens[0]["content"]


async def test_sem_a_linha_de_assunto_o_assunto_sai_do_pedido():
    modelo = ModeloQueEscreve("Oi, Ana.\n\nTudo certo para amanhã.")

    assunto, texto = await redigir_email(modelo, "confirmar a reunião de amanhã com o time", "Ana", None)

    assert assunto == "Confirmar a reunião de amanhã com o time"
    assert texto == "Oi, Ana.\n\nTudo certo para amanhã."
