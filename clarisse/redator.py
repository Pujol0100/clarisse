"""Escreve o texto de um e-mail numa chamada própria ao modelo local, sem ferramentas.

Separar a escrita da escolha da ferramenta foi medido em 01/10/2026: pedindo o e-mail inteiro como
argumento da ferramenta, o Gemma não chamava a ferramenta e perguntava "para quem?" mesmo com tudo dito."""
import re

_ASSUNTO = re.compile(r"^\s*assunto\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)


def _instrucoes(assinatura: str | None) -> str:
    despedida = f"'Abraço,' e, na linha de baixo, {assinatura}" if assinatura else "'Abraço,'"
    return (
        "Você escreve e-mails de trabalho curtos em português do Brasil, educados e diretos. "
        "Responda só com o e-mail, neste formato: a primeira linha 'Assunto: ' seguida de um assunto curto, "
        "uma linha em branco, a saudação 'Olá, ' com o primeiro nome de quem recebe, o texto em um ou dois parágrafos "
        f"e a despedida {despedida}. Não invente fatos, datas nem valores que o pedido não tem."
    )


async def redigir_email(modelo, sobre: str, para: str, assinatura: str | None) -> tuple[str, str]:
    """(assunto, texto) do e-mail para `para` dizendo `sobre`."""
    resposta = await modelo.conversar(
        [{"role": "system", "content": _instrucoes(assinatura)},
         {"role": "user", "content": f"Para: {para}\nO que dizer: {sobre}"}],
        [],
    )
    texto = resposta.texto.strip()
    achado = _ASSUNTO.search(texto)
    if achado:
        assunto = achado.group(1).strip()
        texto = (texto[:achado.start()] + texto[achado.end():]).strip()
    else:
        assunto = sobre.strip().rstrip(".")
        assunto = assunto[:1].upper() + assunto[1:]
    return assunto, texto
