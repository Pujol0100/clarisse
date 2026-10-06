import json
import os

from clarisse.ferramentas.leitura import ferramentas_de_leitura
from clarisse.ferramentas.processos import Resultado
from clarisse.cartoes import Retorno


def _linha(tipo, conteudo, **extra):
    return {"type": tipo, "message": {"role": tipo, "content": conteudo}, **extra}


CONVERSA = [
    _linha("user", "primeira pergunta"),
    _linha("assistant", [{"type": "text", "text": "Resposta antiga."}]),
    _linha("user", "segunda pergunta"),
    _linha("assistant", [{"type": "thinking", "thinking": "pensando alto"}]),
    _linha("assistant", [{"type": "text", "text": "Vou conferir o arquivo."}]),
    _linha("assistant", [{"type": "tool_use", "name": "Bash", "input": {}}]),
    _linha("user", [{"type": "tool_result", "content": "saída do comando"}]),
    _linha("assistant", [{"type": "text", "text": "Achei o problema."}], isSidechain=True),
    _linha("assistant", [{"type": "text", "text": "O arquivo está certo."}]),
]


def _gravar(caminho, linhas, idade=0):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("\n".join(json.dumps(l, ensure_ascii=False) for l in linhas) + "\n", encoding="utf-8")
    os.utime(caminho, (1_800_000_000 - idade, 1_800_000_000 - idade))


def _ferramenta(executor, tmp_path, cadastros=None):
    [f] = ferramentas_de_leitura(executor, pasta_das_conversas=tmp_path / "projects", cadastros=cadastros)
    return f


def _pasta_das_conversas_do(caminho):
    return "".join(c if c.isalnum() else "-" for c in str(caminho))


async def test_le_na_integra_o_que_o_claude_respondeu_depois_da_ultima_pergunta(executor, tmp_path):
    _gravar(tmp_path / "projects" / "-home-x-proj" / "sessao-a.jsonl", CONVERSA)
    f = _ferramenta(executor, tmp_path)

    resultado = await f.executar(f.argumentos())

    assert isinstance(resultado, Retorno) and resultado.na_integra
    assert resultado.texto == "Vou conferir o arquivo.\n\nO arquivo está certo."


async def test_sem_nome_usa_a_conversa_mais_recente(executor, tmp_path):
    _gravar(tmp_path / "projects" / "-home-x-a" / "velha.jsonl", [_linha("user", "p"), _linha("assistant", [{"type": "text", "text": "Velha."}])], idade=500)
    _gravar(tmp_path / "projects" / "-home-x-b" / "nova.jsonl", [_linha("user", "p"), _linha("assistant", [{"type": "text", "text": "Nova."}])])
    f = _ferramenta(executor, tmp_path)

    resultado = await f.executar(f.argumentos())

    assert resultado.texto == "Nova."


async def test_pelo_nome_acha_a_conversa_aberta(executor, tmp_path):
    _gravar(tmp_path / "projects" / "-home-x-meus-programas-clarisse" / "abc.jsonl", [_linha("user", "p"), _linha("assistant", [{"type": "text", "text": "Da clarisse."}])], idade=500)
    _gravar(tmp_path / "projects" / "-home-x-outro" / "def.jsonl", [_linha("user", "p"), _linha("assistant", [{"type": "text", "text": "De outra."}])])
    executor.respostas.append(Resultado(0, json.dumps([
        {"name": "clarisse", "cwd": "/home/x/meus.programas/clarisse", "sessionId": "abc"},
        {"name": "omni", "cwd": "/home/x/outro", "sessionId": "def"},
    ]), ""))
    f = _ferramenta(executor, tmp_path)

    resultado = await f.executar(f.argumentos(conversa="Clarisse"))

    assert executor.executados[0][0] == ["claude", "agents", "--json"]
    assert resultado.texto == "Da clarisse."


async def test_nome_que_nao_existe_diz_quais_conversas_estao_abertas(executor, tmp_path):
    executor.respostas.append(Resultado(0, json.dumps([{"name": "omni", "cwd": "/home/x", "sessionId": "d"}]), ""))
    f = _ferramenta(executor, tmp_path)

    resultado = await f.executar(f.argumentos(conversa="financeiro"))

    assert "omni" in resultado and "financeiro" in resultado


async def test_sem_nenhuma_conversa(executor, tmp_path):
    f = _ferramenta(executor, tmp_path)

    resultado = await f.executar(f.argumentos())

    assert "não achei" in resultado.lower()


async def test_pelo_projeto_le_a_conversa_mais_recente_dele(executor, tmp_path, cadastros):
    pasta = tmp_path / "projects" / _pasta_das_conversas_do(cadastros.projetos["omni-api"])
    resposta = lambda texto: [_linha("user", "p"), _linha("assistant", [{"type": "text", "text": texto}])]  # noqa: E731
    _gravar(pasta / "velha.jsonl", resposta("Do omni, velha."), idade=900)
    _gravar(pasta / "nova.jsonl", resposta("Do omni, nova."), idade=300)
    _gravar(tmp_path / "projects" / "-home-x-outro" / "mais-nova.jsonl", resposta("De outro projeto."))
    f = _ferramenta(executor, tmp_path, cadastros)

    resultado = await f.executar(f.argumentos(projeto="Omni API"))

    assert resultado.texto == "Do omni, nova."
    assert executor.executados == []


async def test_projeto_sem_conversa_do_claude_avisa(executor, tmp_path, cadastros):
    f = _ferramenta(executor, tmp_path, cadastros)

    resultado = await f.executar(f.argumentos(projeto="omni-api"))

    assert resultado == "Não achei conversa do Claude no projeto omni-api."


async def test_projeto_que_nao_esta_cadastrado_diz_os_cadastrados(executor, tmp_path, cadastros):
    f = _ferramenta(executor, tmp_path, cadastros)

    resultado = await f.executar(f.argumentos(projeto="financeiro"))

    assert "financeiro" in resultado and "omni-api" in resultado


async def test_pelo_projeto_acha_a_conversa_aberta_na_pasta_geral_que_mexeu_nele(executor, tmp_path, cadastros):
    projeto = cadastros.projetos["omni-api"]
    geral = tmp_path / "projects" / "C--Users-x-PROGRAMASSMART"
    leu_o_projeto = [
        _linha("user", "olha o omni"),
        _linha("assistant", [{"type": "tool_use", "name": "Read", "input": {"file_path": f"{projeto}\\src\\main.ts"}}]),
        _linha("assistant", [{"type": "text", "text": "O main.ts do omni está certo."}]),
    ]
    _gravar(geral / "do-omni.jsonl", leu_o_projeto, idade=600)
    _gravar(geral / "de-outro.jsonl", [_linha("user", "p"), _linha("assistant", [{"type": "text", "text": "Outra coisa."}])])
    f = _ferramenta(executor, tmp_path, cadastros)

    resultado = await f.executar(f.argumentos(projeto="omni-api"))

    assert resultado.texto == "O main.ts do omni está certo."


async def test_conversa_numa_worktree_do_projeto_tambem_conta(executor, tmp_path, cadastros):
    geral = tmp_path / "projects" / "C--Users-x-PROGRAMASSMART"
    na_worktree = [
        _linha("user", "segue"),
        _linha("assistant", [{"type": "tool_use", "name": "Bash", "input": {"command": "cd C:/Users/x/.config/superpowers/worktrees/omni-api/minha-branch && git status"}}]),
        _linha("assistant", [{"type": "text", "text": "Feito na worktree."}]),
    ]
    _gravar(geral / "worktree.jsonl", na_worktree)
    f = _ferramenta(executor, tmp_path, cadastros)

    resultado = await f.executar(f.argumentos(projeto="omni-api"))

    assert resultado.texto == "Feito na worktree."


async def test_conversa_que_so_cita_o_caminho_num_texto_nao_conta_como_do_projeto(executor, tmp_path, cadastros):
    projeto = cadastros.projetos["omni-api"]
    geral = tmp_path / "projects" / "C--Users-x-PROGRAMASSMART"
    _gravar(geral / "mexeu.jsonl", [
        _linha("user", "p"),
        _linha("assistant", [{"type": "tool_use", "name": "Edit", "input": {"file_path": f"{projeto}\\a.ts"}}]),
        _linha("assistant", [{"type": "text", "text": "Mexi no omni."}]),
    ], idade=600)
    _gravar(geral / "so-citou.jsonl", [
        _linha("user", f"o projeto fica em {projeto}\\"),
        _linha("user", [{"type": "tool_result", "content": f"{projeto}\\x.ts"}]),
        _linha("assistant", [{"type": "text", "text": f"Anotei {projeto}\\ e mais nada."}]),
    ])
    f = _ferramenta(executor, tmp_path, cadastros)

    resultado = await f.executar(f.argumentos(projeto="omni-api"))

    assert resultado.texto == "Mexi no omni."


async def test_conversa_que_estava_dentro_da_pasta_do_projeto_conta(executor, tmp_path, cadastros):
    projeto = cadastros.projetos["omni-api"]
    _gravar(tmp_path / "projects" / "C--Users-x-PROGRAMASSMART" / "entrou.jsonl", [
        _linha("user", "p", cwd=f"{projeto}\\src"),
        _linha("assistant", [{"type": "text", "text": "Estava dentro do omni."}], cwd=f"{projeto}\\src"),
    ])
    f = _ferramenta(executor, tmp_path, cadastros)

    resultado = await f.executar(f.argumentos(projeto="omni-api"))

    assert resultado.texto == "Estava dentro do omni."


async def test_comando_com_barra_normal_e_drive_minusculo_conta(executor, tmp_path, cadastros):
    projeto = cadastros.projetos["omni-api"]
    caminho_do_bash = projeto.as_posix().replace(projeto.drive, projeto.drive.lower(), 1)
    _gravar(tmp_path / "projects" / "C--Users-x-PROGRAMASSMART" / "bash.jsonl", [
        _linha("user", "roda os testes"),
        _linha("assistant", [{"type": "tool_use", "name": "Bash", "input": {"command": f"cd {caminho_do_bash}/ && npm test"}}]),
        _linha("assistant", [{"type": "text", "text": "Testes do omni verdes."}]),
    ])
    f = _ferramenta(executor, tmp_path, cadastros)

    resultado = await f.executar(f.argumentos(projeto="omni-api"))

    assert resultado.texto == "Testes do omni verdes."


async def test_conversa_aberta_na_propria_pasta_do_projeto_conta(executor, tmp_path, cadastros):
    projeto = cadastros.projetos["omni-api"]
    _gravar(tmp_path / "projects" / "C--Users-x-PROGRAMASSMART" / "na-raiz.jsonl", [
        _linha("user", "p", cwd=str(projeto)),
        _linha("assistant", [{"type": "text", "text": "Na raiz do omni."}], cwd=str(projeto)),
    ])
    f = _ferramenta(executor, tmp_path, cadastros)

    resultado = await f.executar(f.argumentos(projeto="omni-api"))

    assert resultado.texto == "Na raiz do omni."
