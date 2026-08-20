import json
import os

from clarisse.leitora.sessoes import (
    listar_sessoes,
    projetos_que_casam,
    sessao_mais_recente,
)


def _montar_projeto(raiz, pasta, nome_arquivo, cwd, momento_mtime):
    destino = raiz / pasta
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / nome_arquivo
    registro = {
        'type': 'user',
        'cwd': cwd,
        'timestamp': '2026-08-20T10:00:00Z',
        'message': {'role': 'user', 'content': 'oi'},
    }
    arquivo.write_text(json.dumps(registro) + '\n', encoding='utf-8')
    os.utime(arquivo, (momento_mtime, momento_mtime))
    return arquivo


def test_lista_sessoes_com_o_nome_do_projeto_vindo_do_cwd(tmp_path):
    _montar_projeto(
        tmp_path, 'C--Users-eu-Documents-api-gestora', 'aaa.jsonl',
        r'C:\Users\eu\Documents\api-gestora', 1000.0,
    )

    sessoes = listar_sessoes(str(tmp_path))

    assert len(sessoes) == 1
    assert sessoes[0].projeto == 'api-gestora'
    assert sessoes[0].sessao_id == 'aaa'


def test_ordena_da_atividade_mais_recente_para_a_mais_antiga(tmp_path):
    _montar_projeto(tmp_path, 'p-antigo', 'a.jsonl', r'C:\dev\antigo', 1000.0)
    _montar_projeto(tmp_path, 'p-novo', 'b.jsonl', r'C:\dev\novo', 2000.0)

    sessoes = listar_sessoes(str(tmp_path))

    assert [s.projeto for s in sessoes] == ['novo', 'antigo']


def test_arquivo_sem_cwd_e_ignorado(tmp_path):
    pasta = tmp_path / 'sem-cwd'
    pasta.mkdir()
    (pasta / 'x.jsonl').write_text(
        json.dumps({'type': 'ai-title', 'aiTitle': 'nada'}) + '\n',
        encoding='utf-8',
    )

    assert listar_sessoes(str(tmp_path)) == []


def test_raiz_inexistente_devolve_lista_vazia(tmp_path):
    assert listar_sessoes(str(tmp_path / 'nao-existe')) == []


def test_nome_parcial_acha_um_projeto(tmp_path):
    _montar_projeto(tmp_path, 'a', 'a.jsonl', r'C:\dev\conciliacao-bancaria', 1000.0)
    sessoes = listar_sessoes(str(tmp_path))

    assert projetos_que_casam(sessoes, 'concil') == ['conciliacao-bancaria']


def test_nome_ambiguo_devolve_todos_os_candidatos(tmp_path):
    _montar_projeto(tmp_path, 'a', 'a.jsonl', r'C:\dev\omni-api', 2000.0)
    _montar_projeto(tmp_path, 'b', 'b.jsonl', r'C:\dev\omni-enrichment', 1000.0)
    sessoes = listar_sessoes(str(tmp_path))

    assert projetos_que_casam(sessoes, 'omni') == ['omni-api', 'omni-enrichment']


def test_nome_que_nao_existe_devolve_lista_vazia(tmp_path):
    _montar_projeto(tmp_path, 'a', 'a.jsonl', r'C:\dev\omni-api', 1000.0)
    sessoes = listar_sessoes(str(tmp_path))

    assert projetos_que_casam(sessoes, 'financeiro') == []


def test_nome_exato_nao_e_atropelado_por_nome_maior(tmp_path):
    _montar_projeto(tmp_path, 'a', 'a.jsonl', r'C:\dev\omni-api', 1000.0)
    _montar_projeto(tmp_path, 'b', 'b.jsonl', r'C:\dev\omni-api-legado', 2000.0)
    sessoes = listar_sessoes(str(tmp_path))

    assert projetos_que_casam(sessoes, 'omni-api') == ['omni-api']


def test_sessao_mais_recente_de_um_projeto(tmp_path):
    _montar_projeto(tmp_path, 'p', 'velha.jsonl', r'C:\dev\alvo', 1000.0)
    _montar_projeto(tmp_path, 'p', 'nova.jsonl', r'C:\dev\alvo', 3000.0)
    sessoes = listar_sessoes(str(tmp_path))

    escolhida = sessao_mais_recente(sessoes, 'alvo')

    assert escolhida is not None
    assert escolhida.sessao_id == 'nova'


def test_sessao_mais_recente_de_projeto_inexistente_e_nula(tmp_path):
    assert sessao_mais_recente([], 'alvo') is None
