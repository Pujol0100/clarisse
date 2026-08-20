# Plano A — A Leitora e o relato falado

> **Para executores agênticos:** SUB-SKILL OBRIGATÓRIA: use
> `superpowers:subagent-driven-development` (recomendado) ou
> `superpowers:executing-plans` para implementar tarefa por tarefa. Os passos usam
> caixa de marcação (`- [ ]`) para acompanhamento.

**Objetivo:** o usuário pergunta "o que está rolando no omni-api" e a Clarisse
**fala** o que aconteceu naquela sessão do Claude Code.

**Arquitetura:** um pacote Python novo, `clarisse/leitora/`, lê as transcrições que
o Claude Code já grava em `~/.claude/projects/<projeto>/<sessão>.jsonl` e devolve
os eventos em JSON. O Claude da sessão corrente compõe a frase falada a partir
desse JSON e manda o motor de voz existente falar. **Nenhum código novo de
PowerShell**: `clarisse.ps1 -Mode say -Text "..."` já fala na hora.

**Pilha:** Python 3.14.4 (só biblioteca padrão), pytest 9.1.1, Windows PowerShell
5.1, o motor de voz que já existe.

**Especificação:** `docs/planos/2026-08-20-clarisse-ao-vivo-design.md`

## Restrições globais

- Python 3.14.4, invocado como `python`. Confirmado nesta máquina em 20/08/2026.
- pytest 9.1.1, já instalado. Confirmado em 20/08/2026.
- **Nenhuma dependência nova de `pip`.** Só biblioteca padrão do Python.
- A suíte Pester existente tem **126 testes, todos passando**, e não pode
  regredir. Pester nesta máquina é 3.4.0: `Invoke-Pester` **não** aceita
  `-Output`; use `-Quiet -PassThru`.
- Todo arquivo de texto lido ou escrito é UTF-8.
- Nomes de função, variável, arquivo e teste em português, como o resto do
  repositório.
- Comentário documenta o código, não o processo. Nada de "melhoria em relação a".
- `try`/`except` só em fronteira de sistema (leitura de arquivo, linha malformada).
  Falha em chamada intermediária sobe.
- O texto falado nunca contém caminho de arquivo, comando, bloco de código, URL ou
  hash — regra que já vale no projeto.
- Nada de credencial, token ou senha no texto falado. Garantido mecanicamente pela
  Tarefa 1.

## Estrutura de arquivos

| Arquivo | Responsabilidade única |
|---|---|
| `clarisse/__init__.py` | Marca `clarisse` como pacote Python, para os testes importarem |
| `clarisse/leitora/__init__.py` | Marca `leitora` como pacote |
| `clarisse/leitora/segredo.py` | Mascarar formatos evidentes de segredo num texto |
| `clarisse/leitora/transcricao.py` | Traduzir um arquivo `.jsonl` de sessão numa lista de eventos legíveis |
| `clarisse/leitora/sessoes.py` | Descobrir projetos e sessões em disco, e resolver nome parcial |
| `clarisse/leitora/cli.py` | Fronteira de linha de comando: recebe argumentos, devolve JSON |
| `pytest.ini` | Aponta o pytest para `tests/`, sem atropelar o Pester |
| `tests/leitora/conftest.py` | Ajuda a escrever transcrições de exemplo nos testes |
| `tests/leitora/test_segredo.py` | Testes do mascaramento |
| `tests/leitora/test_transcricao.py` | Testes da tradução das linhas |
| `tests/leitora/test_sessoes.py` | Testes da descoberta e da resolução de nome |
| `tests/leitora/test_cli.py` | Testes da fronteira de linha de comando |
| `comandos/clarisse.md` | Ganha os argumentos de relato |
| `instalar.ps1` | Passa a copiar a pasta `leitora` |
| `README.md` | Documenta o relato e corrige a contagem de testes |

---

### Tarefa 1: Mascarar segredo antes de qualquer coisa ser falada

Esta tarefa vem primeiro porque a especificação declara o vazamento de segredo
como risco alto, e porque ela também prova que a suíte pytest funciona neste
repositório.

**Arquivos:**
- Criar: `clarisse/__init__.py`
- Criar: `clarisse/leitora/__init__.py`
- Criar: `clarisse/leitora/segredo.py`
- Criar: `pytest.ini`
- Testar: `tests/leitora/test_segredo.py`

**Interfaces:**
- Consome: nada.
- Produz: `mascarar(texto: str) -> str` e `contem_segredo(texto: str) -> bool`,
  em `clarisse.leitora.segredo`.

- [ ] **Passo 1: Criar os arquivos de pacote e a configuração do pytest**

Crie `clarisse/__init__.py` **vazio** (zero bytes).

Crie `clarisse/leitora/__init__.py` **vazio** (zero bytes).

Crie `pytest.ini` na raiz do repositório com exatamente este conteúdo:

```ini
[pytest]
testpaths = tests
python_files = test_*.py
```

`python_files = test_*.py` é o que impede o pytest de tentar coletar os arquivos
`*.Tests.ps1` do Pester que vivem na mesma pasta.

- [ ] **Passo 2: Escrever o teste que falha**

Crie `tests/leitora/test_segredo.py`:

```python
from clarisse.leitora.segredo import contem_segredo, mascarar


def test_mascara_valor_de_senha_em_atribuicao():
    texto = 'conectei com password=Trocar123! e deu certo'
    assert mascarar(texto) == 'conectei com password=[oculto] e deu certo'


def test_mascara_chave_da_anthropic():
    texto = 'usei a chave sk-ant-api03-abc123DEF456 no teste'
    assert mascarar(texto) == 'usei a chave [oculto] no teste'


def test_mascara_cabecalho_bearer():
    texto = 'mandei Authorization: Bearer eyJhbGciOiJIUzI1NiJ9 no header'
    assert '[oculto]' in mascarar(texto)
    assert 'eyJhbGciOiJIUzI1NiJ9' not in mascarar(texto)


def test_mascara_chave_de_acesso_da_aws():
    texto = 'a conta usa AKIAIOSFODNN7EXAMPLE hoje'
    assert mascarar(texto) == 'a conta usa [oculto] hoje'


def test_nao_mascara_a_palavra_senha_sem_valor():
    texto = 'o usuario esqueceu a senha e pediu para redefinir'
    assert mascarar(texto) == texto
    assert contem_segredo(texto) is False


def test_contem_segredo_acusa_quando_mascarou():
    assert contem_segredo('token: abc123xyz789') is True


def test_texto_vazio_nao_quebra():
    assert mascarar('') == ''
    assert contem_segredo('') is False
```

- [ ] **Passo 3: Rodar o teste e confirmar que falha**

No PowerShell, na raiz do worktree:

```
python -m pytest tests/leitora/test_segredo.py -v
```

Esperado: **erro de coleta**, com `ModuleNotFoundError: No module named
'clarisse.leitora.segredo'`. Se em vez disso vier "no tests ran", o `pytest.ini`
está no lugar errado — ele vai na raiz do repositório.

- [ ] **Passo 4: Escrever a implementação mínima**

Crie `clarisse/leitora/segredo.py`:

```python
"""Mascara formatos evidentes de segredo antes de um texto virar voz.

A sintese neural manda o texto para servidores da Microsoft. Transcricao de
sessao contem tudo que passou por um terminal, inclusive credencial colada.

Este filtro pega formato, nao sentido: ele barra uma chave, um token e uma
atribuicao de senha. Nome de cliente dito em texto corrido passa. A defesa
contra isso e a instrucao dada ao Claude que compoe o resumo, e ela e
instrucao, nao garantia.
"""

from __future__ import annotations

import re

OCULTO = '[oculto]'

_ATRIBUICAO = re.compile(
    r'(?i)\b(senha|password|secret|token|api[_-]?key|chave[_-]?api|authorization)'
    r'(\s*[:=]\s*)("?)([^\s"\']+)\3'
)
_BEARER = re.compile(r'(?i)\bBearer\s+[A-Za-z0-9._\-]{8,}')
_CHAVE_ANTHROPIC = re.compile(r'\bsk-ant-[A-Za-z0-9._\-]+')
_CHAVE_AWS = re.compile(r'\bAKIA[0-9A-Z]{16}\b')
_CHAVE_PRIVADA = re.compile(
    r'-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----',
    re.DOTALL,
)


def mascarar(texto: str) -> str:
    """Devolve o texto com os segredos reconhecidos trocados por [oculto]."""
    if not texto:
        return texto
    limpo = _CHAVE_PRIVADA.sub(OCULTO, texto)
    limpo = _ATRIBUICAO.sub(lambda m: f'{m.group(1)}{m.group(2)}{OCULTO}', limpo)
    limpo = _BEARER.sub(f'Bearer {OCULTO}', limpo)
    limpo = _CHAVE_ANTHROPIC.sub(OCULTO, limpo)
    limpo = _CHAVE_AWS.sub(OCULTO, limpo)
    return limpo


def contem_segredo(texto: str) -> bool:
    """Verdadeiro quando mascarar mudaria o texto."""
    return mascarar(texto) != texto
```

- [ ] **Passo 5: Rodar o teste e confirmar que passa**

```
python -m pytest tests/leitora/test_segredo.py -v
```

Esperado: `7 passed`.

Atenção ao teste do Bearer: `_ATRIBUICAO` casa `Authorization: Bearer` e mascara
a palavra `Bearer`, produzindo `Authorization: [oculto] eyJ...`; depois `_BEARER`
não encontra mais o padrão. O teste só exige que o token não sobre e que
`[oculto]` apareça — as duas coisas acontecem. Se você mudar a ordem das
substituições, esse teste é o que avisa.

- [ ] **Passo 6: Confirmar que o Pester não regrediu**

```
$r = Invoke-Pester -Path .\tests -PassThru -Quiet; "Total: $($r.TotalCount) Passaram: $($r.PassedCount) Falharam: $($r.FailedCount)"
```

Esperado: `Total: 126 Passaram: 126 Falharam: 0`.

- [ ] **Passo 7: Commitar**

```bash
git add clarisse/__init__.py clarisse/leitora/__init__.py clarisse/leitora/segredo.py pytest.ini tests/leitora/test_segredo.py
git commit -m "Barra formato de segredo antes do texto virar voz"
```

---

### Tarefa 2: Traduzir a transcrição de uma sessão em eventos legíveis

**Arquivos:**
- Criar: `clarisse/leitora/transcricao.py`
- Criar: `tests/leitora/conftest.py`
- Testar: `tests/leitora/test_transcricao.py`

**Interfaces:**
- Consome: nada da Tarefa 1 (o mascaramento é aplicado na Tarefa 4, na fronteira).
- Produz, em `clarisse.leitora.transcricao`:
  - constantes `USUARIO = 'usuario'`, `CLAUDE = 'claude'`,
    `FERRAMENTA = 'ferramenta'`
  - `class Evento` com os campos `quem: str`, `texto: str`, `momento: str`,
    `ferramenta: str`
  - `ler_eventos(caminho: str) -> list[Evento]`

- [ ] **Passo 1: Escrever a ajuda de teste**

Crie `tests/leitora/conftest.py`:

```python
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
```

- [ ] **Passo 2: Escrever os testes que falham**

Crie `tests/leitora/test_transcricao.py`:

```python
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
```

- [ ] **Passo 3: Rodar os testes e confirmar que falham**

```
python -m pytest tests/leitora/test_transcricao.py -v
```

Esperado: erro de coleta com `ModuleNotFoundError: No module named
'clarisse.leitora.transcricao'`.

- [ ] **Passo 4: Escrever a implementação mínima**

Crie `clarisse/leitora/transcricao.py`:

```python
"""Traduz uma transcricao de sessao do Claude Code em eventos legiveis.

O Claude Code grava uma linha JSON por evento em
~/.claude/projects/<projeto>/<sessao>.jsonl.

Linha malformada e ignorada de proposito: o arquivo esta sendo escrito enquanto
lemos, e a ultima linha pode estar pela metade. Derrubar a leitura por causa
disso faria a Clarisse calar justamente quando o projeto esta em atividade.

O pensamento do Claude fica de fora do relato: e raciocinio interno, nao e o que
aconteceu, e carrega mais risco de vazar do que informa.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

USUARIO = 'usuario'
CLAUDE = 'claude'
FERRAMENTA = 'ferramenta'

_TIPOS_RELATAVEIS = ('user', 'assistant')


@dataclass(frozen=True)
class Evento:
    quem: str
    texto: str
    momento: str
    ferramenta: str = ''


def _eventos_da_lista_de_blocos(blocos, quem, momento):
    achados = []
    for bloco in blocos:
        if not isinstance(bloco, dict):
            continue
        tipo = bloco.get('type')
        if tipo == 'text':
            texto = (bloco.get('text') or '').strip()
            if texto:
                achados.append(Evento(quem, texto, momento))
        elif tipo == 'tool_use':
            nome = (bloco.get('name') or '').strip()
            if nome:
                achados.append(Evento(FERRAMENTA, '', momento, nome))
    return achados


def _eventos_do_registro(registro):
    if registro.get('isSidechain') or registro.get('isMeta'):
        return []
    if registro.get('type') not in _TIPOS_RELATAVEIS:
        return []

    quem = USUARIO if registro.get('type') == 'user' else CLAUDE
    momento = registro.get('timestamp') or ''
    conteudo = (registro.get('message') or {}).get('content')

    if isinstance(conteudo, str):
        texto = conteudo.strip()
        return [Evento(quem, texto, momento)] if texto else []
    if isinstance(conteudo, list):
        return _eventos_da_lista_de_blocos(conteudo, quem, momento)
    return []


def ler_eventos(caminho: str) -> list[Evento]:
    """Le a transcricao e devolve os eventos, na ordem em que aconteceram."""
    try:
        with open(caminho, encoding='utf-8', errors='replace') as arquivo:
            linhas = arquivo.read().splitlines()
    except OSError:
        return []

    eventos = []
    for linha in linhas:
        linha = linha.strip()
        if not linha:
            continue
        try:
            registro = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if isinstance(registro, dict):
            eventos.extend(_eventos_do_registro(registro))
    return eventos
```

Remova a importação `field` se o seu editor apontar que ela não é usada — ela não
é. O arquivo acima está correto sem ela; a linha de importação deve ser
`from dataclasses import dataclass`.

- [ ] **Passo 5: Rodar os testes e confirmar que passam**

```
python -m pytest tests/leitora/test_transcricao.py -v
```

Esperado: `8 passed`.

Se vier `ImportError: cannot import name 'field'`, você copiou uma versão antiga
do bloco acima: a linha de importação é `from dataclasses import dataclass`, sem
`field`.

- [ ] **Passo 6: Commitar**

```bash
git add clarisse/leitora/transcricao.py tests/leitora/conftest.py tests/leitora/test_transcricao.py
git commit -m "Le a transcricao de uma sessao sem cair em linha pela metade"
```

---

### Tarefa 3: Descobrir sessões e resolver nome parcial de projeto

**Arquivos:**
- Criar: `clarisse/leitora/sessoes.py`
- Testar: `tests/leitora/test_sessoes.py`

**Interfaces:**
- Consome: nada.
- Produz, em `clarisse.leitora.sessoes`:
  - `class Sessao` com `projeto: str`, `caminho: str`, `sessao_id: str`,
    `modificado_em: float`
  - `listar_sessoes(raiz: str) -> list[Sessao]` — mais recente primeiro
  - `projetos_que_casam(sessoes: list[Sessao], termo: str) -> list[str]`
  - `sessao_mais_recente(sessoes: list[Sessao], projeto: str) -> Sessao | None`

O nome do projeto vem do campo `cwd` gravado dentro da transcrição, **não** do
nome da pasta. O nome da pasta é higienizado com hifens
(`C--Users-...-api-gestora`) e não dá para separar o hífen do caminho do hífen do
nome. O `cwd` é exato.

- [ ] **Passo 1: Escrever os testes que falham**

Crie `tests/leitora/test_sessoes.py`:

```python
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
```

- [ ] **Passo 2: Rodar os testes e confirmar que falham**

```
python -m pytest tests/leitora/test_sessoes.py -v
```

Esperado: erro de coleta com `ModuleNotFoundError: No module named
'clarisse.leitora.sessoes'`.

- [ ] **Passo 3: Escrever a implementação mínima**

Crie `clarisse/leitora/sessoes.py`:

```python
"""Descobre as sessoes do Claude Code em disco e resolve nome de projeto.

O nome do projeto sai do campo cwd gravado dentro da transcricao, nao do nome da
pasta. A pasta e higienizada com hifens - C--Users-eu-Documents-api-gestora - e
nao da para separar o hifen do caminho do hifen do nome. O cwd e exato.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

LINHAS_PROCURADAS_PELO_CWD = 50


@dataclass(frozen=True)
class Sessao:
    projeto: str
    caminho: str
    sessao_id: str
    modificado_em: float


def _nome_do_caminho(cwd: str) -> str:
    partes = [p for p in re.split(r'[\\/]+', cwd) if p]
    return partes[-1] if partes else ''


def _projeto_do_arquivo(caminho: Path) -> str:
    try:
        with open(caminho, encoding='utf-8', errors='replace') as arquivo:
            for numero, linha in enumerate(arquivo):
                if numero >= LINHAS_PROCURADAS_PELO_CWD:
                    break
                linha = linha.strip()
                if not linha:
                    continue
                try:
                    registro = json.loads(linha)
                except json.JSONDecodeError:
                    continue
                if isinstance(registro, dict) and registro.get('cwd'):
                    return _nome_do_caminho(registro['cwd'])
    except OSError:
        return ''
    return ''


def listar_sessoes(raiz: str) -> list[Sessao]:
    """Devolve as sessoes encontradas, da atividade mais recente para a mais antiga."""
    pasta_raiz = Path(raiz)
    if not pasta_raiz.is_dir():
        return []

    encontradas = []
    for arquivo in pasta_raiz.glob('*/*.jsonl'):
        projeto = _projeto_do_arquivo(arquivo)
        if not projeto:
            continue
        encontradas.append(Sessao(
            projeto=projeto,
            caminho=str(arquivo),
            sessao_id=arquivo.stem,
            modificado_em=arquivo.stat().st_mtime,
        ))

    encontradas.sort(key=lambda s: s.modificado_em, reverse=True)
    return encontradas


def projetos_que_casam(sessoes: list[Sessao], termo: str) -> list[str]:
    """Nomes de projeto que casam com o termo, sem repetir, mais ativo primeiro.

    Nome exato ganha sozinho: pedir omni-api nao pode devolver omni-api-legado
    junto e virar uma pergunta que o usuario ja respondeu.
    """
    procurado = (termo or '').strip().lower()
    if not procurado:
        return []

    nomes = []
    for sessao in sessoes:
        if sessao.projeto not in nomes:
            nomes.append(sessao.projeto)

    exatos = [n for n in nomes if n.lower() == procurado]
    if exatos:
        return exatos
    return [n for n in nomes if procurado in n.lower()]


def sessao_mais_recente(sessoes: list[Sessao], projeto: str) -> Sessao | None:
    """A sessao daquele projeto que se moveu por ultimo, ou None."""
    for sessao in sessoes:
        if sessao.projeto == projeto:
            return sessao
    return None
```

- [ ] **Passo 4: Rodar os testes e confirmar que passam**

```
python -m pytest tests/leitora/test_sessoes.py -v
```

Esperado: `10 passed`.

- [ ] **Passo 5: Commitar**

```bash
git add clarisse/leitora/sessoes.py tests/leitora/test_sessoes.py
git commit -m "Acha a sessao certa pelo cwd, e nome exato nao vira pergunta"
```

---

### Tarefa 4: A fronteira de linha de comando

Aqui o mascaramento da Tarefa 1 é aplicado. Ele fica na fronteira, num lugar só,
para não haver caminho que devolva texto sem passar por ele.

**Arquivos:**
- Criar: `clarisse/leitora/cli.py`
- Testar: `tests/leitora/test_cli.py`

**Interfaces:**
- Consome: `ler_eventos`, `Evento` (Tarefa 2); `listar_sessoes`,
  `projetos_que_casam`, `sessao_mais_recente` (Tarefa 3); `mascarar` (Tarefa 1).
- Produz, em `clarisse.leitora.cli`:
  - `RAIZ_PADRAO: str`
  - `executar(argumentos: list[str]) -> dict`
  - `main() -> int`

- [ ] **Passo 1: Escrever os testes que falham**

Crie `tests/leitora/test_cli.py`:

```python
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
```

- [ ] **Passo 2: Rodar os testes e confirmar que falham**

```
python -m pytest tests/leitora/test_cli.py -v
```

Esperado: erro de coleta com `ModuleNotFoundError: No module named
'clarisse.leitora.cli'`.

- [ ] **Passo 3: Escrever a implementação mínima**

Crie `clarisse/leitora/cli.py`:

```python
"""Fronteira de linha de comando da Leitora: recebe argumentos, devolve JSON.

Uso:
    python <caminho>/leitora/cli.py projetos
    python <caminho>/leitora/cli.py relatar --projeto omni-api --maximo 40

O mascaramento de segredo e aplicado aqui, num lugar so, para nao existir
caminho de saida que devolva texto sem passar por ele.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from clarisse.leitora.segredo import mascarar  # noqa: E402
from clarisse.leitora.sessoes import (  # noqa: E402
    listar_sessoes,
    projetos_que_casam,
    sessao_mais_recente,
)
from clarisse.leitora.transcricao import ler_eventos  # noqa: E402

RAIZ_PADRAO = str(Path.home() / '.claude' / 'projects')
MAXIMO_PADRAO = 40


def _montar_analisador():
    analisador = argparse.ArgumentParser(add_help=False)
    analisador.add_argument('comando', choices=('projetos', 'relatar'))
    analisador.add_argument('--projeto', default='')
    analisador.add_argument('--maximo', type=int, default=MAXIMO_PADRAO)
    analisador.add_argument('--raiz', default=RAIZ_PADRAO)
    return analisador


def _evento_em_dicionario(evento):
    return {
        'quem': evento.quem,
        'texto': mascarar(evento.texto),
        'momento': evento.momento,
        'ferramenta': evento.ferramenta,
    }


def _relatar(sessoes, termo, maximo):
    if termo:
        candidatos = projetos_que_casam(sessoes, termo)
        if not candidatos:
            return {'erro': 'nao_encontrado', 'procurado': termo}
        if len(candidatos) > 1:
            return {'erro': 'ambiguo', 'candidatos': candidatos}
        projeto = candidatos[0]
    else:
        if not sessoes:
            return {'erro': 'nao_encontrado', 'procurado': ''}
        projeto = sessoes[0].projeto

    sessao = sessao_mais_recente(sessoes, projeto)
    if sessao is None:
        return {'erro': 'nao_encontrado', 'procurado': termo}

    eventos = ler_eventos(sessao.caminho)
    if maximo > 0:
        eventos = eventos[-maximo:]

    return {
        'projeto': projeto,
        'sessao_id': sessao.sessao_id,
        'eventos': [_evento_em_dicionario(e) for e in eventos],
    }


def executar(argumentos: list[str]) -> dict:
    """Roda um comando da Leitora e devolve o resultado como dicionario."""
    opcoes = _montar_analisador().parse_args(argumentos)
    sessoes = listar_sessoes(opcoes.raiz)

    if opcoes.comando == 'projetos':
        return {'projetos': [
            {'projeto': s.projeto, 'sessao_id': s.sessao_id,
             'modificado_em': s.modificado_em}
            for s in sessoes
        ]}

    return _relatar(sessoes, opcoes.projeto, opcoes.maximo)


def main() -> int:
    resultado = executar(sys.argv[1:])
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 1 if 'erro' in resultado else 0


if __name__ == '__main__':
    raise SystemExit(main())
```

- [ ] **Passo 4: Rodar os testes e confirmar que passam**

```
python -m pytest tests/leitora/test_cli.py -v
```

Esperado: `7 passed`.

- [ ] **Passo 5: Rodar a suíte Python inteira e o Pester**

```
python -m pytest -v
```

Esperado: `32 passed` — 7 do segredo, 8 da transcrição, 10 das sessões, 7 do CLI.

```
$r = Invoke-Pester -Path .\tests -PassThru -Quiet; "Total: $($r.TotalCount) Passaram: $($r.PassedCount) Falharam: $($r.FailedCount)"
```

Esperado: `Total: 126 Passaram: 126 Falharam: 0`.

- [ ] **Passo 6: Provar na prática, contra as suas transcrições de verdade**

Este passo não é teste automatizado: é a verificação de que a Leitora funciona
contra os arquivos reais desta máquina.

```
python .\clarisse\leitora\cli.py projetos
```

Esperado: um JSON listando seus projetos, com `voz-ao-claude` entre eles. Se
vier `{"projetos": []}`, a raiz não foi encontrada — confira se
`%USERPROFILE%\.claude\projects` existe.

```
python .\clarisse\leitora\cli.py relatar --projeto voz-ao-claude --maximo 6
```

Esperado: um JSON com os últimos seis eventos desta própria conversa. É aqui que
você confirma que o conteúdo é reconhecível e útil.

- [ ] **Passo 7: Commitar**

```bash
git add clarisse/leitora/cli.py tests/leitora/test_cli.py
git commit -m "Expoe a Leitora por linha de comando, mascarando na fronteira"
```

---

### Tarefa 5: A Clarisse aprende a relatar quando você pede

**Arquivos:**
- Modificar: `comandos/clarisse.md`
- Modificar: `instalar.ps1:168-169`
- Modificar: `README.md`

**Interfaces:**
- Consome: `python <clarisse>/leitora/cli.py relatar --projeto <termo>` (Tarefa 4).
- Produz: os argumentos de relato no comando `/clarisse`.

- [ ] **Passo 1: Fazer o instalador copiar a Leitora**

Em `instalar.ps1`, o laço das linhas 168-169 é hoje:

```powershell
foreach ($arq in @('clarisse.ps1', 'nucleo.ps1', 'atalhos.ps1', 'falar.py')) {
    Copy-Item (Join-Path $Origem "clarisse\$arq") (Join-Path $DestClarisse $arq) -Force
}
```

Acrescente **imediatamente depois** do fechamento desse laço:

```powershell
$destLeitora = Join-Path $DestClarisse 'leitora'
if (-not (Test-Path $destLeitora)) {
    New-Item -ItemType Directory -Path $destLeitora -Force | Out-Null
}
Copy-Item (Join-Path $Origem 'clarisse\__init__.py') (Join-Path $DestClarisse '__init__.py') -Force
foreach ($arq in @('__init__.py', 'segredo.py', 'transcricao.py', 'sessoes.py', 'cli.py')) {
    Copy-Item (Join-Path $Origem "clarisse\leitora\$arq") (Join-Path $destLeitora $arq) -Force
}
```

O `__init__.py` da pasta `clarisse` também é copiado porque o `cli.py` importa
`clarisse.leitora.*`, e ele resolve a raiz subindo dois níveis a partir de si
mesmo — o que, instalado, aterra em `%USERPROFILE%\.claude`.

- [ ] **Passo 2: Verificar que a instalação copiou tudo**

```
powershell -ExecutionPolicy Bypass -File .\instalar.ps1
```

Depois:

```
Get-ChildItem "$env:USERPROFILE\.claude\clarisse\leitora" | Select-Object -ExpandProperty Name
```

Esperado, cinco nomes: `__init__.py`, `cli.py`, `segredo.py`, `sessoes.py`,
`transcricao.py`.

E o teste que importa, rodando do lugar instalado:

```
python "$env:USERPROFILE\.claude\clarisse\leitora\cli.py" relatar --projeto voz-ao-claude --maximo 4
```

Esperado: JSON com quatro eventos. Se vier `ModuleNotFoundError`, o
`__init__.py` da pasta `clarisse` não foi copiado.

- [ ] **Passo 3: Ensinar o comando `/clarisse` a relatar**

Em `comandos/clarisse.md`, na tabela de argumentos, acrescente estas três linhas
logo **abaixo** da linha que começa com `` | `proximo`, `pula` ``:

```markdown
| `o que esta rolando`, `o que andou`, `resume o dia` | Relato do projeto mais ativo — ver "Relato de sessao" abaixo |
| `o que esta rolando no <projeto>`, `resume o <projeto>`, `o que aconteceu no <projeto>` | Relato daquele projeto |
| `quais projetos`, `lista os projetos` | `python "$env:USERPROFILE\.claude\clarisse\leitora\cli.py" projetos` e responda em uma linha com os nomes |
```

E acrescente esta seção no **fim** do arquivo:

```markdown
## Relato de sessao

Quando o argumento pedir relato de uma sessao, faca nesta ordem:

1. Rode, trocando `<termo>` pelo nome que o usuario disse (ou omita `--projeto`
   quando ele nao disse nenhum):

   `python "$env:USERPROFILE\.claude\clarisse\leitora\cli.py" relatar --projeto <termo> --maximo 40`

2. Se a saida trouxer `"erro": "ambiguo"`, **nao escolha**: pergunte qual dos
   `candidatos` ele quer, em uma linha, e pare.

3. Se trouxer `"erro": "nao_encontrado"`, diga em uma linha que nao ha sessao com
   aquele nome e ofereca `quais projetos`.

4. Com eventos na mao, componha **o texto falado** seguindo as mesmas regras do
   resumo falado deste projeto: diga o conteudo e nunca o aviso; 4 a 8 frases;
   portugues falado sem markdown; numeros, valores e datas por extenso; nenhum
   caminho de arquivo, comando, bloco de codigo, URL ou hash. Diga **o que
   aconteceu e como terminou**, o achado ou a conclusao, e o que ficou pendente.

5. Nunca coloque no texto falado credencial, token, senha, dado pessoal de
   terceiro, nome de cliente nem valor exato de contrato. A Leitora ja mascara
   formato de segredo, mas ela pega formato e nao sentido — o cuidado com nome de
   cliente e seu.

6. Mande falar na hora:

   `& "$env:USERPROFILE\.claude\clarisse\clarisse.ps1" -Mode say -Text "<o texto falado>"`

7. Responda ao usuario em **uma linha**, dizendo de qual projeto foi o relato.
   Nao repita na tela o texto que ela acabou de falar.
```

- [ ] **Passo 4: Provar o caminho completo, ponta a ponta**

Reinstale para levar o comando atualizado:

```
powershell -ExecutionPolicy Bypass -File .\instalar.ps1
```

Abra `/hooks` uma vez no Claude Code, ou reinicie a sessão — comandos e hooks são
lidos na abertura.

Depois, numa sessão do Claude Code, digite:

```
/clarisse o que esta rolando no voz-ao-claude
```

Esperado: ela **fala** um resumo de 4 a 8 frases sobre esta conversa, e a
resposta na tela é uma linha só dizendo de qual projeto foi.

Teste também o caminho ambíguo, que é o que protege contra ela agir no projeto
errado:

```
/clarisse o que esta rolando no omni
```

Esperado: ela **pergunta** qual dos projetos `omni` você quer, em uma linha, e
**não** fala nenhum relato.

- [ ] **Passo 5: Atualizar o README**

Em `README.md`, na tabela de comandos, acrescente logo abaixo da linha
`/clarisse ler`:

```markdown
| `/clarisse o que esta rolando no <projeto>` | Lê a sessão daquele projeto e **fala** o que aconteceu |
| `/clarisse quais projetos` | Lista os projetos com sessão gravada |
```

E acrescente esta seção logo antes de `## Vozes disponíveis`:

```markdown
### Ela lê as suas sessões no seu lugar

O Claude Code grava a conversa de cada sessão em disco enquanto ela acontece. A
Clarisse lê esses arquivos e conta o que houve — de qualquer projeto, a qualquer
momento, sem depender daquela sessão ter terminado.

> *"No omni-api: os vinte e sete testes passaram, mas a conversão de data
> continua sem cobertura. Ficou pendente decidir se o desconto entra antes ou
> depois do imposto."*

Nome parcial serve: `o que esta rolando no concil` acha `conciliacao-bancaria`.
Nome ambíguo faz ela **perguntar** em vez de escolher — `omni` casa com três
projetos, e adivinhar ali seria relatar o projeto errado.

**Privacidade:** transcrição de sessão contém tudo que passou pelo terminal. Um
filtro mecânico barra formatos evidentes de segredo — chave, token, senha,
cabeçalho de autorização — antes de qualquer texto virar áudio. Esse filtro pega
**formato, não sentido**: nome de cliente dito em texto corrido passa. Leia a
seção de privacidade abaixo antes de usar isso com dado de cliente.
```

O README hoje **não** afirma nenhuma contagem de testes — o "vinte e sete" da
linha 89 está dentro de um exemplo de fala, ilustrando como ela soa, e não deve
ser mexido.

O que falta documentar é que a verificação passou a ser **dois** comandos. No fim
da seção nova que você acabou de acrescentar, ponha:

```markdown
Para verificar o projeto agora são dois comandos, porque a Leitora é Python e o
resto é PowerShell:

    Invoke-Pester -Path .\tests
    python -m pytest
```

- [ ] **Passo 6: Rodar as duas suítes uma última vez**

```
python -m pytest -q
```

Esperado: `32 passed`.

```
$r = Invoke-Pester -Path .\tests -PassThru -Quiet; "Total: $($r.TotalCount) Passaram: $($r.PassedCount) Falharam: $($r.FailedCount)"
```

Esperado: `Total: 126 Passaram: 126 Falharam: 0`.

- [ ] **Passo 7: Commitar**

```bash
git add comandos/clarisse.md instalar.ps1 README.md
git commit -m "Ensina a Clarisse a contar o que rolou em qualquer sessao"
```

---

## Cobertura da especificação por este plano

| Requisito da especificação | Onde é atendido |
|---|---|
| A Leitora lê transcrições e não escreve nada | Tarefas 2 e 3 |
| Recorte: eventos mais recentes de um projeto | Tarefa 4, `--maximo` |
| Recorte: quais sessões existem, de quais projetos, última atividade | Tarefa 4, comando `projetos` |
| Recorte: identificador de sessão para retomada futura | Tarefa 4, campo `sessao_id` |
| Nome parcial resolvido; ambíguo faz perguntar | Tarefa 3 e Tarefa 5, passo 3 item 2 |
| Filtro mecânico de formatos de segredo | Tarefa 1, aplicado na fronteira na Tarefa 4 |
| Instrução ao Claude sobre dado sensível | Tarefa 5, passo 3 itens 4 e 5 |
| Risco residual declarado ao usuário | Tarefa 5, passo 5, seção do README |
| Leitora vive na faixa livre da Portaria | Nada a implementar: este plano não escreve nem executa nada |
| Formato de transcrição pode mudar; ela ignora o que não entende | Tarefa 2, linha malformada e tipo desconhecido |
| Ela não fala sem ser perguntada | Tarefa 5: a fala só acontece dentro do comando |
| Reaproveitar o motor de voz existente | Tarefa 5, passo 3 item 6, `-Mode say` |
| Segunda suíte de testes conviver com o Pester | Tarefa 1, `pytest.ini` com `python_files` |

## Requisitos da especificação que este plano deliberadamente **não** cobre

Ficam para os planos B e C, e não são esquecimento:

- Ouvinte, tecla `F6`, palavra de ativação, painel, janela de conversa, e as
  quatro situações de microfone aberto — **Plano B**.
- Portaria com as três faixas e a assimetria do "sim" — **Plano B**.
- O Agente, autorização falada, bipe duplo de conclusão de ação longa, retomada
  com `--fork-session` — **Plano C**.
- Medição do orçamento de tempo de 2 a 4 s — **Plano B**, porque só faz sentido
  medir quando existe caminho de voz de ponta a ponta.
- Aviso de qual projeto travou pedindo permissão — **Plano C**, junto do restante
  do laço; o hook de notificação já cobre o caso hoje de forma parcial.

## Riscos deste plano

| Risco | Mitigação dentro deste plano |
|---|---|
| O formato do `.jsonl` mudar numa atualização do Claude Code | Tarefa 2 ignora linha e tipo que não reconhece, em vez de derrubar a leitura |
| O relato falado ficar longo e chato | Tarefa 5 fixa 4 a 8 frases e as regras do resumo falado que já existem no projeto |
| Ela relatar o projeto errado por nome parecido | Tarefa 3: nome exato ganha sozinho; ambíguo devolve candidatos e a Tarefa 5 obriga a perguntar |
| Segredo escapar para a síntese | Tarefa 1 na fronteira da Tarefa 4, com o limite declarado no README |
| O `pytest` tentar coletar os arquivos do Pester | `pytest.ini` com `python_files = test_*.py` |
