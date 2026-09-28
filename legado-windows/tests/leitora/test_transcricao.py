from clarisse.leitora.transcricao import (
    CLAUDE,
    FERRAMENTA,
    USUARIO,
    ler_eventos,
)


def _fala_do_usuario(texto, momento='2026-08-20T10:00:00Z'):
    return {
        'type': 'user',
        'timestamp': momento,
        'message': {'role': 'user', 'content': texto},
    }


def _resposta_do_claude(blocos, momento='2026-08-20T10:00:05Z'):
    return {
        'type': 'assistant',
        'timestamp': momento,
        'message': {'role': 'assistant', 'content': blocos},
    }


def test_le_pergunta_do_usuario_e_resposta_do_claude(escrever_jsonl):
    caminho = escrever_jsonl('s.jsonl', [
        _fala_do_usuario('roda os testes'),
        _resposta_do_claude([{'type': 'text', 'text': 'rodando agora'}]),
    ])

    eventos = ler_eventos(caminho)

    assert [e.quem for e in eventos] == [USUARIO, CLAUDE]
    assert eventos[0].texto == 'roda os testes'
    assert eventos[1].texto == 'rodando agora'
    assert eventos[0].momento == '2026-08-20T10:00:00Z'


def test_linha_malformada_e_ignorada_sem_derrubar_a_leitura(escrever_jsonl):
    caminho = escrever_jsonl(
        's.jsonl',
        [_fala_do_usuario('primeira')],
        linhas_cruas=['{isso nao e json', ''],
    )

    eventos = ler_eventos(caminho)

    assert [e.texto for e in eventos] == ['primeira']


def test_pensamento_do_claude_nao_entra_no_relato(escrever_jsonl):
    caminho = escrever_jsonl('s.jsonl', [
        _resposta_do_claude([
            {'type': 'thinking', 'thinking': 'deixa eu pensar no caso de borda'},
            {'type': 'text', 'text': 'achei o problema'},
        ]),
    ])

    eventos = ler_eventos(caminho)

    assert [e.texto for e in eventos] == ['achei o problema']


def test_uso_de_ferramenta_vira_evento_com_o_nome(escrever_jsonl):
    caminho = escrever_jsonl('s.jsonl', [
        _resposta_do_claude([{'type': 'tool_use', 'name': 'Bash', 'input': {}}]),
    ])

    eventos = ler_eventos(caminho)

    assert len(eventos) == 1
    assert eventos[0].quem == FERRAMENTA
    assert eventos[0].ferramenta == 'Bash'


def test_linha_de_subagente_e_ignorada(escrever_jsonl):
    registro = _resposta_do_claude([{'type': 'text', 'text': 'sou um subagente'}])
    registro['isSidechain'] = True
    caminho = escrever_jsonl('s.jsonl', [registro])

    assert ler_eventos(caminho) == []


def test_linha_de_servico_do_sistema_e_ignorada(escrever_jsonl):
    caminho = escrever_jsonl('s.jsonl', [
        {'type': 'ai-title', 'aiTitle': 'Um titulo qualquer'},
        {'type': 'file-history-snapshot', 'snapshot': {}},
        _fala_do_usuario('sobrou so eu'),
    ])

    eventos = ler_eventos(caminho)

    assert [e.texto for e in eventos] == ['sobrou so eu']


def test_texto_em_branco_nao_gera_evento(escrever_jsonl):
    caminho = escrever_jsonl('s.jsonl', [
        _fala_do_usuario('   '),
        _resposta_do_claude([{'type': 'text', 'text': ''}]),
    ])

    assert ler_eventos(caminho) == []


def test_arquivo_inexistente_devolve_lista_vazia(tmp_path):
    assert ler_eventos(str(tmp_path / 'nao-existe.jsonl')) == []
