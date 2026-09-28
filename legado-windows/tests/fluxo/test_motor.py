"""As pecas que encostam no hardware: o microfone e o motor de transcricao.

O que da para testar aqui e o contrato, nao o audio de verdade: o fluxo do
microfone e o modelo entram por injecao. A verificacao com voz real e manual,
contra as oito gravacoes de 21/08.

Os parametros da transcricao tem teste proprio porque cada um deles foi decidido
por medicao, e um deles ja custou caro: realimentar o texto recem-transcrito no
`initial_prompt` levou o erro a 52,3% com repeticao em laco.
"""

import numpy as np
import pytest

from clarisse.ouvinte.motor import Gravador, transcrever


class Segmento:
    def __init__(self, texto):
        self.text = texto


class MotorFalso:
    def __init__(self, segmentos=('bom dia',)):
        self.segmentos = segmentos
        self.chamadas = []

    def transcribe(self, onda, **parametros):
        self.chamadas.append({'onda': onda, **parametros})
        return (Segmento(t) for t in self.segmentos), None

    @property
    def parametros(self):
        return self.chamadas[-1]


class FluxoFalso:
    """Microfone de mentira: o teste empurra os blocos na mao."""

    def __init__(self, taxa, aviso):
        self.taxa = taxa
        self.aviso = aviso
        self.aberto = True
        self.rodando = False

    def start(self):
        self.rodando = True

    def stop(self):
        self.rodando = False

    def close(self):
        self.aberto = False

    def falar(self, bloco):
        self.aviso(bloco, len(bloco), None, None)


def gravador_de_mentira():
    fluxos = []

    def abrir_fluxo(taxa, aviso):
        fluxo = FluxoFalso(taxa, aviso)
        fluxos.append(fluxo)
        return fluxo

    return Gravador(abrir_fluxo=abrir_fluxo), fluxos


def bloco(valores):
    return np.array(valores, dtype=np.float32).reshape(-1, 1)


class TestTranscrever:
    def test_devolve_o_que_o_motor_ouviu(self):
        motor = MotorFalso(('abrir o relatorio',))

        assert transcrever(motor, bloco([0.1]), dica='') == 'abrir o relatorio'

    def test_junta_os_segmentos_numa_frase_so(self):
        motor = MotorFalso(('bom dia,', ' tudo certo'))

        assert transcrever(motor, bloco([0.1]), dica='') == 'bom dia, tudo certo'

    def test_devolve_vazio_quando_o_motor_nao_ouviu_nada(self):
        motor = MotorFalso(())

        assert transcrever(motor, bloco([0.1]), dica='') == ''

    def test_passa_a_dica_como_initial_prompt(self):
        motor = MotorFalso()

        transcrever(motor, bloco([0.1]), dica='Projetos: omni-api. Clarisse.')

        assert motor.parametros['initial_prompt'] == 'Projetos: omni-api. Clarisse.'

    def test_transcreve_em_portugues(self):
        motor = MotorFalso()

        transcrever(motor, bloco([0.1]), dica='')

        assert motor.parametros['language'] == 'pt'

    def test_nao_realimenta_o_texto_anterior(self):
        # Medido em 22/08: o texto recem-transcrito no contexto levou o erro a
        # 52,3% e o motor a repetir a mesma frase em laco.
        motor = MotorFalso()

        transcrever(motor, bloco([0.1]), dica='')

        assert motor.parametros['condition_on_previous_text'] is False

    def test_usa_a_busca_mais_barata(self):
        motor = MotorFalso()

        transcrever(motor, bloco([0.1]), dica='')

        assert motor.parametros['beam_size'] == 1

    def test_nao_gasta_tempo_procurando_silencio(self):
        # O corte de silencio ja e feito na gravacao; pagar de novo no motor so
        # somaria latencia ao que a medicao ja apontou como o gargalo.
        motor = MotorFalso()

        transcrever(motor, bloco([0.1]), dica='')

        assert motor.parametros['vad_filter'] is False


class TestGravador:
    def test_devolve_o_audio_que_entrou_pelo_microfone(self):
        microfone, fluxos = gravador_de_mentira()

        microfone.iniciar()
        fluxos[0].falar(bloco([0.1, 0.2]))
        fluxos[0].falar(bloco([0.3]))
        onda = microfone.encerrar()

        assert onda.tolist() == pytest.approx([0.1, 0.2, 0.3])

    def test_a_onda_sai_em_uma_dimensao_so(self):
        microfone, fluxos = gravador_de_mentira()

        microfone.iniciar()
        fluxos[0].falar(bloco([0.1, 0.2]))
        onda = microfone.encerrar()

        assert onda.ndim == 1

    def test_gravacao_sem_som_devolve_onda_vazia(self):
        microfone, _ = gravador_de_mentira()

        microfone.iniciar()

        assert len(microfone.encerrar()) == 0

    def test_encerrar_sem_ter_gravado_devolve_onda_vazia(self):
        microfone, _ = gravador_de_mentira()

        assert len(microfone.encerrar()) == 0

    def test_encerrar_fecha_o_microfone(self):
        microfone, fluxos = gravador_de_mentira()

        microfone.iniciar()
        microfone.encerrar()

        assert fluxos[0].rodando is False
        assert fluxos[0].aberto is False

    def test_guarda_uma_copia_do_bloco_recebido(self):
        # O PortAudio reaproveita o mesmo buffer a cada chamada. Guardar a
        # referencia em vez da copia faria a fala inteira virar o ultimo bloco.
        microfone, fluxos = gravador_de_mentira()

        microfone.iniciar()
        vivo = bloco([0.1, 0.2])
        fluxos[0].falar(vivo)
        vivo[:] = 0.9

        assert microfone.encerrar().tolist() == pytest.approx([0.1, 0.2])

    def test_cada_gravacao_comeca_do_zero(self):
        microfone, fluxos = gravador_de_mentira()
        microfone.iniciar()
        fluxos[0].falar(bloco([0.1]))
        microfone.encerrar()

        microfone.iniciar()
        fluxos[1].falar(bloco([0.5]))

        assert microfone.encerrar().tolist() == pytest.approx([0.5])

    def test_grava_na_taxa_que_o_motor_espera(self):
        microfone, fluxos = gravador_de_mentira()

        microfone.iniciar()

        assert fluxos[0].taxa == 16000
