"""Mede se a transcrição já usada pela Clarisse (faster-whisper small, processador) serve de detector
da palavra "Clarisse", nas gravações de dados/ativacao/ (feitas com gravar.py).

Conta, por grupo, quantas transcrições trazem o nome: "nome" e "pedido" deveriam trazer todas
(acerto); "normal" não deveria trazer nenhuma (alarme falso). Compara sem dica e com a dica "Clarisse".

Rodar da pasta da Clarisse:  uv run python docs/medicoes/2026-10-01-palavra-de-ativacao/medir.py
"""
import csv
import re
import time
import unicodedata
from pathlib import Path

from faster_whisper import WhisperModel

PASTA = Path("dados/ativacao")
# Estrito: só a grafia do nome. Folgado: o que o Whisper costuma escrever no lugar (Clarice, Claris...).
ESTRITO = re.compile(r"\bclarisse\b")
FOLGADO = re.compile(r"\bclari(?:sse|se|ce|ss|s)\b")


def sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")


def main() -> None:
    with (PASTA / "lista.csv").open(encoding="utf-8") as entrada:
        itens = list(csv.DictReader(entrada))
    modelo = WhisperModel("small", device="cpu", compute_type="int8")
    linhas = []
    for dica in (None, "Clarisse"):
        tempos = []
        for item in itens:
            inicio = time.monotonic()
            segmentos, _ = modelo.transcribe(
                str(PASTA / f"{item['arquivo']}.wav"), language="pt", hotwords=dica, vad_filter=True, beam_size=5,
            )
            texto = " ".join(s.text.strip() for s in segmentos).strip()
            tempos.append(time.monotonic() - inicio)
            normal = sem_acento(texto)
            linhas.append({**item, "dica": dica or "-", "texto": texto,
                           "estrito": bool(ESTRITO.search(normal)), "folgado": bool(FOLGADO.search(normal))})
        print(f"\nDica {dica or '-'}: mediana {sorted(tempos)[len(tempos) // 2]:.2f} s por gravação")
        for grupo in ("nome", "pedido", "normal"):
            do_grupo = [l for l in linhas if l["dica"] == (dica or "-") and l["grupo"] == grupo]
            print(f"  {grupo:7s}  estrito {sum(l['estrito'] for l in do_grupo):2d}/{len(do_grupo)}"
                  f"   folgado {sum(l['folgado'] for l in do_grupo):2d}/{len(do_grupo)}")
    with (PASTA / "resultado.csv").open("w", newline="", encoding="utf-8") as saida:
        escritor = csv.DictWriter(saida, fieldnames=list(linhas[0]))
        escritor.writeheader()
        escritor.writerows(linhas)
    print("\nTranscrições em dados/ativacao/resultado.csv")


if __name__ == "__main__":
    main()
