"""O servidor residente carrega o modelo uma vez e espera pedido.

O que estes testes fixam e o protocolo, nao o audio: o motor, o microfone e a
transcricao entram por injecao. A regra que mais custou ao projeto esta aqui — o
sinal de pronto so aparece depois do texto estar fechado, porque arquivo em
escrita e lido pela metade.

A tecla alterna: um `gravar` abre a fala, um `parar` fecha. Nao ha comando unico
porque o `RegisterHotKey` do Windows so avisa quando a tecla desce, e sem evento
de subida nao existe "segurar para falar".
"""

import json
import os

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


class GravadorFalso:
    """Microfone de mentira. A onda e opaca para o servidor: so o tamanho conta."""

    def __init__(self, onda='ondinha'):
        self.onda = onda
        self.iniciou = 0
        self.encerrou = 0

    def iniciar(self) -> None:
        self.iniciou += 1

    def encerrar(self):
        self.encerrou += 1
        return self.onda


def montar(pasta, texto='bom dia', gravador=None, **extras):
    """Servidor de mentira que conta quantas vezes o motor foi aberto."""
    aberturas = []

    def abrir_motor():
        motor = object()
        aberturas.append(motor)
        return motor

    def transcrever(_motor, onda):
        return texto(onda) if callable(texto) else texto

    criado = Servidor(
        pasta,
        abrir_motor=abrir_motor,
        gravador=gravador or GravadorFalso(),
        transcrever=transcrever,
        **extras,
    )
    return criado, aberturas


def pedir(pasta, comando):
    (pasta / 'comando.txt').write_text(comando, encoding='utf-8')


def ditar(atendente, pasta):
    """A rodada inteira: aperta, fala, aperta de novo."""
    pedir(pasta, 'gravar')
    atendente.passo()
    pedir(pasta, 'parar')
    atendente.passo()


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
    def test_gravar_abre_o_microfone_e_nao_responde_nada_ainda(self, tmp_path):
        microfone = GravadorFalso()
        atendente, _ = montar(tmp_path, gravador=microfone)

        pedir(tmp_path, 'gravar')
        atendente.passo()

        assert microfone.iniciou == 1
        assert not (tmp_path / 'pronto.flag').exists()

    def test_o_motor_carrega_enquanto_o_usuario_ainda_fala(self, tmp_path):
        atendente, aberturas = montar(tmp_path)

        pedir(tmp_path, 'gravar')
        atendente.passo()

        assert len(aberturas) == 1

    def test_parar_devolve_o_texto_e_levanta_o_sinal(self, tmp_path):
        atendente, _ = montar(tmp_path, texto='abrir o relatorio')

        ditar(atendente, tmp_path)

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

        ditar(atendente, tmp_path)

        # O sinal e sempre o ultimo, e agora ele cobre os dois arquivos de
        # resposta: quem le o sinal encontra texto e medida ja fechados.
        assert ordem == ['texto.txt', 'medida.json', 'pronto.flag']

    def test_o_pedido_e_consumido(self, tmp_path):
        atendente, _ = montar(tmp_path)

        pedir(tmp_path, 'gravar')
        atendente.passo()

        assert not (tmp_path / 'comando.txt').exists()

    def test_sem_pedido_o_microfone_nem_abre(self, tmp_path):
        microfone = GravadorFalso()
        atendente, aberturas = montar(tmp_path, gravador=microfone)

        atendente.passo()

        assert microfone.iniciou == 0
        assert aberturas == []

    def test_parar_sem_gravar_antes_nao_faz_nada(self, tmp_path):
        microfone = GravadorFalso()
        atendente, _ = montar(tmp_path, gravador=microfone)

        pedir(tmp_path, 'parar')
        atendente.passo()

        assert microfone.encerrou == 0
        assert not (tmp_path / 'pronto.flag').exists()

    def test_gravar_duas_vezes_nao_reinicia_a_gravacao(self, tmp_path):
        microfone = GravadorFalso()
        atendente, _ = montar(tmp_path, gravador=microfone)

        pedir(tmp_path, 'gravar')
        atendente.passo()
        pedir(tmp_path, 'gravar')
        atendente.passo()

        assert microfone.iniciou == 1

    def test_texto_vazio_nao_levanta_o_sinal(self, tmp_path):
        atendente, _ = montar(tmp_path, texto='')

        ditar(atendente, tmp_path)

        assert not (tmp_path / 'pronto.flag').exists()
        assert not (tmp_path / 'texto.txt').exists()

    def test_gravacao_sem_audio_nao_chega_ao_motor(self, tmp_path):
        def nunca(_onda):
            raise AssertionError('o motor nao devia ser chamado com onda vazia')

        atendente, _ = montar(tmp_path, texto=nunca, gravador=GravadorFalso(onda=''))

        ditar(atendente, tmp_path)

        assert not (tmp_path / 'pronto.flag').exists()

    def test_comando_desconhecido_nao_derruba_o_servidor(self, tmp_path):
        atendente, _ = montar(tmp_path, texto='dois')

        pedir(tmp_path, 'dancar')
        atendente.passo()
        assert not (tmp_path / 'pronto.flag').exists()

        ditar(atendente, tmp_path)

        assert (tmp_path / 'texto.txt').read_text(encoding='utf-8') == 'dois'

    def test_a_transcricao_que_estoura_nao_derruba_o_servidor(self, tmp_path):
        def explodir(_onda):
            raise RuntimeError('motor engasgou')

        atendente, _ = montar(tmp_path, texto=explodir)

        ditar(atendente, tmp_path)

        assert not (tmp_path / 'pronto.flag').exists()

    def test_depois_de_um_erro_o_servidor_aceita_nova_gravacao(self, tmp_path):
        falhas = []

        def falhar_uma_vez(_onda):
            if not falhas:
                falhas.append(1)
                raise RuntimeError('motor engasgou')
            return 'segunda tentativa'

        atendente, _ = montar(tmp_path, texto=falhar_uma_vez)
        ditar(atendente, tmp_path)

        ditar(atendente, tmp_path)

        assert (tmp_path / 'texto.txt').read_text(encoding='utf-8') == 'segunda tentativa'

    def test_o_erro_fica_registrado(self, tmp_path):
        anotado = []

        def explodir(_onda):
            raise RuntimeError('motor engasgou')

        atendente, _ = montar(tmp_path, texto=explodir, registrar=anotado.append)

        ditar(atendente, tmp_path)

        assert any('motor engasgou' in linha for linha in anotado)

    def test_a_resposta_anterior_cai_quando_uma_nova_fala_comeca(self, tmp_path):
        atendente, _ = montar(tmp_path)
        (tmp_path / 'pronto.flag').write_text('', encoding='utf-8')
        (tmp_path / 'texto.txt').write_text('velho', encoding='utf-8')

        pedir(tmp_path, 'gravar')
        atendente.passo()

        assert not (tmp_path / 'pronto.flag').exists()
        assert not (tmp_path / 'texto.txt').exists()


class TestOcio:
    def test_o_motor_abre_uma_vez_e_serve_as_falas_seguintes(self, tmp_path):
        atendente, aberturas = montar(tmp_path)

        for _ in range(3):
            ditar(atendente, tmp_path)

        assert len(aberturas) == 1

    def test_ocio_alem_do_limite_descarrega_o_motor(self, tmp_path):
        relogio = Relogio()
        atendente, _ = montar(tmp_path, ocioso_s=900, relogio=relogio)
        ditar(atendente, tmp_path)
        assert atendente.motor_carregado

        relogio.avancar(901)
        atendente.passo()

        assert not atendente.motor_carregado

    def test_ocio_dentro_do_limite_mantem_o_motor(self, tmp_path):
        relogio = Relogio()
        atendente, _ = montar(tmp_path, ocioso_s=900, relogio=relogio)
        ditar(atendente, tmp_path)

        relogio.avancar(899)
        atendente.passo()

        assert atendente.motor_carregado

    def test_fala_atendida_reinicia_a_contagem_do_ocio(self, tmp_path):
        relogio = Relogio()
        atendente, _ = montar(tmp_path, ocioso_s=900, relogio=relogio)
        ditar(atendente, tmp_path)

        relogio.avancar(800)
        ditar(atendente, tmp_path)
        relogio.avancar(800)
        atendente.passo()

        assert atendente.motor_carregado

    def test_gravacao_em_andamento_impede_a_descarga(self, tmp_path):
        relogio = Relogio()
        atendente, _ = montar(tmp_path, ocioso_s=900, relogio=relogio)
        pedir(tmp_path, 'gravar')
        atendente.passo()

        relogio.avancar(5000)
        atendente.passo()

        assert atendente.motor_carregado

    def test_depois_de_descarregar_o_servidor_continua_atendendo(self, tmp_path):
        relogio = Relogio()
        atendente, aberturas = montar(
            tmp_path, texto='de novo', ocioso_s=900, relogio=relogio
        )
        ditar(atendente, tmp_path)
        relogio.avancar(901)
        atendente.passo()

        ditar(atendente, tmp_path)

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
        pedir(tmp_path, 'gravar')
        voltas = []

        def parar():
            voltas.append(1)
            if len(voltas) == 2:
                pedir(tmp_path, 'parar')
            return len(voltas) > 3

        atendente.rodar(intervalo_s=0, parar=parar)

        assert (tmp_path / 'texto.txt').read_text(encoding='utf-8') == 'ate aqui'
        assert len(voltas) == 4


class TestMedida:
    """O servidor e o unico que sabe quanto durou o audio e a transcricao.

    Sem esses dois numeros o ditado nao tem como ser medido depois: a latencia
    de quem solta a tecla e espera o texto so existe aqui dentro.
    """

    def test_a_medida_sai_junto_com_o_texto(self, tmp_path):
        relogio = Relogio()
        atendente, _ = montar(
            tmp_path,
            texto=lambda _onda: (relogio.avancar(3.1), 'bom dia')[1],
            gravador=GravadorFalso(onda=[0.0] * 32000),
            relogio=relogio,
        )

        ditar(atendente, tmp_path)

        medida = json.loads((tmp_path / 'medida.json').read_text(encoding='utf-8'))
        assert medida['segundos_audio'] == 2.0
        assert medida['segundos_transcricao'] == 3.1

    def test_a_medida_esta_pronta_antes_do_sinal(self, tmp_path):
        atendente, _ = montar(tmp_path, gravador=GravadorFalso(onda=[0.0] * 16000))

        ditar(atendente, tmp_path)

        assert (tmp_path / 'pronto.flag').exists()
        assert (tmp_path / 'medida.json').exists()

    def test_transcricao_sem_texto_nao_deixa_medida(self, tmp_path):
        atendente, _ = montar(
            tmp_path, texto='', gravador=GravadorFalso(onda=[0.0] * 16000)
        )

        ditar(atendente, tmp_path)

        assert not (tmp_path / 'medida.json').exists()

    def test_gravar_de_novo_apaga_a_medida_anterior(self, tmp_path):
        (tmp_path / 'medida.json').write_text('{"segundos_audio": 99}', encoding='utf-8')
        atendente, _ = montar(tmp_path)

        pedir(tmp_path, 'gravar')
        atendente.passo()

        assert not (tmp_path / 'medida.json').exists()
