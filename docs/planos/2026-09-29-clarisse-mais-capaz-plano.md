# Clarisse mais capaz — plano (29/09/2026)

Pedidos do usuário que ela não atendeu no uso real de 29/09/2026, e o que o
registro mostrou:

| Pedido | O que aconteceu | Causa |
|---|---|---|
| "O que você me fala sobre a Smart Compass?" | Respondeu de cabeça, confundindo com nomes de projeto | O Gemma não delegou ao Claude, que pesquisaria |
| "Abre o smart-anchor local" / "roda no Chrome" | Abriu o projeto no VS Code | Não existe ferramenta de rodar aplicação |
| "Coloca o Bruno Santos na reunião" | Disse, com razão, que não consegue | `criar_compromisso` só tem título e horário |
| "Quais são as minhas reuniões de amanhã?" | "Não tenho ferramenta de calendário" | O Claude por trás às vezes não enxerga o conector (2 de 3 na reprodução) |
| "Abre o VS Code … e faz X" | Faz a primeira etapa e para | O Gemma e4b escolhe bem uma ação, planeja mal várias |

Decisão do usuário (29/09/2026): usar **só a Clarisse** (voz, drones); sem porta
`/clarisse` no Claude Code. O Claude vira o cérebro das tarefas de várias etapas,
por trás dela.

## Decisões do usuário (29/09/2026)

1. Fase 1 inteira, depois a fase 2.
2. Rodar **qualquer projeto da máquina**, sem cadastro: ela acha o projeto e o
   comando de iniciar. A confirmação diz para qual banco o `.env` aponta, e os
   bancos de produção conhecidos ficam numa lista de bloqueio (recusa mesmo com
   "sim"). Abrir **qualquer arquivo** da pasta pessoal.
3. Autorizada a dependência `mcp` na fase 2.

## Fase 1 — consertar e completar (ferramentas; Gemma continua escolhendo)

Cada tarefa: teste primeiro, implementação, mutação, medição com o Gemma real.

### 1. Agenda que some às vezes (depuração primeiro)

**Feito em 29/09/2026.** Causa provada pelo `--debug-file`: o Claude roda os
conectores do claude.ai "fully async (nonblocking)" e, quando a lista de
conectores demora, manda a primeira pergunta ao modelo antes de o Microsoft 365
conectar ("Tool search disabled: no deferred tools available"). Correção:
`MCP_CONNECTION_NONBLOCKING=false` em toda chamada ao Claude — ele espera os
conectores (no máximo 5 s) antes de começar. Resultado: 10 de 10 consultas com a
agenda, de 12 a 24 s cada (antes 6 a 10 s, com falha em 2 de 3).

- Reproduzir com o `claude -p` da `consultar_agenda` e registrar a saída JSON
  inteira (ferramentas disponíveis, `ToolSearch`, erros de conexão do MCP).
- Hipótese a provar ou derrubar: o conector do Microsoft 365 ainda está
  conectando quando o Claude chama o `ToolSearch`.
- Só depois da causa provada, corrigir. Vale para `consultar_agenda` e
  `criar_compromisso` (que pode ter dito "criei" sem criar — evento das 15:00 de
  29/09 não existe).
- Critério: 10 consultas seguidas, 10 com a agenda.

### 2. Participantes no compromisso

**Feito em 29/09/2026** (3/3 no Gemma; pelo agente, chega à confirmação com os nomes).

- `criar_compromisso` ganha `participantes: list[str]` (nomes como o usuário
  falou, até 10).
- O Claude acha o e-mail pelo nome (`search_people`, só na empresa). Nome que
  casa com mais de uma pessoa, ou com ninguém: **não cria**, volta dizendo quem
  achou.
- A confirmação fala os nomes: "Vou criar: Reunião com Bruno Santos, hoje às 18h,
  convidando Bruno Santos. Confirma?". Convite manda e-mail, por isso confirma.

### 3. Abrir arquivo

**Feito em 29/09/2026.** Procura no caminho inteiro (pasta e nome); "planilha", "pdf", "documento" viram filtro de tipo.

- `abrir_arquivo(nome)`: procura pelo nome dentro da pasta pessoal (pula pastas
  ocultas, `node_modules`, `.git`), mostra até 3 se houver vários, abre com o
  programa padrão (`xdg-open`).
- Recusa executáveis, `.desktop`, `.sh` e parecidos: abrir pode executar.

### 4. Rodar aplicação local

**Feito em 29/09/2026, com mudança de desenho** (decisão do usuário: qualquer projeto, sem cadastro). Acha o projeto sozinho; confirmação diz o banco do `.env` pela lista `config/bancos.json`; produção recusa; sem `node_modules` diz que falta `npm install`.

- `projetos.json` passa a aceitar, por projeto, os comandos de iniciar e o
  endereço. O formato antigo (só o caminho) continua valendo.
- Exemplo do smart-anchor (conferido em 29/09/2026: backend no banco de
  **desenvolvimento**, porta 65432):

  ```json
  "smart-anchor": {
    "caminho": "~/Documentos/PROGRAMASSMART/smart-anchor",
    "iniciar": [
      {"pasta": "backend", "comando": ["npm", "run", "dev"]},
      {"pasta": "frontend", "comando": ["npm", "run", "dev"]}
    ],
    "endereco": "http://localhost:3100"
  }
  ```

- `rodar_aplicacao(projeto)`: pede confirmação, abre um terminal visível para
  cada comando (para ver os erros e parar com Ctrl+C), espera o endereço
  responder (até 2 min) e abre no navegador.
- **Só roda o que está cadastrado.** Projeto sem `iniciar` responde que não sabe
  rodar. Cada projeto novo só entra depois de conferir para qual banco o `.env`
  aponta (no smart-anchor, 45432 é produção).

### 5. Perguntas de conhecimento vão ao Claude

**Feito em 29/09/2026.** Regra no prompt, garantia quando o modelo só fala em pesquisar, e instrução ao Claude para pesquisar na web.

- Regra no prompt: pergunta sobre empresa, pessoa, notícia específica ou fato que
  o modelo não sabe com certeza → `pedir_ao_claude` (que pesquisa na web).
- Medir: "o que é a Smart Compass?", "quem fundou a Anthropic?", sem piorar as
  perguntas simples ("o que é uma API?" continua direto).

## Fase 2 — o Claude como cérebro das tarefas de várias etapas

**Feito em 30/09/2026.** Servidor MCP que repassa à Clarisse (não executa nada);
confirmação falada com botões na página; figuras dos drones por evento. O Gemma não
escolhia `fazer_em_etapas` (0/6): pedido com "e depois", "em seguida", "depois
disso" ou "e quando subir/terminar" vai direto, sem passar pelo modelo. Testes
reais: hora + tempo (13 s, figuras relógio e nuvem), calculadora com "sim" (fechou)
e com "não" (ficou aberta), e o pedido encadeado de ponta a ponta pela Clarisse.

- **Servidor MCP da Clarisse** (processo local): expõe as mesmas ferramentas,
  com os mesmos testes. Nova dependência: `mcp` (SDK oficial em Python, licença
  MIT).
- Nova ferramenta para o Gemma: `fazer_em_etapas(pedido)`. Roda um Claude com
  **só** as ferramentas da Clarisse (`--strict-mcp-config`, `--tools` restrito).
- **Confirmação continua sua:** quando o Claude chama uma ferramenta arriscada, o
  servidor MCP pede a confirmação pela Clarisse (ela fala a pergunta, você
  responde sim ou não) e espera. Sem resposta em 60 s, cancela.
- **Drones:** cada ferramenta chamada pelo Claude avisa a página, e a figura muda
  como hoje.
- Custo: cada tarefa usa o plano do Claude, teto de US$ 1,00 e 10 minutos (os
  mesmos de hoje).

## Fora deste plano

- Porta `/clarisse` no Claude Code (decisão do usuário).
- Clicar com o mouse, escolher contato no WhatsApp.
