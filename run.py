"""Liga a Clarisse: confere o ambiente, liga o Ollama se preciso, sobe o servidor e abre a página."""
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path

import httpx
import uvicorn

RAIZ = Path(__file__).resolve().parent
os.chdir(RAIZ)

from clarisse.config import Ajustes, carregar_cadastros
from clarisse.llm import CONTEXTO
from clarisse.montagem import montar_app


def ok(texto: str) -> None:
    print(f"  [✓] {texto}")


def aviso(texto: str) -> None:
    print(f"  [!] {texto}")


def ollama_responde(url: str) -> bool:
    try:
        return httpx.get(f"{url}/api/version", timeout=2).status_code == 200
    except httpx.HTTPError:
        return False


def garantir_ollama(ajustes: Ajustes) -> bool:
    if ollama_responde(ajustes.ollama_url):
        ok("Ollama já estava ligado")
        return True
    binario = Path(ajustes.ollama_bin).expanduser()
    if not binario.exists():
        aviso(f"Ollama não encontrado em {binario}. Ajuste CLARISSE_OLLAMA_BIN no arquivo .env.")
        return False
    registro = ajustes.pasta_dados / "ollama.log"
    registro.parent.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(
        [str(binario), "serve"],
        stdout=registro.open("a"), stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        env={**os.environ, "OLLAMA_HOST": ajustes.ollama_url.removeprefix("http://")},
    )
    for _ in range(40):
        if ollama_responde(ajustes.ollama_url):
            ok("Ollama ligado agora")
            return True
        time.sleep(0.5)
    aviso(f"O Ollama não respondeu em 20 segundos. Veja {registro}.")
    return False


def garantir_modelo(ajustes: Ajustes) -> None:
    modelos = [m["name"] for m in httpx.get(f"{ajustes.ollama_url}/api/tags", timeout=5).json()["models"]]
    if ajustes.modelo not in modelos:
        aviso(f"Modelo {ajustes.modelo} não está baixado. Rode: {ajustes.ollama_bin} pull {ajustes.modelo}")
        return
    httpx.post(
        f"{ajustes.ollama_url}/api/generate",
        json={"model": ajustes.modelo, "keep_alive": "30m", "options": {"num_ctx": CONTEXTO}},
        timeout=120,
    )
    ok(f"Modelo {ajustes.modelo} carregado na placa")


def main() -> None:
    ajustes = Ajustes()
    cadastros = carregar_cadastros(ajustes.pasta_config)
    endereco = f"http://127.0.0.1:{ajustes.porta}"

    print("=" * 44)
    print("  CLARISSE")
    print("=" * 44)
    if cadastros.projetos:
        ok(f"{len(cadastros.projetos)} projetos cadastrados")
    else:
        aviso("Nenhum projeto cadastrado. Copie config/projetos.exemplo.json para config/projetos.json e ajuste.")
    if not cadastros.aplicativos:
        aviso("Nenhum aplicativo cadastrado. Copie config/aplicativos.exemplo.json para config/aplicativos.json.")
    if shutil.which("claude"):
        ok("Claude Code encontrado")
    else:
        aviso("Comando claude não encontrado: as tarefas para o Claude vão falhar.")
    if garantir_ollama(ajustes):
        garantir_modelo(ajustes)

    app = montar_app(ajustes, cadastros)
    ok(f"Servidor em {endereco}")
    print("  Para desligar: Ctrl+C nesta janela.")
    print("=" * 44)
    if ajustes.abrir_navegador:
        threading.Timer(1.5, webbrowser.open, args=(endereco,)).start()
    uvicorn.run(app, host="127.0.0.1", port=ajustes.porta, log_level="warning")


if __name__ == "__main__":
    sys.exit(main())
