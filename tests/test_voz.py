import asyncio
from dataclasses import dataclass

import pytest

import numpy as np
import soundfile

from clarisse.voz import Locutor, Transcritor, enderecos_falados, gerar_local, texto_para_fala


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


class PipelineFalso:
    """Imita o KPipeline do Kokoro: vozes carregáveis e áudio em pedaços de 24 kHz."""

    def __init__(self):
        self.chamadas = []
        self.threads = []
        self.vozes = {"pf_dora": np.full(4, 1.0, dtype="float32"), "af_bella": np.full(4, 3.0, dtype="float32")}

    def load_voice(self, nome):
        return self.vozes[nome]

    def __call__(self, texto, voice, speed):
        import threading

        self.chamadas.append((texto, voice, speed))
        self.threads.append(threading.get_ident())
        for _ in range(2):
            yield None, None, np.zeros(2400, dtype="float32")


async def test_voz_local_mistura_as_vozes_da_receita_e_grava_mp3(tmp_path):
    cargas, pipeline = [], PipelineFalso()
    gerar = gerar_local("pf_dora*0.8+af_bella*0.2", 1.08, carregar=lambda: cargas.append(1) or pipeline)

    await gerar("Oi", tmp_path / "a.mp3")
    await gerar("Tchau", tmp_path / "b.mp3")

    texto, voz, velocidade = pipeline.chamadas[0]
    assert texto == "Oi" and velocidade == 1.08
    assert list(voz) == pytest.approx([1.4] * 4)
    info = soundfile.info(tmp_path / "a.mp3")
    assert info.format == "MP3" and info.samplerate == 24000 and info.duration == pytest.approx(0.2, abs=0.06)
    assert cargas == [1]


@pytest.mark.parametrize("receita", ["pf_dora", "pf_dora*abc", "pf_dora*0.8+", "Dora*1"])
def test_receita_de_voz_escrita_errado_e_recusada_ao_ligar(receita):
    with pytest.raises(ValueError):
        gerar_local(receita, 1.0, carregar=PipelineFalso)


async def test_toda_fala_e_gerada_na_mesma_thread(tmp_path):
    # O PyTorch cria um grupo de trabalhadores por thread: uma thread nova a cada frase lotava o processador.
    pipeline = PipelineFalso()
    gerar = gerar_local("pf_dora*1", 1.0, carregar=lambda: pipeline)

    await asyncio.gather(*(gerar(f"frase {i}", tmp_path / f"{i}.mp3") for i in range(6)))

    assert len(set(pipeline.threads)) == 1
