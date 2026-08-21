"""Grava a sua voz dizendo as frases de teste, imitando o fluxo do F6.

Enter comeca a gravar, Enter para. Igual a tecla vai funcionar.

As gravacoes ficam salvas em WAV a 16 kHz, para eu poder testar quantas
configuracoes eu quiser depois sem voce precisar falar de novo.
"""

import json
import queue
import sys
import threading
import wave
from pathlib import Path

import numpy as np
import sounddevice as sd

AQUI = Path(__file__).parent
DESTINO = AQUI / "voz_real"
TAXA = 16000

FRASES = [
    ("omni", "Clarisse, o que está rolando no omni-api?"),
    ("compliance", "Clarisse, me conta o que aconteceu no compliance-app."),
    ("voz", "Clarisse, resume a última sessão do voz-ao-claude."),
    ("consultor", "Clarisse, como está o consultor-financeiro?"),
    ("testes", "Clarisse, roda os testes e me avisa quando terminar."),
    ("conciliacao", "Clarisse, quantos testes passaram na conciliação bancária?"),
    ("compara", "Clarisse, compara o omni-api com o compliance-app."),
    ("velocimetro", "Clarisse, o que falta no velocímetro de tokens?"),
]

REFERENCIAS = {
    "omni": "clarisse o que esta rolando no omni api",
    "compliance": "clarisse me conta o que aconteceu no compliance app",
    "voz": "clarisse resume a ultima sessao do voz ao claude",
    "consultor": "clarisse como esta o consultor financeiro",
    "testes": "clarisse roda os testes e me avisa quando terminar",
    "conciliacao": "clarisse quantos testes passaram na conciliacao bancaria",
    "compara": "clarisse compara o omni api com o compliance app",
    "velocimetro": "clarisse o que falta no velocimetro de tokens",
}


def grava_ate_enter() -> np.ndarray:
    """Grava do microfone padrao ate o usuario apertar Enter de novo."""
    pedacos: queue.Queue = queue.Queue()
    parar = threading.Event()

    def entra(dados, frames, tempo, status):
        if status:
            print(f"  (aviso do audio: {status})", file=sys.stderr)
        pedacos.put(dados.copy())

    def espera_enter():
        input()
        parar.set()

    threading.Thread(target=espera_enter, daemon=True).start()

    with sd.InputStream(samplerate=TAXA, channels=1, dtype="float32", callback=entra):
        while not parar.is_set():
            sd.sleep(50)

    blocos = []
    while not pedacos.empty():
        blocos.append(pedacos.get())
    if not blocos:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(blocos).flatten()


def salva_wav(caminho: Path, onda: np.ndarray) -> None:
    pcm = (np.clip(onda, -1.0, 1.0) * 32767).astype(np.int16)
    with wave.open(str(caminho), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes(pcm.tobytes())


def nivel(onda: np.ndarray) -> str:
    """Aviso na hora se o microfone captou baixo ou estourou."""
    if onda.size == 0:
        return "NADA GRAVADO"
    pico = float(np.max(np.abs(onda)))
    rms = float(np.sqrt(np.mean(onda ** 2)))
    if pico >= 0.99:
        return f"ESTOUROU (pico {pico:.2f}) - fale mais longe do microfone"
    if rms < 0.005:
        return f"MUITO BAIXO (rms {rms:.4f}) - fale mais perto ou aumente o ganho"
    return f"ok (pico {pico:.2f}, rms {rms:.3f})"


def principal() -> None:
    DESTINO.mkdir(exist_ok=True)
    dispositivo = sd.query_devices(sd.default.device[0])

    print("=" * 70)
    print("  GRAVACAO DAS FRASES DE TESTE")
    print("=" * 70)
    print(f"\nMicrofone: {dispositivo['name']}")
    print(f"Frases: {len(FRASES)}")
    print("\nComo funciona, igual a tecla vai funcionar:")
    print("  1. A frase aparece na tela")
    print("  2. Aperte Enter e fale a frase")
    print("  3. Aperte Enter de novo quando terminar de falar")
    print("\nFale no seu ritmo normal, do jeito que voce falaria de verdade.")
    print("Se errar, digite 'r' e Enter para regravar a mesma frase.")
    print("Para parar no meio, digite 's' e Enter.\n")
    input("Aperte Enter para comecar... ")

    gravadas = 0
    for i, (chave, texto) in enumerate(FRASES, start=1):
        while True:
            print("\n" + "-" * 70)
            print(f"[{i}/{len(FRASES)}]  Fale:  {texto}")
            resposta = input("       Enter grava  |  s = sair  >>> ").strip().lower()
            if resposta == "s":
                print("\nParando aqui.")
                print(f"{gravadas} frases gravadas em {DESTINO}")
                return

            print("       GRAVANDO... fale agora, e aperte Enter ao terminar.")
            onda = grava_ate_enter()
            duracao = onda.size / TAXA
            estado = nivel(onda)
            print(f"       {duracao:.1f}s  |  {estado}")

            if onda.size == 0:
                print("       Nada foi gravado. Vamos tentar de novo.")
                continue

            de_novo = input("       Enter aceita  |  r = regravar  >>> ").strip().lower()
            if de_novo == "r":
                continue

            salva_wav(DESTINO / f"{chave}.wav", onda)
            gravadas += 1
            break

    (DESTINO / "referencias.json").write_text(
        json.dumps(REFERENCIAS, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("\n" + "=" * 70)
    print(f"Pronto. {gravadas} frases gravadas em {DESTINO}")
    print("Agora me avise que eu rodo a medicao.")


if __name__ == "__main__":
    principal()
