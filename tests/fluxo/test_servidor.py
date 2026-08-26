"""O servidor residente carrega o modelo uma vez e espera pedido.

O que estes testes fixam e o protocolo, nao o audio: o motor e a gravacao entram
por injecao. A regra que mais custou ao projeto esta aqui — o sinal de pronto so
aparece depois do texto estar fechado, porque arquivo em escrita e lido pela
metade.
"""

import os

import pytest

from clarisse.ouvinte import servidor as modulo
from clarisse.ouvinte.servidor import Servidor, processo_vivo, travar


class Relogio:
    """Relogio de mentira: so anda quando o teste manda."""

    def __init__(self):
        self.agora = 0.0

    def __call__(self) -> float:
        return self.agora

    def avancar(self, segundos: float) -> None:
        self.agora += segundos


def montar(pasta, texto='bom dia', **extras):
    """Servidor com motor e ditado de mentira, contando quantas vezes abriu."""
    aberturas = []

    def abrir_motor():
        motor = object()
        aberturas.append(motor)
        return motor

    def ditar(motor):
        return texto(motor) if callable(texto) else texto

    criado = Servidor(pasta, abrir_motor=abrir_motor, ditar=ditar, **extras)
    return criado, aberturas


def pedir(pasta, comando='ditar'):
    (pasta / 'comando.txt').write_text(comando, encoding='utf-8')


class TestTrava:
    def test_sobe_quando_nao_ha_arquivo_de_pid(self, tmp_path):
        assert travar(tmp_path, pid=4242, vivo=lambda _: False) is True
        assert (tmp_path / 'servidor.pid').read_text(encoding='utf-8') == '4242'

    def test_pid_de_processo_vivo_impede_a_subida(self, tmp_path):
        (tmp_path / 'servidor.pid').write_text('111', encoding='utf-8')

        assert travar(tmp_path, pid=222, vivo=lambda pid: pid == 111) is False
        assert (tmp_path / 'servidor.pid').read_text(encoding='utf-8') == '111'

    def test_pid_de_processo_morto_nao_impede_a_subida(self, tmp_path):
        (tmp_path / 'servidor.pid').write_text('111', encoding='utf-8')

        assert travar(tmp_path, pid=222, vivo=lambda _: False) is True
        assert (tmp_path / 'servidor.pid').read_text(encoding='utf-8') == '222'

    def test_arquivo_de_pid_ilegivel_nao_impede_a_subida(self, tmp_path):
        (tmp_path / 'servidor.pid').write_text('lixo', encoding='utf-8')

        assert travar(tmp_path, pid=222, vivo=lambda _: True) is True

    def test_a_pasta_e_criada_se_nao_existir(self, tmp_path):
        pasta = tmp_path / 'ouvinte'

        assert travar(pasta, pid=1, vivo=lambda _: False) is True
        assert (pasta / 'servidor.pid').exists()


class TestProcessoVivo:
    def test_reconhece_o_proprio_processo(self):
        assert processo_vivo(os.getpid()) is True

    def test_nega_pid_que_nao_existe(self):
        assert processo_vivo(999_999_999) is False


class TestProtocolo:
    def test_o_pedido_de_ditado_devolve_o_texto_e_levanta_o_sinal(self, tmp_path):
        atendente, _ = montar(tmp_path, texto='abrir o relatorio')
        pedir(tmp_path)

        atendente.passo()

        assert (tmp_path / 'texto.txt').read_text(encoding='utf-8') == 'abrir o relatorio'
        assert (tmp_path / 'pronto.flag').exists()

    def test_o_sinal_so_aparece_depois_do_texto_fechado(self, tmp_path, monkeypatch):
        ordem = []
        original = modulo.escrever

        def espiao(caminho, conteudo):
            original(caminho, conteudo)
            ordem.append(caminho.name)

        monkeypatch.setattr(modulo, 'escrever', espiao)
        atendente, _ = montar(tmp_path)
        pedir(tmp_path)

        atendente.passo()

        assert ordem == ['texto.txt', 'pronto.flag']

    def test_o_pedido_e_consumido(self, tmp_path):
        atendente, _ = montar(tmp_path)
        pedir(tmp_path)

        atendente.passo()

        assert not (tmp_path / 'comando.txt').exists()

    def test_sem_pedido_o_motor_nem_abre(self, tmp_path):
        atendente, aberturas = montar(tmp_path)

        atendente.passo()

        assert aberturas == []
        assert not (tmp_path / 'pronto.flag').exists()

    def test_texto_vazio_nao_levanta_o_sinal(self, tmp_path):
        atendente, _ = montar(tmp_path, texto='')
        pedir(tmp_path)

        atendente.passo()

        assert not (tmp_path / 'pronto.flag').exists()
        assert not (tmp_path / 'texto.txt').exists()

    def test_comando_desconhecido_nao_derruba_o_servidor(self, tmp_path):
        atendente, _ = montar(tmp_path, texto='dois')
        pedir(tmp_path, 'dancar')

        atendente.passo()

        assert not (tmp_path / 'pronto.flag').exists()

        pedir(tmp_path, 'ditar')
        atendente.passo()

        assert (tmp_path / 'texto.txt').read_text(encoding='utf-8') == 'dois'

    def test_o_ditado_que_estoura_nao_derruba_o_servidor(self, tmp_path):
        def explodir(_motor):
            raise RuntimeError('microfone ocupado')

        atendente, _ = montar(tmp_path, texto=explodir)
        pedir(tmp_path)

        atendente.passo()

        assert not (tmp_path / 'pronto.flag').exists()
        assert not (tmp_path / 'comando.txt').exists()

    def test_o_sinal_da_rodada_anterior_nao_sobrevive_ao_novo_pedido(self, tmp_path):
        atendente, _ = montar(tmp_path, texto='')
        (tmp_path / 'pronto.flag').write_text('', encoding='utf-8')
        (tmp_path / 'texto.txt').write_text('velho', encoding='utf-8')
        pedir(tmp_path)

        atendente.passo()

        assert not (tmp_path / 'pronto.flag').exists()
        assert not (tmp_path / 'texto.txt').exists()

    def test_o_erro_do_ditado_fica_registrado(self, tmp_path):
        anotado = []

        def explodir(_motor):
            raise RuntimeError('microfone ocupado')

        atendente, _ = montar(tmp_path, texto=explodir, registrar=anotado.append)
        pedir(tmp_path)

        atendente.passo()

        assert any('microfone ocupado' in linha for linha in anotado)


class TestOcio:
    def test_o_motor_abre_uma_vez_e_serve_os_pedidos_seguintes(self, tmp_path):
        atendente, aberturas = montar(tmp_path)

        for _ in range(3):
            pedir(tmp_path)
            atendente.passo()

        assert len(aberturas) == 1

    def test_ocio_alem_do_limite_descarrega_o_motor(self, tmp_path):
        relogio = Relogio()
        atendente, _ = montar(tmp_path, ocioso_s=900, relogio=relogio)
        pedir(tmp_path)
        atendente.passo()
        assert atendente.motor_carregado

        relogio.avancar(901)
        atendente.passo()

        assert not atendente.motor_carregado

    def test_ocio_dentro_do_limite_mantem_o_motor(self, tmp_path):
        relogio = Relogio()
        atendente, _ = montar(tmp_path, ocioso_s=900, relogio=relogio)
        pedir(tmp_path)
        atendente.passo()

        relogio.avancar(899)
        atendente.passo()

        assert atendente.motor_carregado

    def test_pedido_atendido_reinicia_a_contagem_do_ocio(self, tmp_path):
        relogio = Relogio()
        atendente, _ = montar(tmp_path, ocioso_s=900, relogio=relogio)
        pedir(tmp_path)
        atendente.passo()

        relogio.avancar(800)
        pedir(tmp_path)
        atendente.passo()
        relogio.avancar(800)
        atendente.passo()

        assert atendente.motor_carregado

    def test_depois_de_descarregar_o_servidor_continua_atendendo(self, tmp_path):
        relogio = Relogio()
        atendente, aberturas = montar(tmp_path, texto='de novo', ocioso_s=900, relogio=relogio)
        pedir(tmp_path)
        atendente.passo()
        relogio.avancar(901)
        atendente.passo()

        pedir(tmp_path)
        atendente.passo()

        assert (tmp_path / 'texto.txt').read_text(encoding='utf-8') == 'de novo'
        assert len(aberturas) == 2

    def test_servidor_que_nunca_ditou_nao_quebra_no_ocio(self, tmp_path):
        relogio = Relogio()
        atendente, aberturas = montar(tmp_path, ocioso_s=900, relogio=relogio)

        relogio.avancar(5000)
        atendente.passo()

        assert aberturas == []


class TestLaco:
    def test_o_laco_atende_ate_mandarem_parar(self, tmp_path):
        atendente, _ = montar(tmp_path, texto='ate aqui')
        pedir(tmp_path)
        voltas = []

        def parar():
            voltas.append(1)
            return len(voltas) > 3

        atendente.rodar(intervalo_s=0, parar=parar)

        assert (tmp_path / 'pronto.flag').exists()
        assert len(voltas) == 4
