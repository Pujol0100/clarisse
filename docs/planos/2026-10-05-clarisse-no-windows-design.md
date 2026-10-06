# Clarisse no Windows — desenho

**Decisão do usuário em 05/10/2026:** a Clarisse passa a rodar **só no Windows 11**. O que é de
Linux sai; o que não é de Windows vira Windows. Não há camada para os dois sistemas.

**Fica intocado:** `legado-windows/`. É a Clarisse antiga (resumo falado do Claude Code com
Ctrl+Alt+L), instalada em `%USERPROFILE%\.claude\clarisse` e em uso hoje. Ela é idêntica à pasta
(conferido em 05/10/2026, ignorando fim de linha).

## Ponto de partida (medido em 05/10/2026, Windows 11, Python 3.12 do uv)

- 4 arquivos de teste nem carregam: `test_outlook`, `test_dokploy`, `test_montagem`, `test_cartoes`
  (30 testes). O Windows não tem base de fusos e o `tzdata` não está nas dependências.
- Dos outros 422, 14 falham: `test_processos` (4), `test_sistema` (6), `test_leitura` (4).
- Os que passam usam o `ExecutorFalso` e fixam comandos de Linux nas asserções (`xdg-open`,
  `pkill`, `wpctl`, `gdbus`, `ydotool`, `wl-copy`, `ptyxis`, `bash -c`).

## Máquina

Intel Core Ultra 9 275HX, 31 GB, RTX 5070 Laptop. Tem: `uv`, `wt.exe` (Windows Terminal),
`claude.exe`, `code.cmd`, `gh.exe`, `git.exe`, Node (`npm.cmd`/`npx.cmd`). Não tem: Ollama,
Outlook clássico (só o novo, que não tem automação COM).

O espeak embutido no `espeakng-loader` funciona no Windows: fonetizou "Olá, a reunião começa às
três horas." em pt-br. O defeito que obrigou o espeak do sistema era só do Linux. **Não precisa
instalar espeak-ng.**

## Decisões

| Área | Linux | Windows | Por quê |
|---|---|---|---|
| Fusos | base do sistema | pacote `tzdata` | Windows não tem base IANA |
| Texto | codificação padrão | UTF-8 explícito em toda leitura e gravação | o padrão do Windows é cp1252 |
| Executor: ambiente mínimo | `HOME`, `XDG_*`, `DBUS_*`, `WAYLAND_*` | `USERPROFILE`, `APPDATA`, `LOCALAPPDATA`, `SYSTEMROOT`, `WINDIR`, `PATHEXT`, `TEMP`, `TMP`, `COMSPEC` e afins, mais `PYTHONUTF8=1` | sem `SYSTEMROOT` programas que abrem rede falham; `gh` lê `APPDATA` |
| Executor: tempo estourado | `os.killpg` | `psutil`: encerra filhos e o processo | `killpg` não existe no Windows |
| Executor: grupo de processo | `start_new_session` | `CREATE_NEW_PROCESS_GROUP` | Ctrl+C na janela da Clarisse não derruba o que ela abriu |
| Executor: achar o programa | o sistema acha | `shutil.which` com o `PATH` do ambiente mínimo | `code` é `code.cmd`; o Windows só completa `.exe` |
| Executor: programa `.cmd`/`.bat` | — | recusa argumento com `& \| < > ^ % " !` | o `cmd.exe` interpretaria esses caracteres (falha "BatBadBut") |
| Abrir pasta, arquivo, site | `xdg-open` | `Executor.abrir` → `os.startfile` | programa padrão do Windows |
| Fechar programa | `pkill -x` com 15 letras | `Executor.encerrar(nome.exe)` com `psutil` | |
| Programas abertos | nome sem extensão | nome com `.exe`, sem diferenciar maiúsculas | `psutil` no Windows devolve `chrome.exe` |
| Arquivo que executa | bit `x` + lista Linux | lista do Windows: `.exe .com .bat .cmd .ps1 .psm1 .vbs .vbe .js .jse .wsf .wsh .msi .msp .lnk .scr .pif .reg .cpl .hta .jar .appref-ms` | no Windows `os.access(X_OK)` é verdadeiro para qualquer arquivo |
| Busca de arquivo | pula pasta com ponto | também pula `AppData` | `AppData` tem dezenas de milhares de arquivos de programa |
| Volume | `wpctl` | `pycaw` | |
| Janelas | extensão Window Calls + `ydotool` + `wl-copy` | `pywinauto` (lista, ativa, aperta teclas) + `pyperclip` (área de transferência) | |
| Colar no terminal | Ctrl+Shift+V | Ctrl+V em tudo | Windows Terminal e console aceitam Ctrl+V |
| Terminal visível | Ptyxis + `bash -c` | `wt.exe -w new -d <pasta> powershell.exe -NoExit -EncodedCommand <base64>` | `-EncodedCommand` impede o `wt` de partir o comando no `;`; `-NoExit` segura a janela com o erro |
| npm no terminal | `npm` | `npm.cmd` | `npm.ps1` é bloqueado pela política de scripts padrão |
| MCP do Playwright | `npx` | `cmd /c npx` | o Claude Code no Windows não acha `npx` sem o `cmd` |
| Pastas da Clarisse | `~/.config/clarisse`, `~/.local/share/clarisse` | `%APPDATA%\Clarisse`, `%LOCALAPPDATA%\Clarisse` | |
| Chave da sessão | arquivo modo 0600 | arquivo em `%APPDATA%\Clarisse` | o perfil do usuário já é restrito por ACL; modo POSIX não vale no Windows |
| Tecla Insert | atalho do GNOME → `alternar-escuta.sh` → `curl` | tarefa de fundo do servidor registra Insert com `RegisterHotKey` e publica `{"tipo": "escutar"}` | sem script intermediário |
| Agenda do Linux | `agenda_linux.py` sincroniza o evolution | sai, com o retorno `apos_mudar_agenda` | o Outlook novo sincroniza sozinho e a Clarisse lê o Graph direto |
| Outlook | token da conta do GNOME (`gdbus`) | MSAL com o app público do Microsoft Graph PowerShell (`14d82eec-204b-4c2f-b7e8-296a70dab67e`), autoridade `organizations`, cache protegido pelo Windows (DPAPI) | escolha do usuário em 05/10/2026 |
| Ollama | `~/.local/ollama/bin/ollama` | `~/AppData/Local/Programs/Ollama/ollama.exe` | instalador do Windows |
| Voz | espeak-ng do sistema | espeak embutido (`misaki.espeak`) | funciona no Windows |
| Scripts | `ligar.sh`, `desligar.sh`, `alternar-escuta.sh`, `instalar-atalho.sh`, `instalar-no-menu.sh`, `instalar-teclado-virtual.sh` | `ligar.ps1`, `desligar.ps1`, `instalar-no-menu.ps1`, `entrar-microsoft.ps1` | |
| CI | `testes` no Ubuntu | `testes` no `windows-latest` | os jobs de dependências e segredos continuam no Ubuntu: não dependem do sistema |

### Outlook: login

- Escopos: `User.Read`, `Calendars.Read`, `Mail.ReadWrite`, `Mail.Send`, `People.Read` (as rotas que
  `ferramentas/outlook.py` usa).
- O login interativo **nunca** abre sozinho durante uma pergunta. Ele roda uma vez por
  `scripts/entrar-microsoft.ps1` (abre o navegador para escolher a conta). O servidor só pede
  token em silêncio; sem conta guardada, a ferramenta responde "Entre na conta Microsoft: rode
  scripts\entrar-microsoft.ps1".
- **Risco aceito pelo usuário:** é a identidade de outro aplicativo; o administrador do Microsoft 365
  pode bloquear o app ou exigir consentimento de administrador para algum escopo.

### Não entra (YAGNI)

- Transcrição e voz na placa de vídeo: continuam no processador, como no Linux.
- Camada que serve Linux e Windows.

## Bibliotecas novas (aprovadas em 05/10/2026)

`tzdata`, `pywinauto`, `pyperclip`, `pycaw`, `msal`. Pendente de aprovação: `msal-extensions`
(da Microsoft, guarda o cache do login criptografado pelo Windows).

## Testes

- Cada ferramenta continua testada pelos dublês (`ExecutorFalso` e o novo `AreaFalsa` em
  `tests/conftest.py`), agora com as chamadas de Windows.
- O executor real é testado com processos de verdade (Python, `ping.exe` copiado com outro nome,
  `.cmd` criado no teste).
- As fronteiras com o sistema (`pywinauto`, `pycaw`, `RegisterHotKey`, `msal`) não têm teste de
  unidade; a verificação é manual, na máquina, no fim de cada fase.

## Mudanças durante a execução (06/10/2026)

- **O Chrome continua na frente dos apps instalados por ele.** No Windows todos são
  `chrome.exe`, mas o título do Chrome tem "Google Chrome" e o do app não; entre janelas
  do mesmo programa vem primeiro a que tem o nome do aplicativo no título. O teste ficou.
- **Janelas pelo backend `win32` do pywinauto, não pelo `uia`.** Medido nesta máquina: o
  `uia` levou 3 s para listar as janelas, o `win32` menos de 0,1 s. A lista segue a regra do
  Alt+Tab: fica de fora janela de ferramenta (`WS_EX_TOOLWINDOW`) e janela escondida pelo
  Windows (`DWMWA_CLOAKED`), o que tira "Program Manager", o overlay da NVIDIA e a entrada
  de texto do Windows.
- **`ativar` espera o Windows confirmar a janela na frente** antes de voltar. Com espera fixa
  de 0,3 s a colagem falhou em 1 de 2 rodadas numa janela de teste; esperando o primeiro
  plano, 4 de 4 sem espera fixa.
- **O Explorador de Arquivos não entra nos aplicativos de exemplo**: fechar o `explorer.exe`
  derruba a barra de tarefas. Chrome e Edge vão com caminho completo, porque não estão no
  `PATH`.
- **Volume chamado direto, sem `asyncio.to_thread`**: o `pycaw` usa COM, que o `comtypes`
  inicia só na thread principal.
- **O teste de sintaxe dos `.ps1` força UTF-8 na saída do PowerShell.** Sem isso, a mensagem
  de erro em cp850 (com acento) não decodificava e o teste passava com script quebrado.
