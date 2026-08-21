"""Gera amostras de fala em pt-BR com a mesma voz que a Clarisse ja usa.

Audio sintetico e mais limpo que microfone real, entao a precisao medida aqui e
otimista. Serve para comparar os motores entre si em condicao identica, e para
medir latencia - que nao depende de o audio ser sintetico ou nao.
"""

import asyncio
import json
from pathlib import Path

import edge_tts

VOZ = "pt-BR-ThalitaMultilingualNeural"

FRASES = [
    ("curta", "Clarisse, o que esta rolando no omni-api?"),
    ("media", "Clarisse, me conta o que aconteceu na cadeia sequencial hoje."),
    ("longa", "Clarisse, resume a ultima sessao do voz ao claude e diz quantos testes passaram."),
    ("nomes", "Clarisse, compara o omni-api com a cadeia sequencial."),
    ("acao", "Clarisse, roda os testes do projeto e me avisa quando terminar."),
]

# O que a transcricao deveria devolver, para calcular a taxa de erro.
REFERENCIAS = {
    "curta": "clarisse o que esta rolando no omni api",
    "media": "clarisse me conta o que aconteceu na cadeia sequencial hoje",
    "longa": "clarisse resume a ultima sessao do voz ao claude e diz quantos testes passaram",
    "nomes": "clarisse compara o omni api com a cadeia sequencial",
    "acao": "clarisse roda os testes do projeto e me avisa quando terminar",
}

# Frases para medir a palavra de ativacao: so o nome, e frases que NAO tem o nome
# e nunca deveriam acordar a Clarisse.
ATIVACAO = [
    ("nome_so", "Clarisse."),
    ("nome_frase", "Clarisse, escuta."),
    ("falso_1", "Preciso revisar a clareza desse texto."),
    ("falso_2", "A analise do contrato ficou pronta."),
    ("falso_3", "Vou almocar e volto depois."),
]


async def principal() -> None:
    destino = Path(__file__).parent / "audio"
    destino.mkdir(exist_ok=True)

    todas = [(f"fala_{n}", t) for n, t in FRASES] + [(f"ativ_{n}", t) for n, t in ATIVACAO]

    for nome, texto in todas:
        caminho = destino / f"{nome}.mp3"
        await edge_tts.Communicate(texto, VOZ).save(str(caminho))
        print(f"{caminho.name:24} {caminho.stat().st_size:>7} bytes  {texto}")

    (destino / "referencias.json").write_text(
        json.dumps(REFERENCIAS, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n{len(todas)} amostras geradas em {destino}")


if __name__ == "__main__":
    asyncio.run(principal())
