# Clarisse assistente local — desenho

Data: 28/09/2026. Substitui o propósito do projeto: a Clarisse deixa de ser só a
voz do Claude Code no Windows e vira uma assistente de voz que roda nesta máquina
Linux, conversa, executa ações e passa trabalho pesado para o Claude.

Ponto de partida: o documento `assistente_neural_gemma.md` (arquitetura de
assistente com Gemma via Ollama). Onde este desenho diverge dele, este ganha, e o
motivo está escrito.

## O que o usuário pediu

- Uma aplicação chamada Clarisse com quem ele conversa por voz.
- Ela executa tarefas na máquina sem ele precisar mexer: tirar dúvida, notícias do
  dia, abrir o VS Code e iniciar o Claude Code já com o pedido, agenda, ler um
  dashboard, conversar com o Claude sobre uma aplicação nova.
- Roda na máquina, para poder mexer na máquina.
- Por ora a cara dela é uma bola neural que se mexe quando ela escuta e fala.

## Restrições

- **Sem IA chinesa** (regra da empresa). Qwen está fora mesmo rodando local.
- Máquina: Predator Helios Neo 16 AI, RTX 5070 Laptop com **8 GB** de VRAM, 30 GB
  de RAM, Ubuntu 26.04 com **Wayland**.
- A máquina tem acesso a sistemas de produção da empresa. Um modelo local pequeno
  erra; o sistema tem que aguentar o erro sem estrago.
- O repositório é público no GitHub. Nada pessoal (caminhos, histórico de falas,
  áudio, logs) pode ser versionado.

## Decisões medidas

Ver `docs/medicoes/2026-09-28-roteador/`.

| Decisão | Por quê |
|---|---|
| Modelo local: `gemma4:e4b-it-qat` via Ollama | 29/32 pedidos certos, mediana 0,27 s, 3,1 GB, 100% na placa. Quando erra, pergunta em vez de agir errado |
| Sem VPS | GPU alugada custa R$ 600–1.300/mês; VPS só CPU leva dezenas de segundos por pedido |
| Sem LangChain/AutoGen | O Ollama já devolve `tool_calls`; o laço cabe num arquivo legível |
| OpenJarvis não é base | Sem allowlist de comandos, telemetria ligada por padrão; a voz é a parte mais fraca dele |
| O sistema confirma, não o modelo | Com a regra "não peça confirmação" no prompt, o Gemma subiu de 26 para 29 acertos |
| "Parar" não passa pelo modelo | Falhou em quase todos os modelos medidos |
| Conhecimento factual não vem do modelo local | Todos os modelos inventaram "curiosidades" |
| Claude sem tela com `--setting-sources project` | Leu a agenda do M365 em 6,3 s; o contexto caiu pela metade (US$ 0,40 → 0,19 equivalentes por chamada) |
| Ativação por tecla; palavra "Clarisse" fica para depois | Em 21/08/2026 nenhum motor gratuito acertou a palavra em português |

## Arquitetura

```
navegador (bola neural)                     backend (FastAPI, 127.0.0.1:8765)
┌──────────────────────┐   WebSocket    ┌──────────────────────────────────┐
│ microfone (gravação) │ ─── áudio ───► │ STT: faster-whisper              │
│ canvas da bola       │ ◄── eventos ── │ Agente ─► Ollama (Gemma 4 e4b)   │
│ reprodução da voz    │ ◄── mp3 ────── │   └─► Segurança ─► Ferramentas   │
└──────────────────────┘                │ TTS: edge-tts                    │
                                        └──────────────────────────────────┘
atalho do GNOME ─► scripts/alternar-escuta.sh ─► POST /api/escutar
```

**O áudio entra e sai pelo navegador.** A página já existe por causa da bola, e o
navegador dá de graça a captura do microfone, a reprodução e o nível do som que
anima a bola. Isso elimina PortAudio, pygame e pyautogui (que não funciona no
Wayland). O atalho global é um atalho do próprio GNOME que chama um script; o
backend avisa a página pelo WebSocket para começar ou parar de gravar.

### Peças do backend (`clarisse/`)

| Arquivo | Responsabilidade |
|---|---|
| `config.py` | Lê `.env` e `config/*.json` (projetos, aplicativos, pastas) |
| `llm.py` | Cliente do Ollama `/api/chat` (`think: false`) |
| `ferramentas/registro.py` | Registro de ferramentas: nome, descrição, modelo Pydantic dos argumentos, risco, função |
| `ferramentas/processos.py` | Única porta para executar programas: lista de argumentos, sem shell, timeout, ambiente mínimo |
| `ferramentas/sistema.py` | hora e data, abrir/fechar aplicativo, listar programas, abrir pasta, abrir site, volume |
| `ferramentas/projetos.py` | abrir projeto no VS Code, git (status, log, pull) |
| `ferramentas/claude.py` | abrir o Claude na tela com o pedido; pedir ao Claude em segundo plano; agenda |
| `ferramentas/noticias.py` | manchetes de feeds RSS de uma lista fixa |
| `seguranca.py` | Valida a chamada: ferramenta existe, argumentos válidos, risco |
| `agente.py` | O laço: pedido → modelo → ferramenta → modelo → resposta; confirmação pendente; "parar" |
| `eventos.py` | Estados e distribuição de eventos para os WebSockets |
| `voz.py` | STT (faster-whisper) e TTS (edge-tts) atrás de interfaces trocáveis |
| `auditoria.py` | Uma linha JSON por ferramenta executada |
| `web.py` | Rotas, WebSocket, proteção da porta local, cabeçalhos |
| `run.py` (raiz) | Confere o ambiente, liga o Ollama se preciso, sobe o servidor |

### Ferramentas e risco

| Ferramenta | Risco | Observação |
|---|---|---|
| `hora_e_data` | seguro | |
| `abrir_aplicativo` | seguro | Só aplicativos cadastrados em `config/aplicativos.json` |
| `fechar_aplicativo` | **confirmar** | Só cadastrados |
| `listar_programas_abertos` | seguro | |
| `abrir_pasta` | seguro | Apelido cadastrado ou pasta dentro da home |
| `abrir_site` | seguro | Só `http`/`https` |
| `ajustar_volume` | seguro | 0 a 100 |
| `abrir_projeto_vscode` | seguro | Só projetos cadastrados |
| `git` | seguro para status/log, **confirmar** para pull | Só projetos cadastrados |
| `abrir_claude_na_tela` | seguro | O próprio Claude pede permissão para o que for fazer |
| `pedir_ao_claude` | seguro | Roda com ferramentas somente leitura; resultado falado quando termina |
| `consultar_agenda` | seguro | Pelo Claude, com a ferramenta de leitura do calendário |
| `criar_compromisso` | **confirmar** | Pelo Claude, com a ferramenta de criar evento |
| `noticias_do_dia` | seguro | Feeds fixos |

Fora do MVP: WhatsApp (sem API oficial para conta pessoal; as alternativas quebram
ou arriscam banir o número), clicar em telas arbitrárias, palavra de ativação,
memória persistente, modo 100% offline para a voz.

### Confirmação

Ferramenta de risco "confirmar" não executa: a Clarisse descreve o que vai fazer
("Vou atualizar o repositório smart-cep com git pull. Confirma?") e guarda a
chamada pendente. A próxima fala decide: `sim`, `pode`, `confirmo`, `pode executar`
executam; qualquer outra coisa cancela. A decisão é por palavra, não pelo modelo.

### Parar

`para`, `parar`, `cancela`, `cancelar`, `chega`, `silêncio` (com ou sem "Clarisse")
são reconhecidos antes do modelo: cancelam a fala e qualquer confirmação pendente.

### Estados

`idle` → `listening` → `thinking` → `executing` → `thinking` → `speaking` → `idle`,
e `error`. Cada mudança vira evento no WebSocket e muda a animação da bola.

## Segurança da porta local

A Clarisse abre uma porta que executa ações. Qualquer site aberto no navegador
consegue tentar falar com `127.0.0.1`. Defesas, todas antes das funcionalidades:

1. Escuta só em `127.0.0.1`.
2. **Host** tem que ser `127.0.0.1:8765` ou `localhost:8765` (bloqueia DNS rebinding).
3. **Chave de sessão** gerada a cada início (`secrets.token_urlsafe(32)`), entregue
   à página num cookie `HttpOnly; SameSite=Strict` e gravada em
   `~/.config/clarisse/chave` (permissão 600) para o script do atalho. Toda rota
   `/api/*` e o WebSocket exigem a chave (cookie ou cabeçalho `X-Clarisse-Chave`).
4. **Origin**, quando presente, tem que ser a própria página.
5. Documentação automática do FastAPI desligada; cabeçalhos de segurança e CSP sem
   `unsafe-inline`.
6. Nenhuma ferramenta monta comando de shell: sempre lista de argumentos.
7. Um pedido de cada vez (trava no agente); áudio limitado a 10 MB.

O detalhe item a item está em `SEGURANCA.md`.

## Privacidade

- O modelo e a transcrição rodam na máquina.
- **A voz (edge-tts) envia o texto da resposta para a Microsoft**, como a Clarisse
  antiga. As notícias vêm da internet. O Claude envia o pedido para a Anthropic.
- Logs, áudio e auditoria ficam em `dados/`, fora do git.

## Testes

- Unidade e integração com pytest, sem abrir programas de verdade: a porta única
  de processos é trocada por uma falsa nos testes.
- O laço do agente é testado com um modelo falso roteirizado.
- As rotas são testadas com o cliente de teste do FastAPI, incluindo as recusas de
  Host, Origin e chave.
- A medição do roteador (`docs/medicoes/2026-09-28-roteador/`) é repetível e deve
  ser rodada de novo quando o modelo ou o prompt mudar.

## Critério de pronto do MVP

O usuário aperta a tecla, fala "abre o projeto sienge no VS Code", e:
a bola passa por ouvindo → pensando → executando → falando → parada; o VS Code
abre na pasta cadastrada; a Clarisse fala que abriu.
