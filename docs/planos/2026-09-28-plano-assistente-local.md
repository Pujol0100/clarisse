# Plano — Clarisse assistente local (MVP)

Desenho: `docs/planos/2026-09-28-clarisse-assistente-local-design.md`.

**Objetivo:** aplicação local com bola neural no navegador que ouve, entende com o
Gemma 4 e4b, executa ferramentas com segurança e responde falando.

**Pilha:** Python 3.12 (uv), FastAPI, uvicorn, httpx, pydantic-settings,
faster-whisper, edge-tts, psutil; HTML/CSS/JS sem framework no navegador.

Toda tarefa segue o ciclo: teste que falha → rodar e ver falhar → código mínimo →
rodar e ver passar → commit. Comando de teste: `uv run pytest -q`.

## Tarefa 0 — Casa arrumada

- Mover o código do Windows para `legado-windows/` (`clarisse/`, `comandos/`,
  `instalar.ps1`, `tests/`, `pytest.ini`, README antigo). Ele não roda no Linux; o
  histórico continua no git.
- `pyproject.toml` com uv e Python 3.12; `uv.lock` versionado.
- `.gitignore`: `.env*` (exceto `.env.example`), `dados/`, `config/*.json` (exceto
  `*.exemplo.json`), `*.pem`, `*.key`, `credentials.json`, caches.
- `.env.example` só com nomes e valores padrão não sensíveis.
- `SEGURANCA.md` com os 21 itens.
- Medição do roteador em `docs/medicoes/2026-09-28-roteador/` (script + README),
  com nomes de pessoas trocados por fictícios.

## Tarefa 1 — Configuração (`clarisse/config.py`)

Testes: lê valores padrão sem `.env`; lê `config/projetos.json`,
`config/aplicativos.json` e `config/pastas.json`; arquivo ausente vira dicionário
vazio; caminho de projeto com `~` é expandido.

## Tarefa 2 — Registro de ferramentas (`clarisse/ferramentas/registro.py`)

Testes: registra ferramenta e gera o esquema no formato do Ollama a partir do
modelo Pydantic; argumentos extras são recusados; nome desconhecido é recusado;
cada ferramenta declara risco (`seguro`, `confirmar`, `bloqueado`).

## Tarefa 3 — Porta única de processos (`clarisse/ferramentas/processos.py`)

Testes: executa lista de argumentos e devolve saída e código; nunca aceita string
(recusa); respeita timeout e mata o processo; `iniciar` solta programa gráfico sem
esperar; ambiente mínimo (sem variáveis com `KEY`, `TOKEN`, `SECRET`, `PASSWORD`).

## Tarefa 4 — Ferramentas do sistema (`clarisse/ferramentas/sistema.py`)

Testes (com executor falso): hora e data em português; abrir aplicativo cadastrado
chama o comando certo e recusa não cadastrado; fechar aplicativo é "confirmar";
abrir pasta aceita apelido ou pasta dentro da home e recusa fora dela; abrir site
aceita só http/https; volume limita 0–100 e chama `wpctl`.

## Tarefa 5 — Ferramentas de projeto (`clarisse/ferramentas/projetos.py`)

Testes: abrir projeto cadastrado chama `code <pasta>`; projeto desconhecido é
recusado; git status/log seguros e pull "confirmar"; git usa `-C <pasta>`.

## Tarefa 6 — Ferramentas do Claude (`clarisse/ferramentas/claude.py`)

Testes: abrir na tela chama o VS Code e um terminal na pasta com `claude <pedido>`;
pedir ao Claude chama `claude -p` com `--setting-sources project`,
`--no-session-persistence`, `--output-format json`, ferramentas somente leitura e
timeout, e devolve o campo `result`; agenda usa só a ferramenta de leitura do
calendário; criar compromisso é "confirmar".

## Tarefa 7 — Notícias (`clarisse/ferramentas/noticias.py`)

Testes (transporte HTTP falso): lê RSS e devolve as 5 primeiras manchetes; tema
escolhe o feed; tema desconhecido cai no geral; falha de rede vira erro legível.

## Tarefa 8 — Cliente do Ollama (`clarisse/llm.py`)

Testes (transporte HTTP falso): envia `think: false`, ferramentas e mensagens;
devolve texto e chamadas de ferramenta; erro HTTP levanta exceção com a mensagem.

## Tarefa 9 — Segurança e agente (`clarisse/seguranca.py`, `clarisse/agente.py`)

Testes (modelo falso roteirizado): resposta sem ferramenta; ferramenta segura
executa e o resultado volta ao modelo; "confirmar" pergunta e só executa com "sim";
outra fala cancela; ferramenta inexistente ou argumento inválido volta como erro
ao modelo; exceção da ferramenta não derruba o agente; limite de rodadas; "parar"
não chama o modelo; a data de hoje entra no prompt; cada execução gera auditoria.

## Tarefa 10 — Eventos (`clarisse/eventos.py`)

Testes: publicar estado chega a todos os assinantes; assinante que caiu é removido.

## Tarefa 11 — Voz (`clarisse/voz.py`)

Testes: interfaces trocáveis; TTS grava mp3 com nome aleatório em `dados/audio` e
apaga os antigos; STT passa os nomes dos projetos como dica. A verificação real
com microfone é manual.

## Tarefa 12 — Web (`clarisse/web.py`)

Testes: Host estranho → 400; sem chave → 401; Origin de outro site → 403; página
inicial entrega o cookie; `/api/mensagem` responde; `/api/voz` recusa áudio acima
de 10 MB; `/api/escutar` publica evento; cabeçalhos de segurança presentes;
`/docs` não existe.

## Tarefa 13 — Interface (`web/`)

`index.html`, `estilo.css`, `app.js`: bola neural em canvas reagindo ao estado e ao
nível do áudio; painel de conversa; campo de texto; botão e barra de espaço para
falar; botões de confirmação. Verificação no navegador com Playwright.

## Tarefa 14 — Execução (`run.py`, `scripts/`)

`run.py` confere Ollama, modelo e placa, liga o Ollama se não estiver de pé e sobe
o servidor. `scripts/alternar-escuta.sh` chama `/api/escutar` com a chave;
`scripts/instalar-atalho.sh` cadastra o atalho no GNOME.

## Tarefa 15 — Fechamento

README novo, `SEGURANCA.md` atualizado, CI (pytest, pip-audit, gitleaks),
Dependabot, verificação de ponta a ponta, nota no vault.
