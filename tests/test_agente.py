import asyncio
import json
from datetime import datetime

import pytest
from pydantic import Field

from clarisse.agente import Agente
from clarisse.auditoria import Auditoria
from clarisse.eventos import Eventos
from clarisse.ferramentas.registro import Argumentos, Ferramenta, Registro, Risco
from clarisse.llm import ChamadaDeFerramenta, ErroDoModelo, RespostaDoModelo


class ModeloFalso:
    """Devolve respostas roteirizadas e guarda o que recebeu."""

    def __init__(self, *roteiro):
        self.roteiro = list(roteiro)
        self.recebidas: list[list[dict]] = []

    async def conversar(self, mensagens, ferramentas):
        self.recebidas.append([dict(m) for m in mensagens])
        passo = self.roteiro.pop(0)
        if isinstance(passo, Exception):
            raise passo
        return passo


def texto(t):
    return RespostaDoModelo(t, [], {"role": "assistant", "content": t})


def chamada(nome, **argumentos):
    return RespostaDoModelo(
        "", [ChamadaDeFerramenta(nome, argumentos)],
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": nome, "arguments": argumentos}}]},
    )


class ArgsGit(Argumentos):
    projeto: str
    operacao: str = Field(pattern="^(status|pull)$")


@pytest.fixture
def executadas():
    return []


@pytest.fixture
def registro(executadas):
    async def git(args):
        executadas.append(("git", args.operacao))
        return f"git {args.operacao}: limpo"

    async def quebra(args):
        raise RuntimeError("disco cheio")

    r = Registro()
    r.registrar(Ferramenta(
        "git", "git", ArgsGit, git,
        risco=lambda a: Risco.CONFIRMAR if a.operacao == "pull" else Risco.SEGURO,
        descrever=lambda a: f"Vou dar pull no {a.projeto}. Confirma?",
    ))
    r.registrar(Ferramenta("quebra", "quebra", Argumentos, quebra))
    return r


@pytest.fixture
def auditoria(tmp_path):
    return Auditoria(tmp_path / "auditoria.jsonl")


@pytest.fixture
def eventos():
    return Eventos()


@pytest.fixture
def novo_agente(registro, eventos, auditoria):
    def _novo(modelo):
        return Agente(
            modelo, registro, eventos, auditoria,
            projetos=["omni-api", "smart-cep"], agora=lambda: datetime(2026, 9, 28, 14, 5), max_rodadas=3,
        )
    return _novo


def _mensagens_de_ferramenta(mensagens):
    return [m["content"] for m in mensagens if m["role"] == "tool"]


async def test_responde_sem_ferramenta_com_data_e_projetos_no_prompt(novo_agente):
    modelo = ModeloFalso(texto("Oi! Tudo bem."))

    resposta = await novo_agente(modelo).responder("oi clarisse")

    assert resposta.texto == "Oi! Tudo bem."
    sistema, usuario = modelo.recebidas[0][0], modelo.recebidas[0][-1]
    assert sistema["role"] == "system"
    assert "28 de setembro de 2026" in sistema["content"]
    assert "omni-api" in sistema["content"]
    assert usuario == {"role": "user", "content": "oi clarisse"}


async def test_ferramenta_segura_executa_e_o_resultado_volta_ao_modelo(novo_agente, executadas):
    modelo = ModeloFalso(chamada("git", projeto="omni-api", operacao="status"), texto("Está limpo."))

    resposta = await novo_agente(modelo).responder("git status no omni")

    assert executadas == [("git", "status")]
    assert _mensagens_de_ferramenta(modelo.recebidas[1]) == ["git status: limpo"]
    assert resposta.texto == "Está limpo."


async def test_ferramenta_de_risco_pergunta_e_so_executa_depois_do_sim(novo_agente, executadas):
    modelo = ModeloFalso(chamada("git", projeto="omni-api", operacao="pull"), texto("Atualizado."))
    agente = novo_agente(modelo)

    pergunta = await agente.responder("atualiza o omni")

    assert pergunta.texto == "Vou dar pull no omni-api. Confirma?"
    assert pergunta.aguardando_confirmacao
    assert executadas == []

    resposta = await agente.responder("sim, pode")

    assert executadas == [("git", "pull")]
    assert resposta.texto == "Atualizado."


async def test_nao_cancela_a_acao_pendente_sem_chamar_o_modelo(novo_agente, executadas):
    modelo = ModeloFalso(chamada("git", projeto="omni-api", operacao="pull"))
    agente = novo_agente(modelo)
    await agente.responder("atualiza o omni")

    resposta = await agente.responder("não")

    assert executadas == []
    assert "cancelei" in resposta.texto.lower()
    assert len(modelo.recebidas) == 1


async def test_outro_pedido_cancela_a_acao_pendente_e_e_atendido(novo_agente, executadas):
    modelo = ModeloFalso(chamada("git", projeto="omni-api", operacao="pull"), texto("São 14h05."))
    agente = novo_agente(modelo)
    await agente.responder("atualiza o omni")

    resposta = await agente.responder("que horas são?")

    assert executadas == []
    assert resposta.texto == "São 14h05."
    assert modelo.recebidas[1][-1] == {"role": "user", "content": "que horas são?"}


async def test_ferramenta_inexistente_volta_como_erro_ao_modelo(novo_agente):
    modelo = ModeloFalso(chamada("formatar_disco"), texto("Não posso fazer isso."))

    resposta = await novo_agente(modelo).responder("formata o disco")

    [erro] = _mensagens_de_ferramenta(modelo.recebidas[1])
    assert "formatar_disco" in erro
    assert resposta.texto == "Não posso fazer isso."


async def test_excecao_da_ferramenta_nao_derruba_o_agente(novo_agente):
    modelo = ModeloFalso(chamada("quebra"), texto("Deu erro: disco cheio."))

    resposta = await novo_agente(modelo).responder("quebra")

    [erro] = _mensagens_de_ferramenta(modelo.recebidas[1])
    assert "disco cheio" in erro
    assert resposta.texto == "Deu erro: disco cheio."


async def test_limite_de_rodadas(novo_agente):
    modelo = ModeloFalso(*[chamada("git", projeto="omni-api", operacao="status")] * 3)

    resposta = await novo_agente(modelo).responder("git status em loop")

    assert len(modelo.recebidas) == 3
    assert "não consegui concluir" in resposta.texto.lower()


async def test_parar_nao_chama_o_modelo_e_descarta_a_pendencia(novo_agente, executadas):
    modelo = ModeloFalso(chamada("git", projeto="omni-api", operacao="pull"), texto("ok"))
    agente = novo_agente(modelo)
    await agente.responder("atualiza o omni")

    resposta = await agente.responder("para, Clarisse")
    depois = await agente.responder("sim")

    assert resposta.parar
    assert executadas == []
    assert depois.texto == "ok"


async def test_modelo_fora_do_ar_vira_resposta_legivel(novo_agente):
    modelo = ModeloFalso(ErroDoModelo("o Ollama não respondeu: ConnectError"))

    resposta = await novo_agente(modelo).responder("oi")

    assert "modelo local" in resposta.texto.lower()


async def test_execucao_fica_na_auditoria(novo_agente, tmp_path):
    modelo = ModeloFalso(chamada("git", projeto="omni-api", operacao="status"), texto("ok"))

    await novo_agente(modelo).responder("git status")

    [linha] = (tmp_path / "auditoria.jsonl").read_text(encoding="utf-8").splitlines()
    registro = json.loads(linha)
    assert registro["ferramenta"] == "git"
    assert registro["situacao"] == "ok"
    assert registro["risco"] == "seguro"


async def test_publica_pensando_e_executando(novo_agente, eventos):
    fila = eventos.assinar()
    modelo = ModeloFalso(chamada("git", projeto="omni-api", operacao="status"), texto("ok"))

    await novo_agente(modelo).responder("git status")

    publicados = []
    while not fila.empty():
        publicados.append(fila.get_nowait())
    estados = [e["estado"] for e in publicados if e["tipo"] == "estado"]
    ferramentas = [(e["ferramenta"], e["situacao"]) for e in publicados if e["tipo"] == "ferramenta"]
    assert estados == ["thinking", "executing", "thinking"]
    assert ferramentas == [("git", "iniciada"), ("git", "concluida")]


async def test_lembra_da_conversa_anterior(novo_agente):
    modelo = ModeloFalso(texto("Oi!"), texto("Você disse oi."))
    agente = novo_agente(modelo)

    await agente.responder("oi")
    await agente.responder("o que eu disse?")

    conversa = [(m["role"], m["content"]) for m in modelo.recebidas[1][1:]]
    assert conversa == [("user", "oi"), ("assistant", "Oi!"), ("user", "o que eu disse?")]


async def test_historico_guarda_as_chamadas_de_ferramenta_para_o_modelo_nao_desaprender(novo_agente):
    modelo = ModeloFalso(chamada("git", projeto="omni-api", operacao="status"), texto("Está limpo."), texto("ok"))
    agente = novo_agente(modelo)

    await agente.responder("git status no omni")
    await agente.responder("e agora?")

    papeis = [m["role"] for m in modelo.recebidas[2][1:]]
    assert papeis == ["user", "assistant", "tool", "assistant", "user"]
    assert modelo.recebidas[2][2]["tool_calls"][0]["function"]["name"] == "git"


async def test_historico_guarda_so_as_ultimas_quatro_conversas(novo_agente):
    modelo = ModeloFalso(*[texto(f"resposta {i}") for i in range(6)])
    agente = novo_agente(modelo)

    for i in range(6):
        await agente.responder(f"fala {i}")

    falas = [m["content"] for m in modelo.recebidas[5] if m["role"] == "user"]
    assert falas == ["fala 1", "fala 2", "fala 3", "fala 4", "fala 5"]


async def test_resultado_longo_de_ferramenta_e_encurtado_no_historico(novo_agente, registro):
    async def longo(args):
        return "x" * 5000

    registro.registrar(Ferramenta("longo", "longo", Argumentos, longo))
    modelo = ModeloFalso(chamada("longo"), texto("ok"), texto("ok"))
    agente = novo_agente(modelo)

    await agente.responder("longo")
    await agente.responder("de novo")

    [resultado] = [m["content"] for m in modelo.recebidas[2] if m["role"] == "tool"]
    assert len(resultado) <= 400


async def test_pergunta_de_confirmacao_fica_no_historico_depois_da_chamada(novo_agente):
    modelo = ModeloFalso(chamada("git", projeto="omni-api", operacao="pull"), texto("ok"))
    agente = novo_agente(modelo)

    await agente.responder("atualiza o omni")
    await agente.responder("não")
    await agente.responder("e agora?")

    papeis = [m["role"] for m in modelo.recebidas[1][1:]]
    assert papeis == ["user", "assistant", "tool", "assistant", "user", "assistant", "user"]
    assert modelo.recebidas[1][2]["tool_calls"][0]["function"]["name"] == "git"
    assert modelo.recebidas[1][4]["content"] == "Vou dar pull no omni-api. Confirma?"


class ArgsPedido(Argumentos):
    pedido: str


@pytest.fixture
def pedidos_ao_claude(registro):
    recebidos = []

    async def pedir(args):
        recebidos.append(args.pedido)
        return "Pedi ao Claude. Aviso quando ele terminar."

    registro.registrar(Ferramenta("pedir_ao_claude", "Claude", ArgsPedido, pedir))
    return recebidos


async def test_anunciar_sem_chamar_ganha_segunda_chance(novo_agente, executadas):
    modelo = ModeloFalso(
        texto("Vou rodar o git status no omni-api."),
        chamada("git", projeto="omni-api", operacao="status"),
        texto("Está limpo."),
    )

    resposta = await novo_agente(modelo).responder("git status no omni")

    assert executadas == [("git", "status")]
    assert resposta.texto == "Está limpo."
    cutucada = modelo.recebidas[1][-1]
    assert cutucada["role"] == "user" and "não chamou" in cutucada["content"]


async def test_a_cutucada_nao_fica_no_historico(novo_agente):
    modelo = ModeloFalso(
        texto("Vou rodar o git status."),
        chamada("git", projeto="omni-api", operacao="status"),
        texto("Está limpo."),
        texto("ok"),
    )
    agente = novo_agente(modelo)

    await agente.responder("git status no omni")
    await agente.responder("e agora?")

    conteudos = [m.get("content") or "" for m in modelo.recebidas[3]]
    assert not any("não chamou" in c for c in conteudos)
    assert not any(c.startswith("Vou rodar") for c in conteudos)


async def test_segunda_chance_so_uma_vez(novo_agente):
    modelo = ModeloFalso(texto("Vou fazer."), texto("Vou fazer mesmo."))

    resposta = await novo_agente(modelo).responder("faz aquilo")

    assert len(modelo.recebidas) == 2
    assert resposta.texto == "Vou fazer mesmo."


async def test_resposta_sem_anuncio_nao_e_cutucada(novo_agente):
    modelo = ModeloFalso(texto("De nada!"))

    await novo_agente(modelo).responder("obrigado")

    assert len(modelo.recebidas) == 1


async def test_pedido_que_cita_o_claude_chega_ao_claude_mesmo_se_o_modelo_nao_chamar(novo_agente, pedidos_ao_claude):
    modelo = ModeloFalso(texto("Vou pedir ao Claude."), texto("Vou pedir ao Claude, pode deixar."))

    resposta = await novo_agente(modelo).responder("manda o Claude explicar REST e GraphQL")

    assert pedidos_ao_claude == ["manda o Claude explicar REST e GraphQL"]
    assert resposta.texto == "Pedi ao Claude. Aviso quando ele terminar."


async def test_pedido_sem_claude_nao_e_desviado_para_o_claude(novo_agente, pedidos_ao_claude):
    modelo = ModeloFalso(texto("Vou ver."), texto("Vou ver mesmo."))

    await novo_agente(modelo).responder("explica REST e GraphQL")

    assert pedidos_ao_claude == []



@pytest.mark.parametrize("dito", [
    "Para te dar informações sobre a Smart Compass, eu preciso pesquisar na internet. Qual é o seu interesse?",
    "Vou chamar a ferramenta `pedir_ao_claude` agora para descobrir quem fundou a Anthropic.",
    "Isso o Claude responde melhor.",
])
async def test_modelo_que_so_fala_em_pesquisar_ou_no_claude_tem_a_pergunta_levada_ao_claude(novo_agente, pedidos_ao_claude, dito):
    modelo = ModeloFalso(texto(dito), texto(dito))

    resposta = await novo_agente(modelo).responder("o que é a Smart Compass?")

    assert pedidos_ao_claude == ["o que é a Smart Compass?"]
    assert resposta.texto == "Pedi ao Claude. Aviso quando ele terminar."


async def test_resposta_direta_nao_vai_ao_claude(novo_agente, pedidos_ao_claude):
    modelo = ModeloFalso(texto("Uma API é um conjunto de regras para programas conversarem."))

    await novo_agente(modelo).responder("o que é uma API?")

    assert pedidos_ao_claude == []

async def test_garantia_do_claude_nao_duplica_quando_o_modelo_ja_chamou(novo_agente, pedidos_ao_claude):
    modelo = ModeloFalso(
        RespostaDoModelo("", [ChamadaDeFerramenta("pedir_ao_claude", {"pedido": "explicar REST"})],
                         {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "pedir_ao_claude", "arguments": {"pedido": "explicar REST"}}}]}),
        texto("Pronto, pedi ao Claude."),
    )

    await novo_agente(modelo).responder("pede pro Claude explicar REST")

    assert pedidos_ao_claude == ["explicar REST"]


async def test_resposta_vazia_depois_da_ferramenta_fala_o_resultado_dela(novo_agente):
    modelo = ModeloFalso(chamada("git", projeto="omni-api", operacao="status"), texto(""))

    resposta = await novo_agente(modelo).responder("git status no omni")

    assert resposta.texto == "git status: limpo"


async def test_sim_depois_de_outro_pedido_nao_executa_a_acao_antiga(novo_agente, executadas):
    modelo = ModeloFalso(chamada("git", projeto="omni-api", operacao="pull"), texto("São 14h05."), texto("Sim o quê?"))
    agente = novo_agente(modelo)
    await agente.responder("atualiza o omni")
    await agente.responder("que horas são?")

    await agente.responder("sim")

    assert executadas == []


async def test_ferramenta_travada_estoura_o_tempo_e_o_agente_segue(registro, eventos, auditoria):
    async def travada(args):
        await asyncio.sleep(30)

    registro.registrar(Ferramenta("travada", "trava", Argumentos, travada))
    modelo = ModeloFalso(chamada("travada"), texto("Demorou demais."))
    agente = Agente(modelo, registro, eventos, auditoria, projetos=[], timeout_da_ferramenta=0.1)

    resposta = await agente.responder("trava")

    assert resposta.texto == "Demorou demais."
    assert _mensagens_de_ferramenta(modelo.recebidas[1])[0].startswith("Erro ao executar travada")


async def test_cidade_do_usuario_entra_no_prompt_quando_configurada(registro, eventos, auditoria):
    modelo = ModeloFalso(texto("ok"), texto("ok"))

    await Agente(modelo, registro, eventos, auditoria, projetos=[], cidade="Curitiba").responder("oi")
    await Agente(modelo, registro, eventos, auditoria, projetos=[]).responder("oi")

    assert "Curitiba" in modelo.recebidas[0][0]["content"]
    assert "mora em" not in modelo.recebidas[1][0]["content"]


async def test_garantia_do_claude_nao_dispara_depois_de_uma_acao_confirmada(novo_agente, pedidos_ao_claude, executadas):
    modelo = ModeloFalso(chamada("git", projeto="omni-api", operacao="pull"), texto(""))
    agente = novo_agente(modelo)
    await agente.responder("manda o Claude ver isso e dá um pull no omni")

    await agente.responder("sim")

    assert executadas == [("git", "pull")]
    assert pedidos_ao_claude == []


async def _hora(args):
    return "São 14h05."


async def test_evento_da_ferramenta_diz_o_grupo_que_acende_na_tela(novo_agente, registro, eventos):
    registro.registrar(Ferramenta("hora", "hora", Argumentos, _hora, grupo="sistema"))
    fila = eventos.assinar()

    await novo_agente(ModeloFalso(chamada("hora"), texto("São 14h05."))).responder("que horas são?")

    publicados = [fila.get_nowait() for _ in range(fila.qsize())]
    assert [(e["grupo"], e["situacao"]) for e in publicados if e["tipo"] == "ferramenta"] == [
        ("sistema", "iniciada"), ("sistema", "concluida"),
    ]


async def test_cartao_da_ferramenta_vai_na_resposta_e_so_o_texto_vai_ao_modelo(novo_agente, registro):
    from clarisse.cartoes import Retorno

    async def tempo(args):
        return Retorno("Chuva forte amanhã.", cartao={"tipo": "clima", "titulo": "Clima"})

    registro.registrar(Ferramenta("tempo", "tempo", Argumentos, tempo, grupo="clima"))
    modelo = ModeloFalso(chamada("tempo"), texto("Vai chover."))

    resposta = await novo_agente(modelo).responder("vai chover?")

    assert resposta.cartao == {"tipo": "clima", "titulo": "Clima"}
    assert _mensagens_de_ferramenta(modelo.recebidas[1]) == ["Chuva forte amanhã."]


async def test_ferramenta_sem_cartao_ganha_cartao_de_texto_com_a_resposta_falada(novo_agente, registro):
    registro.registrar(Ferramenta("hora", "hora", Argumentos, _hora, grupo="sistema"))
    modelo = ModeloFalso(chamada("hora"), texto("São duas e cinco da tarde."))

    resposta = await novo_agente(modelo).responder("que horas são?")

    assert resposta.cartao == {"tipo": "texto", "titulo": "Sistema", "texto": "São duas e cinco da tarde."}


async def test_conversa_sem_ferramenta_nao_tem_cartao(novo_agente):
    resposta = await novo_agente(ModeloFalso(texto("Oi!"))).responder("oi")

    assert resposta.cartao is None


async def test_chamada_escrita_como_texto_ganha_segunda_chance(novo_agente, executadas):
    modelo = ModeloFalso(
        texto('git(projeto="omni-api", operacao="status")'),
        chamada("git", projeto="omni-api", operacao="status"),
        texto("Está limpo."),
    )

    resposta = await novo_agente(modelo).responder("git status no omni")

    assert executadas == [("git", "status")]
    assert resposta.texto == "Está limpo."


async def test_prompt_lista_os_sistemas_da_empresa_lidos_a_cada_conversa(registro, eventos, auditoria):
    sistemas = [["omni", "kanban"]]
    modelo = ModeloFalso(texto("Oi!"), texto("Oi de novo!"))
    agente = Agente(
        modelo, registro, eventos, auditoria, projetos=["omni-api"],
        agora=lambda: datetime(2026, 9, 28, 14, 5), sistemas=lambda: sistemas[0],
    )

    await agente.responder("oi")
    sistemas[0] = ["omni", "kanban", "favo"]
    await agente.responder("oi de novo")

    primeiro, segundo = (r[0]["content"] for r in modelo.recebidas)
    assert "Sistemas da empresa na internet: omni, kanban." in primeiro
    assert "favo" in segundo


async def test_sem_sistemas_o_prompt_nao_fala_deles(novo_agente):
    modelo = ModeloFalso(texto("Oi!"))

    await novo_agente(modelo).responder("oi")

    assert "Sistemas da empresa" not in modelo.recebidas[0][0]["content"]


@pytest.fixture
def pedidos_em_etapas(registro):
    recebidos = []

    async def etapas(args):
        recebidos.append(args.pedido)
        return "Pedi ao Claude para fazer isso em etapas. Aviso quando terminar."

    registro.registrar(Ferramenta("fazer_em_etapas", "etapas", ArgsPedido, etapas))
    return recebidos


@pytest.mark.parametrize("fala", [
    "abre o kanban e depois me diz a previsão do tempo",
    "vê que horas são e em seguida abre o chrome",
    "roda o smart anchor e quando subir abre o readme dele",
    "abre o omni, depois disso confere o login",
])
async def test_pedido_encadeado_vai_inteiro_para_as_etapas_sem_passar_pelo_modelo(novo_agente, pedidos_em_etapas, fala):
    modelo = ModeloFalso()

    resposta = await novo_agente(modelo).responder(fala)

    assert pedidos_em_etapas == [fala]
    assert modelo.recebidas == []
    assert "etapas" in resposta.texto


@pytest.mark.parametrize("fala", ["me lembra de ligar pro João depois", "abre o kanban", "o que acontece depois do deploy?"])
async def test_pedido_sem_encadeamento_segue_pelo_modelo(novo_agente, pedidos_em_etapas, fala):
    modelo = ModeloFalso(texto("Certo."))

    await novo_agente(modelo).responder(fala)

    assert pedidos_em_etapas == []
    assert len(modelo.recebidas) == 1


async def test_sem_a_ferramenta_de_etapas_o_encadeado_vai_ao_modelo(novo_agente):
    modelo = ModeloFalso(texto("Certo."))

    await novo_agente(modelo).responder("abre o kanban e depois o chrome")

    assert len(modelo.recebidas) == 1


async def test_resultado_na_integra_vai_direto_para_a_voz_sem_o_modelo_resumir(registro, eventos, auditoria):
    from clarisse.cartoes import Retorno

    longo = "Primeiro parágrafo da resposta do Claude.\n\nSegundo parágrafo, com mais detalhes."

    async def ler(args):
        return Retorno(longo, na_integra=True)

    registro.registrar(Ferramenta("ler", "lê", Argumentos, ler))
    modelo = ModeloFalso(chamada("ler"), texto("Resumo curto que não pode aparecer."))
    agente = Agente(modelo, registro, eventos, auditoria, projetos=[], agora=lambda: datetime(2026, 9, 30, 10, 0))

    resposta = await agente.responder("lê a última resposta do Claude")

    assert resposta.texto == longo
    assert len(modelo.recebidas) == 1


@pytest.fixture
def leituras(registro):
    from clarisse.cartoes import Retorno

    class ArgsLeitura(Argumentos):
        conversa: str | None = None

    feitas = []

    async def ler(args):
        feitas.append(args.conversa)
        return Retorno("Texto da resposta do Claude.", na_integra=True)

    registro.registrar(Ferramenta("ler_resposta_do_claude", "lê", ArgsLeitura, ler))
    return feitas


@pytest.mark.parametrize("fala", ["Clarisse, lê pra mim a resposta do Claude", "leia o que o Claude respondeu"])
async def test_pedido_de_leitura_sem_ferramenta_chamada_le_em_vez_de_mandar_ao_claude(novo_agente, pedidos_ao_claude, leituras, fala):
    modelo = ModeloFalso(texto("Qual resposta do Claude você gostaria que eu lesse?"), texto("Qual resposta?"))

    resposta = await novo_agente(modelo).responder(fala)

    assert leituras == [None]
    assert pedidos_ao_claude == []
    assert resposta.texto == "Texto da resposta do Claude."


async def test_pergunta_ao_claude_continua_indo_ao_claude(novo_agente, pedidos_ao_claude, leituras):
    modelo = ModeloFalso(texto("Vou pedir ao Claude."), texto("Vou pedir ao Claude, pode deixar."))

    await novo_agente(modelo).responder("pergunta pro Claude o que é REST")

    assert leituras == []
    assert pedidos_ao_claude == ["pergunta pro Claude o que é REST"]


def test_prompt_sem_o_claude_manda_dizer_que_nao_sabe_em_vez_de_pesquisar():
    from clarisse.agente import prompt_do_sistema

    texto = prompt_do_sistema(
        [], datetime(2026, 10, 1, 9, 0), ferramentas={"hora_e_data", "abrir_claude_na_tela", "ler_resposta_do_claude"},
    )

    assert "pedir_ao_claude" not in texto
    assert "consultar_agenda" not in texto
    assert "Você não tem acesso à internet para pesquisar" in texto
    assert "ler_resposta_do_claude" in texto and "abrir_claude_na_tela" in texto


def test_prompt_com_o_claude_manda_pesquisar_com_ele():
    from clarisse.agente import prompt_do_sistema

    texto = prompt_do_sistema(
        [], datetime(2026, 10, 1, 9, 0), ferramentas={"pedir_ao_claude", "consultar_agenda", "abrir_claude_na_tela"},
    )

    assert "vão para pedir_ao_claude" in texto
    assert "chama consultar_agenda" in texto
    assert "não tem acesso à internet" not in texto


async def test_agente_monta_o_prompt_com_as_ferramentas_que_existem(novo_agente):
    modelo = ModeloFalso(texto("Não sei a cotação de hoje."))

    await novo_agente(modelo).responder("quanto está o dólar?")

    prompt = modelo.recebidas[0][0]["content"]
    assert "Você não tem acesso à internet para pesquisar" in prompt
