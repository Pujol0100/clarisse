"""O cortador decide, enquanto o usuario ainda fala, qual trecho ja pode ser
transcrito. O que importa em cada corte e o `fechado_em`: o instante, contado do
inicio da fala, em que aquele trecho ficou disponivel. Trecho que so fecha no fim
do audio nao adianta nada, porque e exatamente o que a medicao de 21/08 ja fez.
"""

import numpy as np
import pytest

from clarisse.ouvinte.cortador import cortes_por_silencio, cortes_por_tempo

TAXA = 16000


def fala(segundos: float, amplitude: float = 0.3) -> np.ndarray:
    """Sinal audivel: ruido com amplitude bem acima do limiar."""
    gerador = np.random.default_rng(1234)
    return gerador.normal(0.0, amplitude, int(segundos * TAXA)).astype(np.float32)


def silencio(segundos: float) -> np.ndarray:
    return np.zeros(int(segundos * TAXA), dtype=np.float32)


class TestCortesPorSilencio:
    def test_audio_todo_silencioso_nao_gera_corte(self):
        assert cortes_por_silencio(silencio(3.0), TAXA) == []

    def test_fala_sem_pausa_gera_um_corte_que_so_fecha_no_fim(self):
        onda = fala(4.0)

        cortes = cortes_por_silencio(onda, TAXA)

        assert len(cortes) == 1
        assert cortes[0].fechado_em == pytest.approx(4.0, abs=0.1)

    def test_pausa_longa_fecha_o_primeiro_trecho_antes_do_fim_da_fala(self):
        onda = np.concatenate([fala(2.0), silencio(0.8), fala(2.0)])

        cortes = cortes_por_silencio(onda, TAXA, silencio_ms=400)

        assert len(cortes) == 2
        assert cortes[0].fechado_em == pytest.approx(2.4, abs=0.15)
        assert cortes[1].fechado_em == pytest.approx(4.8, abs=0.15)

    def test_pausa_curta_nao_corta(self):
        onda = np.concatenate([fala(1.5), silencio(0.2), fala(1.5)])

        cortes = cortes_por_silencio(onda, TAXA, silencio_ms=400)

        assert len(cortes) == 1

    def test_trecho_menor_que_o_minimo_nao_fecha_sozinho(self):
        onda = np.concatenate([fala(0.4), silencio(0.8), fala(2.0)])

        cortes = cortes_por_silencio(onda, TAXA, silencio_ms=400, minimo_s=1.0)

        assert len(cortes) == 1

    def test_cortes_saem_em_ordem_e_sem_sobreposicao(self):
        onda = np.concatenate(
            [fala(1.5), silencio(0.6), fala(1.5), silencio(0.6), fala(1.5)]
        )

        cortes = cortes_por_silencio(onda, TAXA, silencio_ms=400)

        assert len(cortes) == 3
        for anterior, seguinte in zip(cortes, cortes[1:]):
            assert anterior.fim <= seguinte.inicio
            assert anterior.fechado_em < seguinte.fechado_em


class TestCortesPorTempo:
    def test_janela_fixa_fecha_a_cada_janela(self):
        cortes = cortes_por_tempo(fala(5.0), TAXA, janela_s=2.0)

        assert [round(c.fechado_em, 2) for c in cortes] == [2.0, 4.0, 5.0]

    def test_ultimo_trecho_curto_e_absorvido_pelo_anterior(self):
        cortes = cortes_por_tempo(fala(4.2), TAXA, janela_s=2.0, minimo_s=0.5)

        assert [round(c.fechado_em, 2) for c in cortes] == [2.0, 4.2]

    def test_audio_menor_que_a_janela_gera_um_corte_no_fim(self):
        cortes = cortes_por_tempo(fala(1.2), TAXA, janela_s=2.0)

        assert len(cortes) == 1
        assert cortes[0].fechado_em == pytest.approx(1.2, abs=0.01)

    def test_os_cortes_cobrem_o_audio_inteiro(self):
        onda = fala(5.0)

        cortes = cortes_por_tempo(onda, TAXA, janela_s=2.0)

        assert cortes[0].inicio == 0
        assert cortes[-1].fim == len(onda)
        for anterior, seguinte in zip(cortes, cortes[1:]):
            assert anterior.fim == seguinte.inicio
