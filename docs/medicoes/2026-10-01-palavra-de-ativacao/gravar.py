"""Grava a voz do usuário para medir a palavra de ativação "Clarisse".

Três grupos: o nome sozinho (20), o nome seguido de um pedido (10) e frases do dia a dia sem o nome,
algumas com som parecido (20). A voz da Clarisse fala cada frase antes; um bipe marca o começo e outro
o fim da gravação. As gravações ficam em dados/ativacao/ (fora do git: é a voz do usuário).

Rodar da pasta da Clarisse:  uv run python docs/medicoes/2026-10-01-palavra-de-ativacao/gravar.py
Ctrl+C pausa; rodar de novo continua de onde parou.
"""
import asyncio
import csv
import signal
import subprocess
import sys
import time
from pathlib import Path

import edge_tts

PASTA = Path("dados/ativacao")
FALAS = PASTA / ".falas"
VOZ = "pt-BR-ThalitaMultilingualNeural"
BIPE_INICIO = "/usr/share/sounds/freedesktop/stereo/bell.oga"
BIPE_FIM = "/usr/share/sounds/freedesktop/stereo/complete.oga"

JEITOS = [
    "do seu jeito normal", "um pouco mais baixo", "um pouco mais alto", "mais rápido", "devagar",
    "como se chamasse alguém", "olhando para o lado", "de mais longe do notebook", "com a voz cansada", "do seu jeito normal",
]
COM_PEDIDO = [
    "Clarisse, que horas são?", "Clarisse, como está o tempo?", "Clarisse, lê as notícias.",
    "Clarisse, tenho e-mail?", "Clarisse, abre o VS Code.", "Clarisse, para.",
    "Clarisse, me lembra em dez minutos de beber água.", "Clarisse, quais são as minhas PRs?",
    "Clarisse, lê o que o Claude disse.", "Clarisse, volta para a lista.",
]
SEM_O_NOME = [
    "Que horas são?", "Abre o navegador.", "Vou almoçar daqui a pouco.", "A reunião foi remarcada para amanhã.",
    "Clarice Lispector é uma escritora.", "A clareza do texto ficou boa.", "Essa classe tem um erro.",
    "A Clara chegou agora.", "Me passa o arquivo da planilha.", "Quanto ficou o boleto?", "O deploy terminou.",
    "Liga para o financeiro.", "Clareia um pouco a tela.", "Vamos conferir os números.", "Hoje está calor.",
    "A Carla mandou mensagem.", "Preciso revisar a PR.", "Fecha essa janela.", "O cliente respondeu o e-mail.",
    "Coloca uma música.",
]


def roteiro() -> list[tuple[str, str, str, float]]:
    """(arquivo, grupo, frase gravada, segundos)."""
    itens = [(f"nome-{i:02d}", "nome", "Clarisse", 3.0) for i in range(1, 21)]
    itens += [(f"pedido-{i:02d}", "pedido", frase, 4.5) for i, frase in enumerate(COM_PEDIDO, 1)]
    itens += [(f"normal-{i:02d}", "normal", frase, 4.5) for i, frase in enumerate(SEM_O_NOME, 1)]
    return itens


def instrucao(numero: int, grupo: str, frase: str) -> str:
    if grupo == "nome":
        return f"Diga Clarisse, {JEITOS[(numero - 1) % len(JEITOS)]}."
    return f"Repita: {frase}"


async def preparar_falas(itens) -> None:
    FALAS.mkdir(parents=True, exist_ok=True)
    for i, (arquivo, grupo, frase, _) in enumerate(itens, 1):
        destino = FALAS / f"{arquivo}.mp3"
        if not destino.exists():
            numero = int(arquivo.split("-")[1])
            await edge_tts.Communicate(instrucao(numero, grupo, frase), VOZ, rate="+0%").save(str(destino))
    for nome, texto in [("comeco", "Vamos gravar. Depois do bipe, fale. Outro bipe marca o fim."),
                        ("pausa", "Pausa. Rode de novo para continuar."), ("fim", "Pronto, terminamos. Obrigada!")]:
        destino = FALAS / f"{nome}.mp3"
        if not destino.exists():
            await edge_tts.Communicate(texto, VOZ).save(str(destino))


def tocar(caminho: Path | str) -> None:
    subprocess.run(["pw-play", str(caminho)], check=False)


def gravar(destino: Path, segundos: float) -> None:
    temporario = destino.with_suffix(".parcial.wav")
    processo = subprocess.Popen(["pw-record", "--rate", "16000", "--channels", "1", "--format", "s16", str(temporario)])
    time.sleep(segundos)
    processo.send_signal(signal.SIGINT)
    processo.wait(timeout=5)
    temporario.rename(destino)


def main() -> None:
    itens = roteiro()
    asyncio.run(preparar_falas(itens))
    lista = PASTA / "lista.csv"
    if not lista.exists():
        with lista.open("w", newline="", encoding="utf-8") as saida:
            csv.writer(saida).writerow(["arquivo", "grupo", "frase"])
    faltam = [item for item in itens if not (PASTA / f"{item[0]}.wav").exists()]
    if not faltam:
        print("Todas as 50 gravações já existem.")
        return
    tocar(FALAS / "comeco.mp3")
    try:
        for arquivo, grupo, frase, segundos in faltam:
            feitas = len(itens) - len(faltam) + 1
            print(f"\n\n  [{feitas}/{len(itens)}]   {instrucao(int(arquivo.split('-')[1]), grupo, frase).upper()}\n")
            tocar(FALAS / f"{arquivo}.mp3")
            time.sleep(0.3)
            tocar(BIPE_INICIO)
            gravar(PASTA / f"{arquivo}.wav", segundos)
            tocar(BIPE_FIM)
            with lista.open("a", newline="", encoding="utf-8") as saida:
                csv.writer(saida).writerow([arquivo, grupo, frase])
            faltam = faltam[1:]
            time.sleep(0.6)
    except KeyboardInterrupt:
        tocar(FALAS / "pausa.mp3")
        print("\n\n  Pausado. Rode o mesmo comando para continuar de onde parou.\n")
        sys.exit(0)
    tocar(FALAS / "fim.mp3")
    print("\n\n  Pronto: 50 gravações em dados/ativacao/. Avise o Claude.\n")


if __name__ == "__main__":
    main()
