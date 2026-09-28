"""A conta que decide o desenho do Agente.

O analisador do diario nao e codigo de producao — ele mora com as outras
medicoes. Mas a conta dele decide se a voz vai poder autorizar acao que altera
arquivo, e conta errada aqui vira decisao errada la. Por isso ela tem teste.

O que estes testes fixam e a separacao entre trocar, remover e acrescentar.
Somar os tres num numero so faria "digitei mais uma frase no fim" parecer erro
de transcricao, e foi exatamente esse tipo de leitura que a medicao de 26/08
teve que corrigir depois de publicada.
"""

import importlib.util
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
ANALISADOR = RAIZ / 'docs' / 'medicoes' / '2026-09-01-ditado-real' / 'analisar.py'

_spec = importlib.util.spec_from_file_location('analisar_ditado', ANALISADOR)
analisar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(analisar)


class TestNormaliza:
    def test_tira_acento_pontuacao_e_caixa(self):
        assert analisar.normaliza('Conciliação, de Férias!').split() == [
            'conciliacao',
            'de',
            'ferias',
        ]

    def test_texto_vazio_vira_lista_vazia(self):
        assert analisar.normaliza('').split() == []


class TestScriptDeEdicao:
    def test_textos_iguais_nao_tem_edicao_nenhuma(self):
        palavras = ['roda', 'os', 'testes']

        assert analisar.script_de_edicao(palavras, palavras) == (0, 0, 0)

    def test_palavra_trocada_conta_como_troca(self):
        assert analisar.script_de_edicao(
            ['abre', 'o', 'homem', 'in', 'api'],
            ['abre', 'o', 'omni', 'in', 'api'],
        ) == (1, 0, 0)

    def test_palavra_acrescentada_no_fim_nao_e_troca(self):
        assert analisar.script_de_edicao(
            ['roda', 'os', 'testes'],
            ['roda', 'os', 'testes', 'agora', 'por', 'favor'],
        ) == (0, 0, 3)

    def test_palavra_removida_conta_como_remocao(self):
        assert analisar.script_de_edicao(
            ['roda', 'logo', 'os', 'testes'],
            ['roda', 'os', 'testes'],
        ) == (0, 1, 0)

    def test_texto_enviado_vazio_remove_tudo(self):
        assert analisar.script_de_edicao(['roda', 'os', 'testes'], []) == (0, 3, 0)


class TestResumir:
    def test_par_identico_nao_acusa_correcao(self):
        ditados = {'a': {'id': 'a', 'bruto': 'roda os testes', 'segundos_transcricao': 3.0}}
        enviados = {'a': {'id': 'a', 'enviado': 'roda os testes', 'segundos_ate_enviar': 4}}

        r = analisar.resumir(ditados, enviados)

        assert r['amostra'] == 1
        assert r['correcao_mediana'] == 0.0

    def test_acrescentar_no_fim_nao_conta_como_correcao(self):
        # O caso mais comum: o ditado saiu certo e o usuario digitou mais.
        ditados = {'a': {'id': 'a', 'bruto': 'roda os testes', 'segundos_transcricao': 3.0}}
        enviados = {
            'a': {'id': 'a', 'enviado': 'roda os testes e me diz o numero', 'segundos_ate_enviar': 9}
        }

        assert analisar.resumir(ditados, enviados)['correcao_mediana'] == 0.0

    def test_uma_palavra_trocada_em_quatro_da_um_quarto(self):
        ditados = {'a': {'id': 'a', 'bruto': 'abre o homem api', 'segundos_transcricao': 3.0}}
        enviados = {'a': {'id': 'a', 'enviado': 'abre o omni api', 'segundos_ate_enviar': 12}}

        assert analisar.resumir(ditados, enviados)['correcao_mediana'] == 0.25

    def test_ditado_sem_enviado_e_abandono(self):
        ditados = {
            'a': {'id': 'a', 'bruto': 'roda os testes', 'segundos_transcricao': 3.0},
            'b': {'id': 'b', 'bruto': 'apaga tudo', 'segundos_transcricao': 3.0},
        }
        enviados = {'a': {'id': 'a', 'enviado': 'roda os testes', 'segundos_ate_enviar': 5}}

        r = analisar.resumir(ditados, enviados)

        assert r['amostra'] == 1
        assert r['abandonados'] == 1
        assert r['taxa_abandono'] == 0.5

    def test_lista_a_palavra_que_o_motor_errou(self):
        # E o que realimenta a dica: saber que "omni" vira "homem" toda vez.
        ditados = {'a': {'id': 'a', 'bruto': 'abre o homem api', 'segundos_transcricao': 3.0}}
        enviados = {'a': {'id': 'a', 'enviado': 'abre o omni api', 'segundos_ate_enviar': 12}}

        r = analisar.resumir(ditados, enviados)

        assert ('homem -> omni', 1) in r['trocas_frequentes']

    def test_guarda_a_latencia_e_o_tempo_de_revisao(self):
        ditados = {'a': {'id': 'a', 'bruto': 'roda os testes', 'segundos_transcricao': 4.5}}
        enviados = {'a': {'id': 'a', 'enviado': 'roda os testes', 'segundos_ate_enviar': 22}}

        r = analisar.resumir(ditados, enviados)

        assert r['latencia_mediana_s'] == 4.5
        assert r['revisao_mediana_s'] == 22.0

    def test_sem_par_nenhum_nao_inventa_estatistica(self):
        assert analisar.resumir({}, {}) is None
