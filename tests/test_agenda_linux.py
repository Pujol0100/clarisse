import asyncio

from clarisse.agenda_linux import agendas_do_microsoft365, atualizar_agendas, manter_agendas_atualizadas
from clarisse.ferramentas.processos import Resultado

FABRICA = "/org/gnome/evolution/dataserver/CalendarFactory"


def _fonte(pasta, uid, backend, secao="Calendar"):
    (pasta / f"{uid}.source").write_text(
        f"[Data Source]\nDisplayName=x\nEnabled=true\n\n[{secao}]\nBackendName={backend}\nSelected=true\n",
        encoding="utf-8",
    )


def test_acha_so_as_agendas_do_microsoft365(tmp_path):
    conta = tmp_path / "conta"
    conta.mkdir()
    _fonte(conta, "agenda-trabalho", "microsoft365")
    _fonte(conta, "feriados", "microsoft365")
    _fonte(conta, "contatos", "microsoft365", secao="Address Book")
    _fonte(conta, "pessoal", "local")

    assert sorted(agendas_do_microsoft365(tmp_path)) == ["agenda-trabalho", "feriados"]


def test_pasta_inexistente_nao_tem_agenda(tmp_path):
    assert agendas_do_microsoft365(tmp_path / "nada") == []


async def test_abre_e_atualiza_cada_agenda_pelo_servico_do_linux(executor):
    executor.respostas = [
        Resultado(0, "('/org/gnome/evolution/dataserver/Subprocess/9769/2', 'org.gnome.evolution.dataserver.Calendar8')\n", ""),
        Resultado(0, "", ""),
        Resultado(0, "()\n", ""),
    ]

    await atualizar_agendas(executor, ["agenda-trabalho"])

    abrir, abrir_objeto, atualizar = [argumentos for argumentos, _ in executor.executados]
    assert abrir[:3] == ["gdbus", "call", "--session"]
    assert FABRICA in abrir and abrir[-1] == "agenda-trabalho"
    assert "org.gnome.evolution.dataserver.CalendarFactory.OpenCalendar" in abrir
    assert "/org/gnome/evolution/dataserver/Subprocess/9769/2" in abrir_objeto
    assert "org.gnome.evolution.dataserver.Calendar.Open" in abrir_objeto
    assert "org.gnome.evolution.dataserver.Calendar.Refresh" in atualizar


async def test_falha_ao_abrir_uma_agenda_nao_impede_as_outras(executor):
    executor.respostas = [
        Resultado(1, "", "Error: source not found"),
        Resultado(0, "('/org/gnome/evolution/dataserver/Subprocess/1/3', 'x')\n", ""),
        Resultado(0, "", ""),
        Resultado(0, "()\n", ""),
    ]

    await atualizar_agendas(executor, ["quebrada", "boa"])

    assert executor.executados[-1][0][-1] == "org.gnome.evolution.dataserver.Calendar.Refresh"


async def test_mantem_atualizada_no_intervalo_ate_ser_cancelada(executor):
    executor.respostas = []
    tarefa = asyncio.create_task(manter_agendas_atualizadas(executor, lambda: ["a"], intervalo=0.01))

    await asyncio.sleep(0.05)
    tarefa.cancel()

    aberturas = [a for a, _ in executor.executados if "org.gnome.evolution.dataserver.CalendarFactory.OpenCalendar" in a]
    assert len(aberturas) >= 2
