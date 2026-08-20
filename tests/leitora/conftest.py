import json

import pytest


@pytest.fixture
def escrever_jsonl(tmp_path):
    """Escreve linhas JSON num arquivo e devolve o caminho como texto."""

    def _escrever(nome, registros, linhas_cruas=()):
        caminho = tmp_path / nome
        partes = [json.dumps(r, ensure_ascii=False) for r in registros]
        partes.extend(linhas_cruas)
        caminho.write_text('\n'.join(partes) + '\n', encoding='utf-8')
        return str(caminho)

    return _escrever
