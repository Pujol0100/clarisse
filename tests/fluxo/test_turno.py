"""O marcador que diz se a Clarisse pode falar sozinha.

A regra de 21/08 continua valendo: ela so fala dentro de um turno que o usuario
abriu. Falar a cada resposta ja interrompeu uma reuniao, e sao ~10 sessoes
abertas ao mesmo tempo.

Ditar abre o turno. O hook Stop consome: com marcador valido, o resumo sai na
hora; sem marcador, bipa e espera o atalho.

O marcador vence, e isso nao e detalhe: quem ditou de manha e saiu para almocar
nao quer a maquina falando sozinha quando o Claude terminar, uma hora depois.
"""

from clarisse.ouvinte.turno import abrir, consumir

AGORA = 1_800_000_000.0
QUINZE_MIN = 15 * 60


class TestTurnoAberto:
    def test_quem_ditou_ouve_a_resposta_na_hora(self, tmp_path):
        abrir(tmp_path, 'voz-ao-claude', agora=AGORA)

        assert consumir(tmp_path, 'voz-ao-claude', agora=AGORA + 5) is True

    def test_sem_marcador_nao_ha_turno(self, tmp_path):
        assert consumir(tmp_path, 'voz-ao-claude', agora=AGORA) is False

    def test_o_turno_serve_uma_vez_so(self, tmp_path):
        abrir(tmp_path, 'voz-ao-claude', agora=AGORA)
        consumir(tmp_path, 'voz-ao-claude', agora=AGORA + 5)

        assert consumir(tmp_path, 'voz-ao-claude', agora=AGORA + 6) is False

    def test_consumir_de_novo_nao_quebra(self, tmp_path):
        assert consumir(tmp_path, 'voz-ao-claude', agora=AGORA) is False
        assert consumir(tmp_path, 'voz-ao-claude', agora=AGORA) is False

    def test_ditar_de_novo_renova_o_turno(self, tmp_path):
        abrir(tmp_path, 'voz-ao-claude', agora=AGORA)
        abrir(tmp_path, 'voz-ao-claude', agora=AGORA + QUINZE_MIN)

        assert consumir(tmp_path, 'voz-ao-claude', agora=AGORA + QUINZE_MIN + 10) is True


class TestValidade:
    def test_marcador_vencido_nao_abre_turno(self, tmp_path):
        abrir(tmp_path, 'voz-ao-claude', agora=AGORA)

        assert consumir(tmp_path, 'voz-ao-claude', agora=AGORA + QUINZE_MIN + 1) is False

    def test_marcador_no_limite_ainda_vale(self, tmp_path):
        abrir(tmp_path, 'voz-ao-claude', agora=AGORA)

        assert consumir(tmp_path, 'voz-ao-claude', agora=AGORA + QUINZE_MIN) is True

    def test_marcador_vencido_e_removido(self, tmp_path):
        abrir(tmp_path, 'voz-ao-claude', agora=AGORA)
        consumir(tmp_path, 'voz-ao-claude', agora=AGORA + QUINZE_MIN + 1)

        assert consumir(tmp_path, 'voz-ao-claude', agora=AGORA) is False

    def test_marcador_do_futuro_nao_vale(self, tmp_path):
        # Relogio da maquina mexido, ou marcador escrito por engano. Um marcador
        # que valeria por horas e pior do que nenhum.
        abrir(tmp_path, 'voz-ao-claude', agora=AGORA + 3600)

        assert consumir(tmp_path, 'voz-ao-claude', agora=AGORA) is False


class TestProjeto:
    def test_marcador_de_um_projeto_nao_abre_turno_de_outro(self, tmp_path):
        abrir(tmp_path, 'voz-ao-claude', agora=AGORA)

        assert consumir(tmp_path, 'omni-api', agora=AGORA + 5) is False

    def test_o_marcador_do_outro_projeto_continua_de_pe(self, tmp_path):
        abrir(tmp_path, 'voz-ao-claude', agora=AGORA)
        consumir(tmp_path, 'omni-api', agora=AGORA + 5)

        assert consumir(tmp_path, 'voz-ao-claude', agora=AGORA + 6) is True

    def test_dois_projetos_tem_marcador_proprio(self, tmp_path):
        abrir(tmp_path, 'voz-ao-claude', agora=AGORA)
        abrir(tmp_path, 'omni-api', agora=AGORA)

        assert consumir(tmp_path, 'omni-api', agora=AGORA + 5) is True
        assert consumir(tmp_path, 'voz-ao-claude', agora=AGORA + 5) is True

    def test_nome_com_barra_nao_escapa_da_pasta(self, tmp_path):
        abrir(tmp_path, 'cliente/projeto', agora=AGORA)

        marcadores = list(tmp_path.iterdir())
        assert [m.name for m in marcadores] == ['cliente-projeto.txt']
        assert consumir(tmp_path, 'cliente/projeto', agora=AGORA + 5) is True

    def test_projeto_sem_nome_nao_abre_turno(self, tmp_path):
        abrir(tmp_path, '', agora=AGORA)

        assert consumir(tmp_path, '', agora=AGORA) is False


class TestMarcadorEstragado:
    def test_marcador_ilegivel_nao_abre_turno(self, tmp_path):
        abrir(tmp_path, 'voz-ao-claude', agora=AGORA)
        arquivo = next(tmp_path.iterdir())
        arquivo.write_text('nao e um instante', encoding='utf-8')

        assert consumir(tmp_path, 'voz-ao-claude', agora=AGORA) is False

    def test_marcador_ilegivel_e_removido(self, tmp_path):
        abrir(tmp_path, 'voz-ao-claude', agora=AGORA)
        next(tmp_path.iterdir()).write_text('lixo', encoding='utf-8')
        consumir(tmp_path, 'voz-ao-claude', agora=AGORA)

        assert list(tmp_path.iterdir()) == []

    def test_pasta_que_nao_existe_nao_quebra(self, tmp_path):
        assert consumir(tmp_path / 'nao-existe', 'voz-ao-claude', agora=AGORA) is False
