"""As pecas do Ouvinte que encostam no hardware: o microfone e o motor.

Ficam fora do `servidor.py` de proposito. O `import faster_whisper` custa 1,51 s
medidos, e o protocolo do servidor e importado por testes e por quem so quer ler
o codigo — nenhum dos dois deve pagar esse pedagio. Aqui o import e adiado ate a
hora de carregar o modelo de verdade.

Os parametros da transcricao nao sao gosto: cada um saiu de uma medicao, e estao
fixados com teste para nao voltarem por descuido.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import numpy as np

TAXA = 16000  # o que o whisper espera; qualquer outra taxa custaria reamostragem
TAMANHO = 'small'
BLOCO = 1024


def abrir_motor(tamanho: str = TAMANHO, *, threads: int = 0) -> object:
    """Carrega o modelo. Sao ~6,8 s a frio nesta maquina, e 500 a 700 MB de RAM.

    `threads=0` deixa a escolha com a biblioteca. A medicao de 25/08 tentou fixar
    esse numero e nao conseguiu: o ruido da maquina variou 5,9x contra um efeito
    de threads de 0,5x, e as duas ordens de medida deram respostas opostas.
    Fixar um numero aqui seria registrar um artefato como decisao.
    """
    from faster_whisper import WhisperModel

    return WhisperModel(tamanho, device='cpu', compute_type='int8', cpu_threads=threads)


def transcrever(motor, onda: np.ndarray, *, dica: str) -> str:
    """Passa a fala ao motor com os parametros que a medicao escolheu.

    `condition_on_previous_text=False` nao e detalhe: com o texto recem-transcrito
    no contexto, o erro foi a 52,3% e o motor passou a repetir a mesma frase em
    laco (22/08/2026). A dica serve para vocabulario fixo — nome de projeto — e
    nada mais.
    """
    segmentos, _ = motor.transcribe(
        onda,
        language='pt',
        beam_size=1,
        vad_filter=False,
        condition_on_previous_text=False,
        initial_prompt=dica or None,
    )
    return sanear(''.join(s.text for s in segmentos))


def sanear(texto: str) -> str:
    """Deixa o texto em uma linha so, pronto para ser colado.

    A quebra de linha e o que importa: o texto vai para a janela em foco, e uma
    quebra de linha no prompt do Claude Code **envia** a mensagem. O Ouvinte
    digita para revisao e nunca envia — entao ela vira espaco aqui.
    """
    return re.sub(r'\s+', ' ', texto).strip()


class Gravador:
    """Acumula o que entra pelo microfone entre o `iniciar` e o `encerrar`."""

    def __init__(
        self,
        *,
        taxa: int = TAXA,
        abrir_fluxo: Callable[[int, Callable], object] | None = None,
    ) -> None:
        self.taxa = taxa
        self._abrir_fluxo = abrir_fluxo or _fluxo_do_microfone
        self._fluxo: object | None = None
        self._blocos: list[np.ndarray] = []

    def iniciar(self) -> None:
        self._blocos = []
        self._fluxo = self._abrir_fluxo(self.taxa, self._receber)
        self._fluxo.start()

    def encerrar(self) -> np.ndarray:
        fluxo, self._fluxo = self._fluxo, None
        if fluxo is not None:
            fluxo.stop()
            fluxo.close()

        blocos, self._blocos = self._blocos, []
        if not blocos:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(blocos).reshape(-1).astype(np.float32)

    def _receber(self, dados, _quadros, _tempo, _estado) -> None:
        """Chamado pelo PortAudio, em outra thread, a cada bloco de audio.

        A copia e obrigatoria: o buffer e reaproveitado a cada chamada, e guardar
        a referencia faria a fala inteira virar o ultimo bloco gravado.
        """
        self._blocos.append(np.array(dados, dtype=np.float32, copy=True))


def _fluxo_do_microfone(taxa: int, aviso: Callable) -> object:
    import sounddevice

    return sounddevice.InputStream(
        samplerate=taxa,
        channels=1,
        dtype='float32',
        blocksize=BLOCO,
        callback=aviso,
    )
