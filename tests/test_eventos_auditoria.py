import json

from clarisse.auditoria import Auditoria
from clarisse.eventos import Estado, Eventos


async def test_evento_chega_a_todos_os_assinantes():
    eventos = Eventos()
    a, b = eventos.assinar(), eventos.assinar()

    await eventos.publicar({"tipo": "resposta", "texto": "oi"})

    assert (await a.get())["texto"] == "oi"
    assert (await b.get())["texto"] == "oi"


async def test_estado_vira_evento_e_fica_guardado():
    eventos = Eventos()
    fila = eventos.assinar()

    await eventos.estado(Estado.PENSANDO)

    evento = await fila.get()
    assert evento["tipo"] == "estado"
    assert evento["estado"] == "thinking"
    assert "quando" in evento
    assert eventos.estado_atual is Estado.PENSANDO


async def test_assinante_que_parou_de_ler_e_descartado():
    eventos = Eventos(tamanho_da_fila=2)
    parado = eventos.assinar()
    ativo = eventos.assinar()

    for i in range(3):
        await eventos.publicar({"tipo": "x", "i": i})
        await ativo.get()

    assert parado not in eventos.assinantes
    assert ativo in eventos.assinantes


async def test_cancelar_assinatura():
    eventos = Eventos()
    fila = eventos.assinar()

    eventos.cancelar(fila)

    assert fila not in eventos.assinantes


def test_auditoria_grava_uma_linha_json_por_execucao(tmp_path):
    auditoria = Auditoria(tmp_path / "sub" / "auditoria.jsonl")

    auditoria.registrar(ferramenta="git", argumentos={"projeto": "omni-api"}, risco="seguro", situacao="ok", duracao_ms=12)
    auditoria.registrar(ferramenta="abrir_site", argumentos={}, risco="seguro", situacao="erro", duracao_ms=3)

    linhas = (tmp_path / "sub" / "auditoria.jsonl").read_text(encoding="utf-8").splitlines()
    primeira = json.loads(linhas[0])
    assert len(linhas) == 2
    assert primeira["ferramenta"] == "git"
    assert primeira["argumentos"] == {"projeto": "omni-api"}
    assert "quando" in primeira
