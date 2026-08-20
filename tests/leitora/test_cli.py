import json
import os

from clarisse.leitora.cli import executar


def _montar(raiz, pasta, nome, cwd, mtime, registros):
    destino = raiz / pasta
    destino.mkdir(parents=True, exist_ok=True)
    arquivo = destino / nome
    linhas = [json.dumps({'type': 'user', 'cwd': cwd,
                          'timestamp': '2026-08-20T09:00:00Z',
                          'message': {'role': 'user', 'content': 'inicio'}})]
    linhas += [json.dumps(r, ensure_ascii=False) for r in registros]
    arquivo.write_text('\n'.join(linhas) + '\n', encoding='utf-8')
    os.utime(arquivo, (mtime, mtime))


def test_projetos_lista_o_que_existe(tmp_path):
    _montar(tmp_path, 'a', 'a.jsonl', r'C:\dev\omni-api', 2000.0, [])
    _montar(tmp_path, 'b', 'b.jsonl', r'C:\dev\api-gestora', 1000.0, [])

    saida = executar(['projetos', '--raiz', str(tmp_path)])

    assert [p['projeto'] for p in saida['projetos']] == ['omni-api', 'api-gestora']


def test_relatar_devolve_os_eventos_do_projeto(tmp_path):
    _montar(tmp_path, 'a', 'a.jsonl', r'C:\dev\omni-api', 2000.0, [
        {'type': 'assistant', 'timestamp': '2026-08-20T09:05:00Z',
         'message': {'role': 'assistant',
                     'content': [{'type': 'text', 'text': 'vinte e sete testes passaram'}]}},
    ])

    saida = executar(['relatar', '--projeto', 'omni', '--raiz', str(tmp_path)])

    assert saida['projeto'] == 'omni-api'
    assert saida['sessao_id'] == 'a'
    textos = [e['texto'] for e in saida['eventos']]
    assert 'vinte e sete testes passaram' in textos


def test_relatar_mascara_segredo_no_caminho_de_saida(tmp_path):
    _montar(tmp_path, 'a', 'a.jsonl', r'C:\dev\omni-api', 2000.0, [
        {'type': 'assistant', 'timestamp': '2026-08-20T09:05:00Z',
         'message': {'role': 'assistant',
                     'content': [{'type': 'text',
                                  'text': 'usei password=Trocar123! para conectar'}]}},
    ])

    saida = executar(['relatar', '--projeto', 'omni-api', '--raiz', str(tmp_path)])

    despejo = json.dumps(saida, ensure_ascii=False)
    assert 'Trocar123!' not in despejo
    assert '[oculto]' in despejo


def test_relatar_com_nome_ambiguo_pede_escolha(tmp_path):
    _montar(tmp_path, 'a', 'a.jsonl', r'C:\dev\omni-api', 2000.0, [])
    _montar(tmp_path, 'b', 'b.jsonl', r'C:\dev\omni-enrichment', 1000.0, [])

    saida = executar(['relatar', '--projeto', 'omni', '--raiz', str(tmp_path)])

    assert saida['erro'] == 'ambiguo'
    assert saida['candidatos'] == ['omni-api', 'omni-enrichment']


def test_relatar_projeto_inexistente_avisa(tmp_path):
    _montar(tmp_path, 'a', 'a.jsonl', r'C:\dev\omni-api', 2000.0, [])

    saida = executar(['relatar', '--projeto', 'financeiro', '--raiz', str(tmp_path)])

    assert saida['erro'] == 'nao_encontrado'


def test_relatar_respeita_o_limite_de_eventos(tmp_path):
    registros = [
        {'type': 'assistant', 'timestamp': f'2026-08-20T09:0{i}:00Z',
         'message': {'role': 'assistant',
                     'content': [{'type': 'text', 'text': f'evento {i}'}]}}
        for i in range(1, 6)
    ]
    _montar(tmp_path, 'a', 'a.jsonl', r'C:\dev\omni-api', 2000.0, registros)

    saida = executar(['relatar', '--projeto', 'omni-api', '--maximo', '2',
                      '--raiz', str(tmp_path)])

    assert len(saida['eventos']) == 2
    assert saida['eventos'][-1]['texto'] == 'evento 5'


def test_relatar_sem_projeto_usa_a_sessao_mais_ativa(tmp_path):
    _montar(tmp_path, 'a', 'a.jsonl', r'C:\dev\antigo', 1000.0, [])
    _montar(tmp_path, 'b', 'b.jsonl', r'C:\dev\recente', 2000.0, [])

    saida = executar(['relatar', '--raiz', str(tmp_path)])

    assert saida['projeto'] == 'recente'


def test_projetos_agrupa_a_mesma_pasta_com_caixa_diferente(tmp_path):
    # No Windows omni-api e OMNI-API sao a mesma pasta. Listar as duas faria a
    # Clarisse anunciar um projeto que nao existe.
    _montar(tmp_path, 'a', 'a.jsonl', r'C:\dev\omni-api', 1000.0, [])
    _montar(tmp_path, 'b', 'b.jsonl', r'C:\dev\OMNI-API', 2000.0, [])

    saida = executar(['projetos', '--raiz', str(tmp_path)])

    assert [p['projeto'] for p in saida['projetos']] == ['OMNI-API']


def test_projetos_traz_a_sessao_mais_recente_de_cada_projeto(tmp_path):
    _montar(tmp_path, 'a', 'velha.jsonl', r'C:\dev\alvo', 1000.0, [])
    _montar(tmp_path, 'a', 'nova.jsonl', r'C:\dev\alvo', 3000.0, [])

    saida = executar(['projetos', '--raiz', str(tmp_path)])

    assert len(saida['projetos']) == 1
    assert saida['projetos'][0]['sessao_id'] == 'nova'
