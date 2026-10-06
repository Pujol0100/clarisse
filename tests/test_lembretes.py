"""Lembretes guardados na máquina e falados na hora certa."""
import json
from datetime import datetime

from clarisse.ferramentas.lembretes import Lembretes, disparar_vencidos, ferramentas_de_lembretes

AGORA = datetime(2026, 10, 1, 14, 15)


def _ferramentas(tmp_path, agora=AGORA):
    lembretes = Lembretes(tmp_path / "lembretes.json")
    return lembretes, {f.nome: f for f in ferramentas_de_lembretes(lembretes, agora=lambda: agora)}


async def _chamar(ferramentas, nome, **argumentos):
    f = ferramentas[nome]
    return await f.executar(f.argumentos(**argumentos))


async def test_lembrar_daqui_a_minutos_guarda_no_arquivo(tmp_path):
    lembretes, ferramentas = _ferramentas(tmp_path)

    resposta = await _chamar(ferramentas, "lembrar", texto="ligar para o financeiro", em_minutos=20)

    assert resposta.texto == "Combinado: hoje às 14:35 eu lembro de ligar para o financeiro."
    assert json.loads((tmp_path / "lembretes.json").read_text(encoding="utf-8")) == [
        {"quando": "2026-10-01T14:35:00", "texto": "ligar para o financeiro"},
    ]


async def test_horario_que_ja_passou_fica_para_amanha(tmp_path):
    _, ferramentas = _ferramentas(tmp_path)

    resposta = await _chamar(ferramentas, "lembrar", texto="tomar remédio", horario="09:00")

    assert resposta.texto == "Combinado: amanhã às 09:00 eu lembro de tomar remédio."


async def test_sem_quando_pede_o_horario(tmp_path):
    _, ferramentas = _ferramentas(tmp_path)

    resposta = await _chamar(ferramentas, "lembrar", texto="algo")

    assert resposta == "Diga quando: daqui a quantos minutos ou a que horas."


async def test_lista_e_cancela_pelo_numero(tmp_path):
    lembretes, ferramentas = _ferramentas(tmp_path)
    await _chamar(ferramentas, "lembrar", texto="segundo", em_minutos=60)
    await _chamar(ferramentas, "lembrar", texto="primeiro", em_minutos=5)

    lista = await _chamar(ferramentas, "listar_lembretes")
    cancelado = await _chamar(ferramentas, "cancelar_lembrete", numero=1)

    assert lista.cartao == {"tipo": "lista", "titulo": "Lembretes", "canto": "2 marcados",
                            "itens": [["14:20", "primeiro"], ["15:15", "segundo"]]}
    assert cancelado == "Cancelei o lembrete de primeiro."
    assert [l["texto"] for l in lembretes.todos()] == ["segundo"]


async def test_sem_lembretes(tmp_path):
    _, ferramentas = _ferramentas(tmp_path)

    resposta = await _chamar(ferramentas, "listar_lembretes")

    assert resposta.texto == "Nenhum lembrete marcado."


async def test_dispara_so_os_vencidos_e_tira_da_lista(tmp_path):
    lembretes = Lembretes(tmp_path / "lembretes.json")
    lembretes.adicionar(datetime(2026, 10, 1, 14, 10), "venceu")
    lembretes.adicionar(datetime(2026, 10, 1, 16, 0), "ainda não")
    avisados = []

    async def avisar(titulo, texto, falar=None):
        avisados.append((titulo, texto, falar))

    await disparar_vencidos(lembretes, avisar, AGORA)

    assert avisados == [("Lembrete", "venceu", "Lembrete: venceu.")]
    assert [l["texto"] for l in lembretes.todos()] == ["ainda não"]
