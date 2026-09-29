import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from clarisse.agente import Resposta
from clarisse.eventos import Eventos
from clarisse.web import criar_app, criar_avisador

CHAVE = "chave-de-teste-" + "x" * 30
ORIGEM = "http://127.0.0.1:8765"


class AgenteFalso:
    def __init__(self):
        self.falas = []
        self.proxima = Resposta("Abri o projeto.")

    async def responder(self, fala):
        self.falas.append(fala)
        return self.proxima


class TranscritorFalso:
    def __init__(self):
        self.audios = []

    async def transcrever(self, audio):
        self.audios.append(audio)
        return "abre o omni api"


class LocutorFalso:
    def __init__(self, pasta, falhar=False):
        self.pasta = pasta
        self.falhar = falhar
        self.textos = []

    async def sintetizar(self, texto):
        if self.falhar:
            raise OSError("sem internet")
        self.textos.append(texto)
        self.pasta.mkdir(parents=True, exist_ok=True)
        destino = self.pasta / ("a" * 32 + ".mp3")
        destino.write_bytes(b"ID3")
        return destino


@pytest.fixture
def pasta_web(tmp_path):
    pasta = tmp_path / "web"
    pasta.mkdir()
    (pasta / "index.html").write_text("<!doctype html><title>Clarisse</title>", encoding="utf-8")
    (pasta / "app.js").write_text("console.log(1)", encoding="utf-8")
    return pasta


@pytest.fixture
def partes(tmp_path, pasta_web):
    agente, transcritor, locutor, eventos = AgenteFalso(), TranscritorFalso(), LocutorFalso(tmp_path / "audio"), Eventos()
    app = criar_app(
        agente=agente, eventos=eventos, transcritor=transcritor, locutor=locutor,
        chave=CHAVE, porta=8765, pasta_web=pasta_web, pasta_audio=tmp_path / "audio",
    )
    return app, agente, transcritor, locutor, eventos


@pytest.fixture
def cliente(partes):
    with TestClient(partes[0], base_url=ORIGEM) as c:
        yield c


@pytest.fixture
def logado(cliente):
    cliente.get("/")
    return cliente


def test_pagina_inicial_entrega_a_chave_em_cookie_protegido(cliente):
    resposta = cliente.get("/")

    assert resposta.status_code == 200
    cookie = resposta.headers["set-cookie"]
    assert f"clarisse_chave={CHAVE}" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie or "SameSite=Strict" in cookie


def test_host_estranho_e_recusado(partes):
    cliente = TestClient(partes[0], base_url="http://clarisse.evil.com:8765")

    assert cliente.get("/").status_code == 400


def test_api_sem_chave_e_recusada(cliente):
    assert cliente.post("/api/mensagem", json={"texto": "oi"}).status_code == 401


def test_api_com_chave_errada_e_recusada(cliente):
    resposta = cliente.post("/api/mensagem", json={"texto": "oi"}, headers={"X-Clarisse-Chave": "errada"})

    assert resposta.status_code == 401


def test_origem_de_outro_site_e_recusada_mesmo_com_chave(logado):
    resposta = logado.post("/api/mensagem", json={"texto": "oi"}, headers={"Origin": "https://evil.com"})

    assert resposta.status_code == 403


def test_mensagem_passa_pelo_agente_e_volta_com_audio(logado, partes):
    _, agente, _, locutor, _ = partes

    resposta = logado.post("/api/mensagem", json={"texto": "abre o omni"}, headers={"Origin": ORIGEM})

    assert resposta.status_code == 200
    corpo = resposta.json()
    assert agente.falas == ["abre o omni"]
    assert corpo["texto"] == "Abri o projeto."
    assert corpo["audio"] == "/audio/" + "a" * 32 + ".mp3"
    assert locutor.textos == ["Abri o projeto."]


def test_chave_pelo_cabecalho_serve_para_o_atalho(cliente, partes):
    resposta = cliente.post("/api/escutar", headers={"X-Clarisse-Chave": CHAVE})

    assert resposta.status_code == 200


def test_mensagem_com_campo_a_mais_e_recusada(logado):
    resposta = logado.post("/api/mensagem", json={"texto": "oi", "admin": True})

    assert resposta.status_code == 422


def test_mensagem_longa_demais_e_recusada(logado):
    assert logado.post("/api/mensagem", json={"texto": "a" * 2001}).status_code == 422


def test_falha_da_voz_nao_perde_o_texto(tmp_path, pasta_web):
    app = criar_app(
        agente=AgenteFalso(), eventos=Eventos(), transcritor=TranscritorFalso(),
        locutor=LocutorFalso(tmp_path / "audio", falhar=True),
        chave=CHAVE, porta=8765, pasta_web=pasta_web, pasta_audio=tmp_path / "audio",
    )
    cliente = TestClient(app, base_url=ORIGEM)
    cliente.get("/")

    corpo = cliente.post("/api/mensagem", json={"texto": "oi"}).json()

    assert corpo["texto"] == "Abri o projeto."
    assert corpo["audio"] is None


def test_voz_transcreve_e_responde(logado, partes):
    _, agente, transcritor, _, _ = partes

    corpo = logado.post("/api/voz", content=b"webm", headers={"Content-Type": "audio/webm"}).json()

    assert transcritor.audios == [b"webm"]
    assert agente.falas == ["abre o omni api"]
    assert corpo["transcricao"] == "abre o omni api"


def test_audio_grande_demais_e_recusado(logado, partes):
    _, _, transcritor, _, _ = partes

    resposta = logado.post("/api/voz", content=b"0" * (10 * 1024 * 1024 + 1), headers={"Content-Type": "audio/webm"})

    assert resposta.status_code == 413
    assert transcritor.audios == []


def test_audio_que_nao_e_audio_e_recusado(logado):
    resposta = logado.post("/api/voz", content=b"x", headers={"Content-Type": "application/json"})

    assert resposta.status_code == 415


def test_fala_vazia_nao_chama_o_agente(logado, partes):
    _, agente, transcritor, _, _ = partes
    transcritor.transcrever = _devolve_vazio

    corpo = logado.post("/api/voz", content=b"x", headers={"Content-Type": "audio/webm"}).json()

    assert agente.falas == []
    assert corpo["transcricao"] == ""


async def _devolve_vazio(audio):
    return ""


def test_audio_so_serve_nome_gerado_pelo_sistema(logado, tmp_path, partes):
    logado.post("/api/mensagem", json={"texto": "oi"})

    assert logado.get("/audio/" + "a" * 32 + ".mp3").status_code == 200
    assert logado.get("/audio/..%2F..%2Fetc%2Fpasswd").status_code == 404
    assert logado.get("/audio/nao-existe.mp3").status_code == 404


def test_parar_publica_evento_de_parar(logado, partes):
    _, agente, _, locutor, eventos = partes
    agente.proxima = Resposta("Parei.", parar=True)
    fila = eventos.assinar()

    corpo = logado.post("/api/mensagem", json={"texto": "para"}).json()

    tipos = []
    while not fila.empty():
        tipos.append(fila.get_nowait()["tipo"])
    assert "parar" in tipos
    assert corpo["audio"] is None
    assert locutor.textos == []


def test_documentacao_automatica_desligada(logado):
    assert logado.get("/docs").status_code == 404
    assert logado.get("/openapi.json").status_code == 404


def test_cabecalhos_de_seguranca(cliente):
    cabecalhos = cliente.get("/").headers

    assert "default-src 'self'" in cabecalhos["content-security-policy"]
    assert "unsafe-inline" not in cabecalhos["content-security-policy"]
    assert "frame-ancestors 'none'" in cabecalhos["content-security-policy"]
    assert cabecalhos["x-content-type-options"] == "nosniff"
    assert cabecalhos["x-frame-options"] == "DENY"
    assert cabecalhos["referrer-policy"] == "no-referrer"
    assert "microphone=(self)" in cabecalhos["permissions-policy"]


def _cabecalhos_ws(origem=ORIGEM, chave=CHAVE):
    """O cliente de teste manda Host "testserver" e nenhum cookie no WebSocket; o navegador manda os dois."""
    cabecalhos = {"Host": "127.0.0.1:8765", "Origin": origem}
    if chave:
        cabecalhos["Cookie"] = f"clarisse_chave={chave}"
    return cabecalhos


def _recusa_do_websocket(cliente, cabecalhos) -> int:
    with pytest.raises(WebSocketDisconnect) as recusa:
        with cliente.websocket_connect("/ws", headers=cabecalhos) as ws:
            ws.receive_json()
    return recusa.value.code


def test_websocket_sem_chave_e_recusado(cliente):
    assert _recusa_do_websocket(cliente, _cabecalhos_ws(chave=None)) == 1008


def test_websocket_com_chave_errada_e_recusado(cliente):
    assert _recusa_do_websocket(cliente, _cabecalhos_ws(chave="errada")) == 1008


def test_websocket_de_outra_origem_e_recusado(cliente):
    assert _recusa_do_websocket(cliente, _cabecalhos_ws(origem="https://evil.com")) == 1008


def test_websocket_de_host_estranho_e_recusado(cliente):
    assert _recusa_do_websocket(cliente, {**_cabecalhos_ws(), "Host": "evil.com:8765"}) == 1008


def test_websocket_recebe_o_estado_atual_e_os_eventos(logado):
    with logado.websocket_connect("/ws", headers=_cabecalhos_ws()) as ws:
        primeiro = ws.receive_json()
        logado.post("/api/escutar")
        evento = ws.receive_json()

    assert primeiro == {"tipo": "estado", "estado": "idle"}
    assert evento["tipo"] == "escutar"


def test_fim_da_fala_volta_ao_estado_parado(logado, partes):
    _, _, _, _, eventos = partes
    logado.post("/api/mensagem", json={"texto": "oi"})
    assert eventos.estado_atual.value == "speaking"

    logado.post("/api/fim-da-fala")

    assert eventos.estado_atual.value == "idle"


async def test_avisador_publica_o_aviso_e_fala_com_o_titulo(tmp_path):
    eventos, locutor = Eventos(), LocutorFalso(tmp_path / "audio")
    fila = eventos.assinar()

    await criar_avisador(eventos, locutor)("omni-api", "O build passou.")

    publicados = []
    while not fila.empty():
        publicados.append(fila.get_nowait())
    assert {"tipo": "aviso", "titulo": "omni-api", "texto": "O build passou."}.items() <= publicados[0].items()
    assert locutor.textos == ["Do omni-api: O build passou."]
    assert any(e["tipo"] == "falar" for e in publicados)
