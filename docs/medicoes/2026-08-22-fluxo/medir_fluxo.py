"""Mede a transcricao em fluxo: quanto da espera de 2,74 s desaparece se o motor
trabalhar enquanto o usuario ainda fala.

A pergunta e uma so. Ao soltar a tecla, o que ainda falta transcrever? Na medicao
de 21/08 faltava o audio inteiro. Aqui o audio e fechado em trechos durante a
fala, e ao soltar a tecla so falta o ultimo pedaco.

Usa as mesmas oito gravacoes da voz real de 21/08, a mesma dica, o mesmo motor e
a mesma normalizacao, para os numeros serem comparaveis linha a linha.

O relogio e contabil, nao dormido: mede-se de verdade quanto cada trecho custa
para transcrever, e depois se calcula quando cada um teria terminado num worker
que atende um trecho por vez.

    disponivel_i = fechado_em do corte
    inicio_i     = max(disponivel_i, fim_{i-1})
    fim_i        = inicio_i + custo_i
    espera       = max(0, fim_ultimo - duracao_da_fala)

O que este metodo NAO captura: o whisper usa oito threads, entao transcrever
durante a fala disputa CPU com as outras sessoes abertas. O trabalho total de CPU
esta na tabela para isso ficar visivel.
"""

from __future__ import annotations

import json
import re
import statistics
import sys
import time
import unicodedata
import wave
from pathlib import Path

import jiwer
import numpy as np
from faster_whisper import WhisperModel

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))

from clarisse.ouvinte.cortador import (  # noqa: E402
    Corte,
    cortes_por_silencio,
    cortes_por_tempo,
)

AQUI = Path(__file__).parent
VOZ = Path.home() / ".claude" / "clarisse" / "medicoes" / "voz_real"
TAXA = 16000
THREADS = 8
MODELO = "small"

DICA = ("Projetos: omni-api, compliance-app, voz-ao-claude, consultor-financeiro, "
        "conciliacao-bancaria, velocimetro-tokens, cadeia-sequencial. Clarisse.")


def um_bloco(onda: np.ndarray, taxa: int) -> list[Corte]:
    """O que a medicao de 21/08 fez: nada e transcrito antes de soltar a tecla."""
    return [Corte(0, len(onda), len(onda) / taxa)]


ESTRATEGIAS = [
    ("bloco (21/08)", um_bloco, False),
    ("silencio 400ms", lambda o, t: cortes_por_silencio(o, t, silencio_ms=400), False),
    ("tempo 2,0s", lambda o, t: cortes_por_tempo(o, t, janela_s=2.0), False),
    ("tempo 2,0s + contexto", lambda o, t: cortes_por_tempo(o, t, janela_s=2.0), True),
    ("tempo 1,5s", lambda o, t: cortes_por_tempo(o, t, janela_s=1.5), False),
]


def normaliza(texto: str) -> str:
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", sem_acento.lower())).strip()


def le_wav(caminho: Path) -> np.ndarray:
    with wave.open(str(caminho), "rb") as w:
        bruto = w.readframes(w.getnframes())
    return np.frombuffer(bruto, dtype=np.int16).astype(np.float32) / 32768.0


def transcreve(modelo: WhisperModel, trecho: np.ndarray, dica: str) -> tuple[str, float]:
    inicio = time.perf_counter()
    segmentos, _ = modelo.transcribe(
        trecho,
        language="pt",
        beam_size=1,
        vad_filter=False,
        condition_on_previous_text=False,
        initial_prompt=dica,
    )
    texto = " ".join(s.text for s in segmentos)
    return texto, time.perf_counter() - inicio


def roda_frase(
    modelo: WhisperModel,
    onda: np.ndarray,
    cortes: list[Corte],
    com_contexto: bool,
) -> dict:
    """Devolve o texto costurado e a espera depois de soltar a tecla."""
    duracao = len(onda) / TAXA
    partes: list[str] = []
    livre_em = 0.0
    trabalho = 0.0

    for corte in cortes:
        dica = DICA
        if com_contexto and partes:
            dica = f"{DICA} {' '.join(partes).strip()}"

        texto, custo = transcreve(modelo, onda[corte.inicio:corte.fim], dica)
        partes.append(texto.strip())
        trabalho += custo

        inicio = max(corte.fechado_em, livre_em)
        livre_em = inicio + custo

    return {
        "texto": " ".join(partes).strip(),
        "espera": max(0.0, livre_em - duracao),
        "trabalho": trabalho,
        "idas": len(cortes),
    }


def principal() -> None:
    if not VOZ.exists():
        print(f"Nao achei as gravacoes em {VOZ}")
        return

    referencias = json.loads((VOZ / "referencias.json").read_text(encoding="utf-8"))
    ondas = {p.stem: le_wav(p) for p in sorted(VOZ.glob("*.wav"))}
    duracoes = {k: len(o) / TAXA for k, o in ondas.items()}

    print(f"{len(ondas)} frases da voz real, {sum(duracoes.values()):.1f}s de audio")
    print(f"motor {MODELO}, int8, {THREADS} threads, com dica\n")

    modelo = WhisperModel(MODELO, device="cpu", compute_type="int8", cpu_threads=THREADS)
    transcreve(modelo, next(iter(ondas.values())), DICA)  # passada fria descartada

    resumo = []
    for rotulo, cortar, com_contexto in ESTRATEGIAS:
        print(f"--- {rotulo} ---")
        esperas, trabalhos, idas, refs, hips = [], [], [], [], []

        for chave, onda in ondas.items():
            cortes = cortar(onda, TAXA)
            saida = roda_frase(modelo, onda, cortes, com_contexto)

            ref = normaliza(referencias.get(chave, ""))
            hip = normaliza(saida["texto"])
            refs.append(ref)
            hips.append(hip)
            esperas.append(saida["espera"])
            trabalhos.append(saida["trabalho"])
            idas.append(saida["idas"])

            erro = jiwer.wer(ref, hip) if ref else float("nan")
            print(f"  {chave:12} falou {duracoes[chave]:4.1f}s | {saida['idas']} trecho(s)"
                  f" | esperou {saida['espera']:5.2f}s | erro {erro * 100:5.1f}%")
            print(f"               -> {hip}")

        resumo.append({
            "estrategia": rotulo,
            "espera_mediana": statistics.median(esperas),
            "espera_pior": max(esperas),
            "wer": jiwer.wer(refs, hips),
            "trabalho_total": sum(trabalhos),
            "idas_medianas": statistics.median(idas),
        })
        print()

    largura = 96
    print("=" * largura)
    print(f"{'estrategia':24}{'espera mediana':>15}{'pior':>9}{'erro palavra':>14}"
          f"{'trabalho CPU':>14}{'trechos':>9}")
    print("=" * largura)
    for r in resumo:
        print(f"{r['estrategia']:24}{r['espera_mediana']:14.2f}s{r['espera_pior']:8.2f}s"
              f"{r['wer'] * 100:13.1f}%{r['trabalho_total']:13.1f}s"
              f"{r['idas_medianas']:9.0f}")
    print("=" * largura)
    print("\n'espera' e o tempo entre soltar a tecla e o texto estar pronto.")
    print("'trabalho CPU' e a soma de tudo que o motor moeu nas oito frases.")

    (AQUI / "resultado.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
    print("Detalhe salvo em resultado.json")


if __name__ == "__main__":
    principal()
