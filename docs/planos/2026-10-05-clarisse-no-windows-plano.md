# Clarisse no Windows — plano

> Para quem executa: siga as fases na ordem. Cada tarefa é TDD: escreva o teste, veja falhar,
> implemente o mínimo, veja passar, faça commit. Durante o trabalho rode só o arquivo de teste que
> mudou (`uv run pytest tests/test_x.py`); a suíte inteira roda no fim de cada fase. Nada em modo
> watch. Desenho: `2026-10-05-clarisse-no-windows-design.md`.

**Objetivo:** a Clarisse roda inteira no Windows 11, sem nenhum comando ou caminho de Linux.

**Arquitetura:** o `Executor` continua a única porta para programas e ganha `abrir` (programa padrão)
e `encerrar` (fechar pelo nome). Janelas, teclas e volume passam por um objeto novo,
`AreaDeTrabalho`, injetado como o executor. Terminal visível vira Windows Terminal + PowerShell.
Outlook troca o token do GNOME por login MSAL.

**Stack nova:** `tzdata`, `pywinauto`, `pyperclip`, `pycaw`, `msal`, `msal-extensions`.

---

## Fase 1 — Base

### Tarefa 1: fusos no Windows
- Rodar `uv add tzdata`.
- Verificar: `uv run pytest tests/test_outlook.py tests/test_dokploy.py tests/test_montagem.py tests/test_cartoes.py`
  carrega os 30 testes (antes: `ZoneInfoNotFoundError` na coleta).
- Commit: "Fusos no Windows: tzdata, que o sistema não traz".

### Tarefa 2: executor no Windows
**Arquivos:** `clarisse/ferramentas/processos.py`, `tests/test_processos.py`, `tests/conftest.py`.

Testes (vermelhos primeiro):
- `test_ambiente_minimo_tira_segredos`: além dos segredos, `env["USERPROFILE"] == os.environ["USERPROFILE"]`,
  `"SYSTEMROOT" in env`, nenhuma variável `XDG_*`/`WAYLAND_*`/`DBUS_*`.
- `test_programa_executado_nao_recebe_segredos_do_ambiente`: `"USERPROFILE"` na saída do filho.
- `test_executa_lista_de_argumentos_e_devolve_saida`: o "olá" chega certo (precisa de `PYTHONUTF8=1`).
- `test_estoura_o_tempo_e_mata_o_processo`: continua; passa sem `os.killpg`.
- novo `test_estourar_o_tempo_encerra_tambem_os_filhos`: filho Python que abre um neto com `time.sleep(30)`
  e grava o PID do neto num arquivo; depois do estouro, `psutil.pid_exists(neto)` é falso.
- novo `test_acha_programa_cmd_pelo_nome`: cria `tmp/eco.cmd` (`@echo %1`), põe `tmp` no `PATH`
  (monkeypatch), `executar(["eco", "oi"])` devolve "oi".
- novo `test_recusa_caractere_do_cmd_em_programa_cmd`: `executar(["eco", "a&calc"])` levanta `ValueError`.
- novo `test_encerrar_fecha_o_programa_pelo_nome`: copia `C:\Windows\System32\PING.EXE` para
  `tmp/clarisse-ping.exe`, inicia com `-n 30 127.0.0.1`, `encerrar("clarisse-ping.exe") == 1`, processo some.
- novo `test_encerrar_programa_que_nao_esta_aberto_devolve_zero`.
- novo `test_abrir_entrega_ao_programa_padrao`: monkeypatch de `os.startfile` registra o alvo.

Implementação:
```python
_VARIAVEIS_DA_SESSAO = (
    "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "SYSTEMDRIVE", "TEMP", "TMP",
    "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "USERNAME", "USERDOMAIN", "COMPUTERNAME",
    "APPDATA", "LOCALAPPDATA", "PROGRAMDATA", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432",
    "COMMONPROGRAMFILES", "COMMONPROGRAMFILES(X86)", "OS", "PROCESSOR_ARCHITECTURE",
    "NUMBER_OF_PROCESSORS", "LANG",
)
_CARACTERES_DO_CMD = set('&|<>^%"!')

def _resolver(argumentos, ambiente) -> list[str]:
    programa = shutil.which(argumentos[0], path=ambiente.get("PATH")) or argumentos[0]
    if programa.lower().endswith((".cmd", ".bat")) and any(_CARACTERES_DO_CMD & set(a) for a in argumentos[1:]):
        raise ValueError("argumento com caractere que o cmd.exe interpretaria")
    return [programa, *argumentos[1:]]

def _encerrar_arvore(pid: int) -> None:
    try:
        processo = psutil.Process(pid)
        for filho in processo.children(recursive=True):
            filho.kill()
        processo.kill()
    except psutil.NoSuchProcess:
        pass
```
- `executar`/`iniciar`: `env = {**ambiente_minimo(), "PYTHONUTF8": "1", **(ambiente or {})}`,
  `creationflags=subprocess.CREATE_NEW_PROCESS_GROUP`, sem `start_new_session`.
- `abrir(alvo: str) -> None`: `os.startfile(alvo)`.
- `encerrar(processo: str) -> int`: encerra todo processo cujo `name()` casa sem diferenciar
  maiúsculas; devolve quantos.
- `ExecutorFalso` ganha `abertos: list[str]`, `encerrados: list[str]` e `quantos_encerrar: int = 1`.
- Commit: "Executor no Windows: ambiente, árvore de processos, .cmd, abrir e encerrar".

### Tarefa 3: pastas da Clarisse e chave
**Arquivos:** `clarisse/config.py`, `clarisse/montagem.py`, `clarisse/mcp_servidor.py`, `tests/test_montagem.py`, `tests/test_config.py`.
- `config.py`: `PASTA_DO_USUARIO = Path(os.environ["APPDATA"]) / "Clarisse"`,
  `PASTA_LOCAL = Path(os.environ["LOCALAPPDATA"]) / "Clarisse"`, `CAMINHO_DA_CHAVE = PASTA_DO_USUARIO / "chave"`.
- `montagem.py` e `mcp_servidor.py` importam `CAMINHO_DA_CHAVE`; `PASTA_NEUTRA_DO_CLAUDE = PASTA_LOCAL / "claude"`.
- `gravar_chave`: `mkdir(parents=True, exist_ok=True)` e `write_text(chave, encoding="utf-8")`.
- Teste `test_chave_gravada_so_para_o_dono` sai; entram `test_chave_nova_substitui_a_antiga` e
  `test_chave_fica_na_pasta_do_usuario_no_appdata` (`CAMINHO_DA_CHAVE.is_relative_to(os.environ["APPDATA"])`).
- Commit: "Pastas da Clarisse no AppData".

### Tarefa 4: texto em UTF-8
**Arquivos:** `clarisse/sites.py`, `clarisse/ferramentas/aplicacoes.py`, `clarisse/mcp_servidor.py`,
`clarisse/montagem.py` e os testes que gravam texto (`test_leitura`, `test_sites`, `test_aplicacoes`,
`test_lembretes`, `test_montagem`, `test_sistema`).
- Teste vermelho: `test_sites` grava `sites.json` com "Gestão" em UTF-8 e espera ler "Gestão".
- Todo `read_text()`/`write_text()` ganha `encoding="utf-8"`; nos testes também.
- Commit: "Texto em UTF-8: o padrão do Windows é cp1252".

Fim da fase: suíte inteira; os 4 de `test_leitura` podem continuar vermelhos (Tarefa 13).

---

## Fase 2 — Abrir, fechar e volume

### Tarefa 5: abrir pelo programa padrão
**Arquivos:** `clarisse/ferramentas/sistema.py` (5 lugares), `clarisse/ferramentas/aplicacoes.py` (2),
`clarisse/montagem.py` (`abrir_no_navegador`), testes de `test_sistema` e `test_aplicacoes`.
- Asserções `(["xdg-open", x], None) in executor.iniciados` viram `x in executor.abertos`.
- `executor.iniciar(["xdg-open", x])` vira `executor.abrir(x)`.
- Commit: "Abre pasta, arquivo e site pelo programa padrão do Windows".

### Tarefa 6: fechar e listar programas
- Testes: `test_fechar_aplicativo_pede_confirmacao_e_fecha_pelo_processo` espera
  `executor.encerrados == ["chrome.exe"]`; `test_fechar...15_caracteres` sai; novo
  `test_fechar_aplicativo_que_nao_estava_aberto` (`quantos_encerrar = 0`);
  `test_lista_programas_cadastrados_que_estao_abertos` recebe `["Code.exe", "chrome.exe"]`.
- `conftest.cadastros`: `processo="Code.exe"` e `processo="chrome.exe"`, `abrir=["chrome"]`.
- `fechar_aplicativo`: `if await executor.encerrar(app.processo) == 0: "não estava aberto"`.
- `listar_programas_abertos`: compara em minúsculas.
- Commit: "Fecha e lista programas pelo nome do Windows".

### Tarefa 7: arquivo que executa e pasta pessoal
- Testes trocam `monkeypatch.setenv("HOME", ...)` por `monkeypatch.setenv("USERPROFILE", ...)`.
- `test_nao_abre_arquivo_que_executa_programa` com `.bat`, `.ps1`, `.lnk`, `.exe`;
  `test_nao_abre_arquivo_marcado_como_executavel` sai; novo `test_nao_procura_em_appdata`;
  `test_recusa_pasta_fora_da_home` com `C:\Windows` e `~\..\..`.
- `_EXTENSOES_QUE_EXECUTAM` = lista do desenho; `_executa_programa` só pela extensão;
  `_PASTAS_PULADAS` ganha `"AppData"`.
- Commit: "Arquivo que executa programa reconhecido pela extensão do Windows".

### Tarefa 8: volume
- `ferramentas_do_sistema(..., definir_volume=area_de_trabalho.definir_volume)`.
- Testes: `test_ajusta_volume` com função falsa que registra 30; `test_falha_do_programa_vira_mensagem`
  passa a usar outra ferramenta que falha (abrir site com executor que levanta) ou sai se só cobria o wpctl.
- `clarisse/area_de_trabalho.py`: `definir_volume(nivel)` com `pycaw`
  (`AudioUtilities.GetSpeakers().EndpointVolume.SetMasterVolumeLevelScalar(nivel / 100, None)`).
- Verificação manual: "volume em trinta" muda o volume do Windows.
- Commit: "Volume pelo Windows".

---

## Fase 3 — Janelas e teclado

### Tarefa 9: janelas pela área de trabalho
**Arquivos:** `clarisse/ferramentas/janelas.py`, `clarisse/area_de_trabalho.py`, `tests/test_janelas.py`, `tests/conftest.py`.
- Contrato do objeto `area`: `listar() -> list[dict]` com `id`, `titulo`, `processo`;
  `ativar(id)`; `colar(texto)`; `apertar(teclas: str)` no formato do `pywinauto` (`"^s"`, `"%{F4}"`).
- `AreaFalsa` no conftest registra `ativadas`, `coladas`, `apertadas`, devolve `janelas`.
- `_ATALHOS`: salvar `^s`, desfazer `^z`, copiar `^c`, colar `^v`, enter `{ENTER}`, esc `{ESC}`,
  trocar_janela `%{TAB}`, nova_aba `^t`, fechar_aba `^w`, fechar_janela `%{F4}`.
- Saem `_JANELAS`, `ler_janelas`, `_combinacao`, `_SEM_EXTENSAO`, `_SEM_TECLADO`, `_TERMINAIS`.
  `digitar_texto` cola com `^v` em qualquer janela.
- Os 19 testes passam a falar de `titulo`/`processo` (ex.: `Code.exe`, `WindowsTerminal.exe`);
  saem `test_le_a_lista_de_janelas_como_o_gdbus_devolve`, `test_sem_a_extensao_explica_o_que_falta`,
  `test_teclado_virtual_desligado_vira_mensagem`, `test_no_terminal_cola_com_ctrl_shift_v`,
  `test_app_do_chrome_nao_passa_na_frente_do_proprio_chrome`.
- Real (`AreaDeTrabalho`): `pywinauto.Desktop(backend="uia").windows(visible_only=True)`,
  título por `window_text()`, processo por `psutil.Process(w.process_id()).name()`, `set_focus()`,
  `pyperclip.copy`, `pywinauto.keyboard.send_keys`.
- Verificação manual: trazer o VS Code, colar "teste" no Bloco de Notas, apertar salvar.
- Commit: "Janelas e teclas pelo Windows".

---

## Fase 4 — Terminal, Claude e conversas

### Tarefa 10: comando do terminal
**Arquivos:** novo `clarisse/terminal.py`, novo `tests/test_terminal.py`.
```python
def em_aspas(texto: str) -> str:
    return "'" + texto.replace("'", "''") + "'"

def terminal(pasta: Path, comando: str) -> list[str]:
    codificado = base64.b64encode(comando.encode("utf-16-le")).decode()
    return ["wt.exe", "-w", "new", "-d", str(pasta), "powershell.exe", "-NoExit", "-EncodedCommand", codificado]
```
- Testes: decodifica o base64 e acha o comando; `;` não aparece solto na lista; `em_aspas("d'água")`.
- Commit: "Terminal visível: Windows Terminal com PowerShell".

### Tarefa 11: rodar projeto no terminal
- `rodar_aplicacao`: comando `npm.cmd ci; if ($LASTEXITCODE -eq 0) { npm.cmd run dev }` (ou sem a
  instalação). Sai `_SEGURAR_A_JANELA` (o `-NoExit` segura).
- `_comando` dos testes decodifica o `-EncodedCommand`; os testes de `ptyxis`/`bash -c`/`read`
  passam a conferir `wt.exe`, `npm.cmd` e a pasta.
- Commit: "Roda projetos no Windows Terminal".

### Tarefa 12: Claude na tela
- `abrir_claude_na_tela`: `iniciar(["code", pasta])` e `iniciar(terminal(Path(pasta), f"claude {em_aspas(pedido)}"))`.
- `test_abrir_na_tela_abre_vscode_e_terminal_com_o_pedido` decodifica e acha `claude '...'`.
- Commit: "Abre o Claude no Windows Terminal".

### Tarefa 13: conversas do Claude com caminho do Windows
**Arquivos:** `clarisse/ferramentas/leitura.py`, `tests/test_leitura.py`.
- `_mexeu_no_projeto` compara caminhos, não texto cru: `cwd` conta quando `Path(cwd) == caminho` ou
  `caminho in Path(cwd).parents`; entrada de ferramenta conta quando algum texto dela, com `/` trocado
  por `\` e em minúsculas, contém `str(caminho).lower() + "\\"` ou `\worktrees\<nome>\`.
  Filtro rápido da linha crua: o nome da pasta do projeto.
- Os 4 testes vermelhos ficam verdes; caminhos dos testes vêm de `tmp_path`.
- Commit: "Acha a conversa do projeto com caminho do Windows".

### Tarefa 14: MCP do Playwright e fim da agenda do Linux
- `_config_do_navegador`: `{"command": "cmd", "args": ["/c", "npx", "-y", PLAYWRIGHT_MCP]}`; teste
  `test_playwright_do_navegador_tem_versao_fixa` ajustado.
- Apaga `clarisse/agenda_linux.py`, `tests/test_agenda_linux.py`, `apos_mudar_agenda` (montagem e
  claude.py) e `test_criar_compromisso_manda_o_linux_atualizar_a_agenda`; sai
  `agenda_intervalo_minutos` do config e do `.env.example`.
- Commit: "Tira a agenda do Linux".

Fim da fase: suíte inteira verde.

---

## Fase 5 — Tecla, voz, Ollama e scripts

### Tarefa 15: tecla Insert
**Arquivos:** novo `clarisse/tecla.py`, novo `tests/test_tecla.py`, `clarisse/montagem.py`.
```python
async def escutar_pela_tecla(publicar, apertos=tecla_insert):
    async for _ in apertos():
        await publicar({"tipo": "escutar"})
```
- Teste: `apertos` falso que rende 2 vezes → 2 eventos publicados.
- `tecla_insert()`: thread com `RegisterHotKey(None, 1, MOD_NOREPEAT, VK_INSERT)` e `GetMessageW`;
  cada `WM_HOTKEY` entra numa `asyncio.Queue` por `loop.call_soon_threadsafe`; no cancelamento,
  `PostThreadMessageW(thread, WM_QUIT)` e `UnregisterHotKey`. Se o registro falhar (tecla em uso),
  levanta `OSError` com a mensagem.
- `montar_app` põe a tarefa em `tarefas_de_fundo`.
- Verificação manual: Insert fora da página liga e desliga o microfone.
- Commit: "Insert para falar, registrada pelo próprio servidor".

### Tarefa 16: voz com o espeak embutido
- `carregar_kokoro`: só `import misaki.espeak`; sai o `find_library` e o `set_library`.
- `run.py`: sai a checagem do espeak-ng.
- Verificação manual: `uv run python -c "from clarisse.voz import carregar_kokoro; carregar_kokoro()"`
  e a frase "Pronta." gerada em MP3 e tocada.
- Commit: "Voz com o espeak que vem no pacote".

### Tarefa 17: Ollama do Windows
- `config.py`: `ollama_bin = "~/AppData/Local/Programs/Ollama/ollama.exe"`; `.env.example` igual.
- `run.py`: `creationflags=subprocess.CREATE_NEW_PROCESS_GROUP` no lugar de `start_new_session`.
- Commit: "Ollama no caminho do instalador do Windows".

### Tarefa 18: scripts em PowerShell
- Apaga os 6 `.sh`. Cria:
  - `scripts/ligar.ps1`: vai para a raiz e roda `uv run python -u run.py`.
  - `scripts/desligar.ps1`: `Get-NetTCPConnection -LocalPort 8765 -State Listen` → `Stop-Process -Id`.
  - `scripts/instalar-no-menu.ps1`: atalho "Clarisse" no Menu Iniciar (`WScript.Shell`) que abre o Windows Terminal rodando `ligar.ps1`.
- `test_scripts.py`: `test_todo_script_e_powershell_sem_erro_de_sintaxe` (passa cada `.ps1` pelo
  `Parser::ParseFile` do PowerShell e espera zero erros) e `test_nao_sobrou_script_do_linux`.
- Commit: "Scripts de ligar, desligar e menu em PowerShell".

---

## Fase 6 — Outlook

### Tarefa 19: conta Microsoft pelo MSAL
**Arquivos:** `clarisse/microsoft.py`, `tests/test_microsoft.py`, `clarisse/montagem.py`.
- `ContaMicrosoft(pedir_token, http)`, onde `pedir_token(forcar_novo: bool) -> Awaitable[str]`.
- Testes reescritos com `pedir_token` falso: usa o token no Graph; guarda entre pedidos (1 chamada);
  401 pede `forcar_novo=True` e repete uma vez; sem conta levanta `SemContaMicrosoft`; post com corpo.
- `LoginMicrosoft(criar_app=_app_do_msal)`:
  - `async token(forcar_novo)`: `acquire_token_silent(ESCOPOS, conta, force_refresh=forcar_novo)` em
    `asyncio.to_thread`; sem conta ou sem token → `SemContaMicrosoft("Entre na conta Microsoft: rode scripts\entrar-microsoft.ps1.")`.
  - `entrar()`: `acquire_token_interactive(ESCOPOS, prompt="select_account")`; erro do MSAL vira
    `SemContaMicrosoft` com a descrição.
  - `_app_do_msal()`: `PublicClientApplication(GRAPH_POWERSHELL, authority="https://login.microsoftonline.com/organizations",
    token_cache=PersistedTokenCache(FilePersistenceWithDataProtection(PASTA_LOCAL / "conta-microsoft.bin")))`.
- Testes de `LoginMicrosoft` com app falso: token silencioso; sem conta → `SemContaMicrosoft`;
  `forcar_novo` chega como `force_refresh`.
- `python -m clarisse.microsoft entrar` chama `entrar()` e diz com qual conta entrou.
- Commit: "Outlook com login próprio no Windows".

### Tarefa 20: script de login
- `scripts/entrar-microsoft.ps1`: `uv run python -m clarisse.microsoft entrar`.
- Verificação manual com o usuário: login e "o que eu tenho na agenda hoje?".
- Commit: "Script para entrar na conta Microsoft".

---

## Fase 7 — Configuração, documentação e CI

### Tarefa 21: configurações de exemplo
- `aplicativos.exemplo.json`: vscode (`["code"]`, `Code.exe`), chrome (`["chrome"]`, `chrome.exe`),
  edge (`["msedge"]`, `msedge.exe`), terminal (`["wt.exe"]`, `WindowsTerminal.exe`),
  explorador (`["explorer.exe"]`, `explorer.exe`), calculadora (`["calc.exe"]`, `CalculatorApp.exe`).
- `pastas.exemplo.json`: `~/Downloads`, `~/Documents`, `~/Desktop`.
- `projetos.exemplo.json`: `~/Documents/meusProgramas/clarisse`, `~/Documents/projetos/meu-projeto`.
- `tests/test_config.py` sem `/tmp` e `google-chrome`.
- Commit: "Configurações de exemplo do Windows".

### Tarefa 22: documentação
- `README.md`, `SEGURANCA.md` e `.env.example` reescritos para Windows (requisitos, instalação,
  scripts, login Microsoft, risco do app público).
- Commit: "Documentação do Windows".

### Tarefa 23: CI no Windows
- `.github/workflows/ci.yml`: job `testes` com `runs-on: windows-latest`.
- Commit: "CI roda os testes no Windows".

### Tarefa 24: verificação final
- Suíte inteira verde; nenhum `xdg-open`, `gdbus`, `ydotool`, `wl-copy`, `wpctl`, `pkill`, `ptyxis`,
  `notify-send`, `.local/`, `.config/` fora de `legado-windows/` e `docs/` (`git grep`).
- Roteiro do usuário: instalar o Ollama, baixar o modelo, rodar `ligar.ps1`, falar com a Clarisse.
