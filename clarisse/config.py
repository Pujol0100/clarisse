"""Ajustes (variáveis CLARISSE_* e .env) e cadastros pessoais (config/*.json)."""
import json
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict


class Ajustes(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CLARISSE_", env_file=".env", extra="ignore")

    porta: int = 8765
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_bin: str = "~/.local/ollama/bin/ollama"
    modelo: str = "gemma4:e4b-it-qat"
    whisper_modelo: str = "small"
    whisper_dispositivo: str = "cpu"
    voz: str = "pt-BR-ThalitaMultilingualNeural"
    voz_velocidade: str = "+10%"
    # Com a chave do serviço de voz do Azure, a Clarisse fala com voz_azure; a voz acima vira a reserva.
    azure_chave: str | None = None
    azure_regiao: str = "brazilsouth"
    voz_azure: str = "pt-BR-BrendaNeural"
    # Desligado em 01/10/2026: a Clarisse responde só com o modelo local. Abrir o Claude e ler o que ele
    # respondeu continuam (não mandam nada ao Claude).
    usar_claude: bool = False
    claude_modelo: str = "sonnet"
    claude_timeout: int = 600
    claude_teto_usd: float = 1.0
    cidade: str | None = None
    # Cofre do Obsidian para buscar e ler notas; sem ele, as ferramentas de notas não existem.
    cofre_de_notas: Path | None = None
    agenda_intervalo_minutos: float = 5
    pasta_config: Path = Path("config")
    pasta_dados: Path = Path("dados")
    abrir_navegador: bool = True


class Aplicativo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    abrir: list[str]
    processo: str
    apelidos: list[str] = []


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFD", texto.strip().lower())
    sem_acento = "".join(c for c in sem_acento if unicodedata.category(c) != "Mn")
    return "-".join(sem_acento.replace("-", " ").split())


@dataclass
class Cadastros:
    projetos: dict[str, Path] = field(default_factory=dict)
    aplicativos: dict[str, Aplicativo] = field(default_factory=dict)
    pastas: dict[str, Path] = field(default_factory=dict)

    def achar_projeto(self, nome: str) -> str | None:
        alvo = normalizar(nome)
        return next((p for p in self.projetos if normalizar(p) == alvo), None)

    def achar_aplicativo(self, nome: str) -> str | None:
        alvo = normalizar(nome)
        for chave, app in self.aplicativos.items():
            if alvo in {normalizar(chave), *(normalizar(a) for a in app.apelidos)}:
                return chave
        return None

    def achar_pasta(self, nome: str) -> str | None:
        alvo = normalizar(nome)
        return next((p for p in self.pastas if normalizar(p) == alvo), None)


def _ler_json(caminho: Path) -> dict:
    if not caminho.exists():
        return {}
    return json.loads(caminho.read_text(encoding="utf-8"))


def carregar_cadastros(pasta: Path) -> Cadastros:
    return Cadastros(
        projetos={k: Path(v).expanduser() for k, v in _ler_json(pasta / "projetos.json").items()},
        aplicativos={k: Aplicativo(**v) for k, v in _ler_json(pasta / "aplicativos.json").items()},
        pastas={k: Path(v).expanduser() for k, v in _ler_json(pasta / "pastas.json").items()},
    )
