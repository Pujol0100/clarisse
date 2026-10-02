from dataclasses import dataclass

import pytest

import httpx

from clarisse.voz import Locutor, Transcritor, com_reserva, enderecos_falados, gerar_azure, texto_para_fala


@dataclass
class Segmento:
    text: str


class WhisperFalso:
    def __init__(self):
        self.chamadas = []

    def transcribe(self, audio, **opcoes):
        self.chamadas.append((audio.read(), opcoes))
        return iter([Segmento(" Abre o projeto"), Segmento(" omni-api. ")]), None


async def test_transcreve_juntando_os_trechos_com_dica_e_idioma():
    whisper = WhisperFalso()
    cargas = []
    transcritor = Transcritor(carregar=lambda: cargas.append(1) or whisper, dicas=["omni-api", "smart-cep"])

    texto = await transcritor.transcrever(b"audio-webm")
    await transcritor.transcrever(b"de novo")

    assert texto == "Abre o projeto omni-api."
    audio, opcoes = whisper.chamadas[0]
    assert audio == b"audio-webm"
    assert opcoes["language"] == "pt"
    assert "omni-api" in opcoes["hotwords"] and "smart-cep" in opcoes["hotwords"]
    assert cargas == [1]


async def test_locutor_grava_mp3_com_nome_aleatorio_e_texto_limpo(tmp_path):
    recebidos = []

    async def gerar(texto, destino):
        recebidos.append(texto)
        destino.write_bytes(b"mp3")

    locutor = Locutor(tmp_path, gerar=gerar)

    primeiro = await locutor.sintetizar("**Pronto!** Veja https://github.com/x")
    segundo = await locutor.sintetizar("oi")

    assert primeiro.parent == tmp_path and primeiro.suffix == ".mp3"
    assert primeiro.name != segundo.name
    assert len(primeiro.stem) >= 32
    assert recebidos[0] == "Pronto! Veja o link"


async def test_locutor_apaga_os_audios_mais_antigos(tmp_path):
    async def gerar(texto, destino):
        destino.write_bytes(b"mp3")

    locutor = Locutor(tmp_path, gerar=gerar, guardar=3)

    for i in range(5):
        await locutor.sintetizar(f"fala {i}")

    assert len(list(tmp_path.glob("*.mp3"))) == 3


@pytest.mark.parametrize(
    "entrada,saida",
    [
        ("# Título\n- item um\n- item dois", "Título. item um. item dois"),
        ("Use `git status` agora", "Use git status agora"),
        ("Veja https://g1.globo.com/economia e http://x.io", "Veja o link e o link"),
        ("  espaços    demais  ", "espaços demais"),
    ],
)
def test_texto_para_fala(entrada, saida):
    assert texto_para_fala(entrada) == saida


def test_link_em_markdown_vira_so_o_texto_dele():
    falado = texto_para_fala("Só achei no site.\n\nFontes: [Smart Compass](https://www.smartcompass.com.br/)")

    assert falado == "Só achei no site. Fontes: Smart Compass"


def test_bloco_de_codigo_vira_aviso_em_vez_de_ser_soletrado():
    falado = texto_para_fala("Rode isto:\n\n```bash\nuv run pytest -q\nls -la\n```\n\nDepois me avise.")

    assert falado == "Rode isto: Trecho de código. Depois me avise."


def test_tabela_e_lida_sem_as_barras():
    falado = texto_para_fala("| Nome | Valor |\n|---|---|\n| Kanban | no ar |")

    assert "|" not in falado and "---" not in falado
    assert "Kanban" in falado and "no ar" in falado


def test_primeira_frase_sai_sozinha_para_a_voz_comecar_logo():
    from clarisse.voz import dividir_em_trechos

    assert dividir_em_trechos("Oi. Tudo bem com você? Hoje faz sol em Campinas.") == [
        "Oi.", "Tudo bem com você? Hoje faz sol em Campinas.",
    ]


def test_trechos_seguintes_juntam_frases_sem_cortar_nenhuma():
    from clarisse.voz import dividir_em_trechos

    frases = [f"Esta é a frase número {i}, com algumas palavras a mais." for i in range(12)]
    trechos = dividir_em_trechos(" ".join(frases))

    assert trechos[0] == frases[0]
    assert " ".join(trechos) == " ".join(frases)
    assert all(len(t) <= 230 for t in trechos[1:])
    assert len(trechos) < len(frases)


def test_frase_mais_longa_que_o_limite_fica_inteira():
    from clarisse.voz import dividir_em_trechos

    longa = "Esta frase " + "muito " * 60 + "comprida termina aqui."

    assert dividir_em_trechos(f"Primeira. {longa}") == ["Primeira.", longa]


def test_trechos_ja_saem_limpos_para_a_fala():
    from clarisse.voz import dividir_em_trechos

    assert dividir_em_trechos("Rode:\n\n```bash\nls\n```\n\nPronto.") == ["Rode: Trecho de código.", "Pronto."]
    assert dividir_em_trechos("   ") == []


@pytest.mark.parametrize("falado,escrito", [
    ("manda para fulano arroba smartcompass ponto com ponto br", "manda para fulano@smartcompass.com.br"),
    ("Escreve para Vinicius ponto Pujol arroba Smartcompass ponto com ponto br.", "Escreve para vinicius.pujol@smartcompass.com.br."),
    ("o e-mail é ana underline souza arroba gmail ponto com", "o e-mail é ana_souza@gmail.com"),
    ("suporte traço ti arroba empresa ponto com", "suporte-ti@empresa.com"),
    ("do meu ponto de vista está ok", "do meu ponto de vista está ok"),
    ("o símbolo arroba fica no meio", "o símbolo arroba fica no meio"),
    ("já veio certo: ana@x.com", "já veio certo: ana@x.com"),
])
def test_endereco_de_email_falado_vira_escrito(falado, escrito):
    assert enderecos_falados(falado) == escrito


class WhisperDoEmail(WhisperFalso):
    def transcribe(self, audio, **opcoes):
        return iter([Segmento(" Escreve para ana arroba x ponto com")]), None


async def test_transcricao_ja_sai_com_o_endereco_escrito():
    transcritor = Transcritor(carregar=WhisperDoEmail, dicas=[])

    assert await transcritor.transcrever(b"audio") == "Escreve para ana@x.com"


async def test_voz_do_azure_pede_o_audio_com_a_voz_escolhida_e_grava(tmp_path):
    pedidos = []

    def responder(pedido):
        pedidos.append(pedido)
        return httpx.Response(200, content=b"ID3-mp3")

    gerar = gerar_azure(httpx.AsyncClient(transport=httpx.MockTransport(responder)), "chave-secreta", "brazilsouth",
                        "pt-BR-BrendaNeural", "+10%")
    destino = tmp_path / "fala.mp3"

    await gerar("Preço < R$ 5 & frete", destino)

    [pedido] = pedidos
    assert str(pedido.url) == "https://brazilsouth.tts.speech.microsoft.com/cognitiveservices/v1"
    assert pedido.headers["Ocp-Apim-Subscription-Key"] == "chave-secreta"
    assert pedido.headers["X-Microsoft-OutputFormat"] == "audio-24khz-48kbitrate-mono-mp3"
    ssml = pedido.read().decode()
    assert "<voice name='pt-BR-BrendaNeural'>" in ssml and "<prosody rate='+10%'>" in ssml
    assert "Preço &lt; R$ 5 &amp; frete" in ssml
    assert destino.read_bytes() == b"ID3-mp3"


async def test_voz_do_azure_que_falha_levanta_erro(tmp_path):
    gerar = gerar_azure(httpx.AsyncClient(transport=httpx.MockTransport(lambda p: httpx.Response(429))), "k", "brazilsouth",
                        "pt-BR-BrendaNeural", "+0%")

    with pytest.raises(httpx.HTTPStatusError):
        await gerar("oi", tmp_path / "x.mp3")


async def test_se_a_voz_principal_falha_fala_com_a_reserva(tmp_path):
    usadas = []

    async def principal(texto, destino):
        usadas.append("principal")
        raise httpx.ConnectError("sem rede")

    async def reserva(texto, destino):
        usadas.append("reserva")
        destino.write_bytes(b"mp3")

    destino = tmp_path / "fala.mp3"
    await com_reserva(principal, reserva)("oi", destino)

    assert usadas == ["principal", "reserva"] and destino.read_bytes() == b"mp3"
