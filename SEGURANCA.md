# Segurança — Clarisse

Metodologia: requisitos AppSec da Smart Compass (skill auditoria-seguranca), 23 itens.
Atualizado em: 29/09/2026

A Clarisse é uma aplicação local de um usuário só. Ela não tem banco, cadastro nem
login de pessoas, mas abre uma porta em `127.0.0.1` que **executa ações na
máquina**, e um modelo de linguagem decide quais. Os dois riscos centrais são:

1. outro programa — em especial uma página aberta no navegador — mandar pedidos
   para essa porta;
2. o modelo pedir uma ação errada, por erro de transcrição, de entendimento ou por
   texto malicioso vindo de fora (uma manchete, a saída de um comando).

| # | Requisito | Situação | Onde / motivo |
|---|-----------|----------|---------------|
| 1 | Esconder API Keys | feito | A aplicação não usa chave de API: o Ollama é local e o Claude usa o login do próprio CLI. `.gitignore` cobre `.env*` (exceto `.env.example`, que só tem nomes e padrões não sensíveis) e `config/*.json` pessoais |
| 2 | Limpar secrets do Git | feito | gitleaks no CI (`.github/workflows/ci.yml`). Varredura de 29/09/2026 em todo o histórico: 2 achados, ambos o mesmo token falso usado como exemplo nos testes do filtro de segredos antigo, registrados em `.gitleaksignore` (junto com a primeira versão deste arquivo, que citava o exemplo) |
| 3 | Public Key DB (chaves públicas vs. privadas de banco) | não se aplica | Sem banco de dados |
| 4 | Ativar RLS (Row Level Security) | não se aplica | Sem banco e sem múltiplos usuários |
| 5 | Criptografia de dados | feito | A chave de sessão vem de `secrets.token_urlsafe(32)` (`clarisse/montagem.py`) e é comparada em tempo constante (`secrets.compare_digest`, `clarisse/web.py`). Chamadas externas (g1, Microsoft Graph, Anthropic, Hugging Face para baixar o modelo de voz uma vez) em HTTPS com verificação de certificado padrão. Nada sensível guardado em repouso além da auditoria local |
| 6 | Auth server-side | feito | `Portaria` em `clarisse/web.py`: toda rota `/api/*`, `/audio/*` e o WebSocket exigem a chave da sessão (cookie ou cabeçalho `X-Clarisse-Chave`). A chave nasce a cada início e é gravada em `%APPDATA%\Clarisse\chave`, dentro do perfil do usuário, que o Windows já restringe a ele, para o servidor MCP da Clarisse |
| 7 | Restringir acessos (authorization / IDOR) | feito | Um usuário só. Documentação automática do FastAPI desligada (`docs_url=None`, `openapi_url=None`). Áudio servido só com nome gerado pelo sistema (32 hexadecimais + `.mp3`) |
| 8 | Bloquear Mass Assignment | feito | Entrada da API e argumentos de ferramenta em modelos Pydantic com `extra="forbid"` (`clarisse/web.py`, `clarisse/ferramentas/registro.py`) |
| 9 | Proteger Cookies | parcial | Cookie `HttpOnly; SameSite=Strict; Path=/`, sem `Domain`. **Sem `Secure`**: a página é servida em `http://127.0.0.1`, que nunca sai da máquina. CSRF barrado por `SameSite=Strict` mais a conferência do `Origin` |
| 10 | Hash nas Senhas | não se aplica | A aplicação não guarda senha |
| 11 | Rate Limit | feito | Um pedido por vez (trava no agente, `clarisse/agente.py`); áudio limitado a 10 MB (`clarisse/web.py`); resposta do modelo local limitada a 400 tokens (`clarisse/llm.py`); cada tarefa do Claude com teto de US$ 1,00 (`--max-budget-usd`) e 10 minutos |
| 12 | Bot protection | não se aplica | Nada exposto à internet; a porta só aceita Host `127.0.0.1`/`localhost` |
| 13 | Queries parametrizadas | feito | Sem SQL. Toda execução de programa passa por `clarisse/ferramentas/processos.py`: lista de argumentos, nunca shell, com teste de injeção. Pasta aberta só dentro da home (caminho resolvido e conferido); site só `http`/`https`; notícias só de feeds fixos e previsão só nos dois endereços fixos do Open-Meteo, com a cidade como parâmetro (sem SSRF) |
| 14 | Validação de inputs | feito | Pydantic com tamanho máximo em todo texto; enum/faixa em operação git e volume; tipo de conteúdo `audio/*` exigido; tela usa `textContent`, nunca `innerHTML` (`web/app.js`) |
| 15 | Vazar conteúdo (data leakage) | feito | Erros viram mensagem curta ao usuário; o detalhe vai para o log do terminal. Ambiente mínimo nos programas executados: variáveis com `KEY`, `TOKEN`, `SECRET`, `PASSWORD` não são repassadas. Logs, áudio, auditoria e o registro da conversa (`dados/conversa.jsonl`, o que foi dito e respondido) em `dados/`, fora do git |
| 16 | Restringir uploads | feito | O único envio é o áudio do microfone: `audio/*`, até 10 MB, lido em memória e nunca gravado com nome do cliente |
| 17 | Trim respostas de API (over-fetching) | feito | Respostas montadas campo a campo em `clarisse/web.py` |
| 18 | Add security headers | feito | CSP sem `unsafe-inline`/`unsafe-eval` com `frame-ancestors 'none'`, `X-Content-Type-Options`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Permissions-Policy` (só microfone), `Cache-Control: no-store` — `Portaria` em `clarisse/web.py`. Sem CORS: só a própria origem |
| 19 | Forçar HTTPS | não se aplica | Servidor só em `127.0.0.1`; o tráfego não sai da máquina. Chamadas externas já são HTTPS |
| 20 | Scan de dependências | feito | `uv.lock` versionado; `pip-audit` no CI (sem vulnerabilidade conhecida em 29/09/2026); `.github/dependabot.yml` |
| 21 | Código de origem open source (procedência e risco de supply chain) | feito | Nenhum código copiado. Fonte Atkinson Hyperlegible Next embutida (tabela abaixo). Licenças das dependências diretas: MIT/BSD/Apache (Kokoro e o modelo de voz são Apache-2.0). O pronunciador que o Kokoro usa é **GPL-3.0**: `phonemizer-fork` (biblioteca Python, sem modificação) e o `espeak-ng` que vem no pacote `espeakng-loader`, carregado como biblioteca compartilhada — leitura técnica; a decisão final é do jurídico |
| 22 | Log de auditoria, monitoramento e backup | parcial | Toda ferramenta executada vira uma linha em `dados/auditoria.jsonl` (quando, qual, argumentos, risco, resultado, duração), e cada troca da conversa uma linha em `dados/conversa.jsonl`. Portaria e segurança negam quando algo falha. **Sem monitoramento externo** (é local) e **sem backup** (não há dado a preservar além da auditoria) |
| 23 | IA, LLM e MCP na aplicação | feito | Fala do usuário e resultados externos entram como mensagens `user` e `tool`, nunca como instrução de sistema; o prompt de sistema não tem segredo nem regra de autorização (a autorização está em `clarisse/seguranca.py`). Ações que alteram algo — fechar aplicativo, `git pull`, criar compromisso — pedem confirmação decidida por palavra, não pelo modelo. O modelo só escolhe entre ferramentas cadastradas, com argumentos validados. Tetos de tokens e de gasto no item 11. Dois servidores MCP, cada um só para o seu Claude, com `--strict-mcp-config` e `--tools` restrito: o Playwright (`@playwright/mcp`, versão fixa 0.0.83, Apache-2.0) nas tarefas no navegador, que pedem confirmação e proíbem enviar, comprar, apagar ou alterar; e o da própria Clarisse (`clarisse/mcp_servidor.py`, SDK `mcp` 2.2.0, MIT) nas tarefas em etapas, que só repassa chamadas para a avaliação e a confirmação da Clarisse |

## O que o risco central exigiu

- **Host** tem que ser `127.0.0.1:8765` ou `localhost:8765`: bloqueia DNS rebinding.
- **Origin**, quando vem, tem que ser a própria página: bloqueia site de terceiro.
- **Chave de sessão** em cookie `SameSite=Strict`: um site de terceiro não consegue
  enviá-la.
- **Parar e confirmar** são decididos por palavra, antes do modelo.
- **O Claude em segundo plano** roda só com ferramentas de leitura
  (`Read`, `Grep`, `Glob`, `WebSearch`, `WebFetch`) e numa pasta fora de qualquer
  repositório; o Claude aberto na tela pede as próprias permissões.
- **Cada chamada ao Claude recebe `--tools` com exatamente as ferramentas
  embutidas de que precisa.** `--allowedTools` só pré-aprova: em 29/09/2026 um
  Claude "de leitura" mandou mensagem para outra sessão pelo `SendMessage`, que não
  pede permissão. Com `--tools` ele nem enxerga a ferramenta (testado).
- **Mensagem para uma conversa aberta** pede confirmação, e quem recebe a trata
  como vinda de outra sessão, não como aprovação do usuário.
- **Teclado e janelas** pelo próprio Windows (`clarisse/area_de_trabalho.py`, com
  `pywinauto` e `pyperclip`), sem instalar serviço nem dar permissão extra. As teclas só
  saem depois que o Windows confirma que a janela pedida está na frente, para não cair
  noutra janela.
- **Programa `.cmd` ou `.bat` não recebe argumento com `& | < > ^ % " !`**
  (`clarisse/ferramentas/processos.py`): o `cmd.exe` interpretaria esses caracteres
  mesmo vindo como argumento separado. O executor continua sem shell e com lista de
  argumentos.
- **Rodar aplicação** só roda o script de desenvolvimento do `package.json`
  (`dev` ou `start:dev`), em terminal visível, depois de confirmação. Lê do `.env`
  só endereço e porta das variáveis de banco que o servidor de desenvolvimento usa
  (`DATABASE_URL`, `DB_HOST`/`DB_PORT`…), nunca a senha, e recusa banco marcado como
  produção em `config/bancos.json`. Sem `node_modules`, instala antes (`npm ci`,
  que respeita o `package-lock.json` e não altera o repositório), no mesmo terminal
  visível, e a confirmação avisa.
- **Abrir arquivo** só dentro da pasta pessoal, sem pastas ocultas, e recusa o que
  executa programa ao abrir (`.exe`, `.bat`, `.cmd`, `.ps1`, `.vbs`, `.js`, `.msi`, `.lnk`, `.scr`,
  `.reg`, `.hta` e outros da lista em `clarisse/ferramentas/sistema.py`), e não procura em `AppData`.
- **Claude das tarefas em etapas** (`fazer_em_etapas`): roda com `--strict-mcp-config`
  e só enxerga o servidor MCP da Clarisse (`clarisse/mcp_servidor.py`) mais busca na
  web. O servidor **não executa nada**: repassa cada chamada às rotas
  `/api/ferramentas` e `/api/ferramenta`, protegidas pela chave da sessão, onde valem a
  mesma avaliação (`clarisse/seguranca.py`), a auditoria e a confirmação. O que pede
  confirmação é perguntado pela voz ("O Claude quer: …"); só "sim" libera, qualquer
  outra resposta, "para" ou 60 s de silêncio cancelam. O Claude não pode pedir
  `pedir_ao_claude` nem `fazer_em_etapas` (sem Claude chamando Claude), e
  `apertar_atalho`, seguro para o modelo local, pede confirmação quando vem do Claude.
- **Não existe ferramenta de tecla livre.** Colar texto pede confirmação mostrando o
  texto e a janela, e não aperta Enter; os atalhos são uma lista fechada
  (`clarisse/ferramentas/janelas.py`), e fechar aba ou janela pede confirmação.
- **Claude desligado por padrão** (`CLARISSE_USAR_CLAUDE=false`, desde 01/10/2026): as
  ferramentas que mandam pedido ao Claude nem são registradas; ficam abrir o Claude na
  tela e ler a resposta dele, que não mandam nada.
- **Conectores só leem, menos o e-mail que o usuário pede.** Escrever e-mail cria um
  rascunho (`POST /me/messages`) e o envio (`/send`) é uma ferramenta de risco "confirmar":
  só vai depois do "sim" falado, decidido por palavra e não pelo modelo (prova por mutação em
  01/10/2026). Destinatário por nome: se casar com mais de uma pessoa nos contatos, não escreve
  e pergunta. O texto é escrito pelo modelo local numa chamada sem ferramentas.
- **Leitura:** agenda e e-mail: `GET` no Microsoft Graph com o token do login MSAL
  (`clarisse/microsoft.py`), renovado em silêncio a partir do cache criptografado pelo
  Windows (DPAPI) em `%LOCALAPPDATA%\Clarisse\conta-microsoft.bin` e usado só no
  cabeçalho, nunca em log nem no modelo. O navegador do login só abre pelo
  `scripts\entrar-microsoft.ps1`, nunca no meio de uma pergunta. GitHub: `gh search prs` e
  `gh pr checks`. Dokploy: `project.all` (só nome, identificador e situação de cada
  aplicação) e `deployment.all`, com a chave de leitura que o Claude Code já usa; nada
  lê variável de ambiente. Notas: arquivos `.md` do cofre, fora da pasta `.obsidian`.
- **Texto escrito por terceiros não passa pelo modelo.** Lista de e-mails, corpo do
  e-mail, matéria, nota, título de PR e de deploy são falados direto pelo sistema
  (`Retorno(na_integra=True)`), para um e-mail não virar instrução. O que fica no
  histórico da conversa é encurtado a 300 letras.
- **Imagens de fora só do servidor de fotos da Globo** (`img-src https://*.glbimg.com`
  na política de segurança da página), para a foto das matérias do g1.

## Riscos aceitos

- **A voz é 100% local desde 02/10/2026** (Kokoro, no processador): o que a Clarisse fala,
  inclusive e-mail, matéria e resposta do Claude lida, não sai mais da máquina. Com o Claude
  ligado, o pedido delegado vai para a Anthropic; o nome da cidade vai para o Open-Meteo.
- **O login Microsoft usa o aplicativo público do Microsoft Graph PowerShell**
  (`14d82eec-204b-4c2f-b7e8-296a70dab67e`), escolha do usuário em 05/10/2026: nada é
  registrado no Entra da empresa, mas a identidade é de outro aplicativo, e o
  administrador do Microsoft 365 pode bloqueá-lo a qualquer momento.
- **Qualquer programa rodando como o seu usuário consegue abrir o cache do login
  Microsoft**: a criptografia do Windows protege contra outros usuários e contra o
  arquivo copiado para outra máquina, não contra programas da sua própria sessão.
- **Lembretes ficam em texto aberto** em `dados/lembretes.json`, fora do git.
- **Qualquer programa rodando como o seu usuário** consegue ler a chave em
  `%APPDATA%\Clarisse\chave` — o mesmo programa já poderia executar comandos
  sozinho, então a chave não protege contra ele.
- **A tecla Insert fica com a Clarisse enquanto ela está ligada**: nos outros
  programas ela deixa de alternar entre inserir e sobrescrever.
- **Texto colado fica na área de transferência** e substitui o que estava lá.
- **Banco não reconhecido é só avisado.** Um `.env` que aponte para produção por
  uma variável fora da convenção, ou um banco de produção que não está em
  `config/bancos.json`, passa com "um banco que eu não conheço" na confirmação.
- **Injeção pela web no Claude das etapas:** uma página lida pelo Claude pode tentar
  induzi-lo a agir. Ele só alcança as ferramentas da Clarisse, e as que alteram algo
  (e os atalhos) dependem do "sim" falado; as de leitura e abrir site/programa rodam
  sem pergunta.
- **Ler a resposta do Claude** abre, só para leitura, as conversas que o Claude Code
  grava em `~/.claude/projects/` e fala a última resposta, com a voz local.
- **Perguntas sobre o mundo vão para a Anthropic** e o Claude pesquisa na web.
- **Instalar dependências executa código de terceiros** (scripts de instalação dos
  pacotes npm), como quando o usuário roda `npm ci` à mão. Autorizado pelo usuário em
  29/09/2026.
- **Atalho sem programa vai para a janela da frente.** O modelo às vezes não
  repassa o programa citado ("salva o arquivo no vs code"). A resposta falada diz
  onde apertou, e fechar aba ou janela pede confirmação mostrando o destino.
- **Janela errada:** se outra janela tomar a frente nos 0,3 s entre trazer e
  colar, o texto vai para ela. Sem Enter, ele fica escrito e não é enviado.
- **Injeção por texto externo** (manchete, saída de git) pode tentar induzir o
  modelo; o dano possível fica limitado às ferramentas seguras, e as que alteram
  algo pedem confirmação.

## Código de terceiros copiado

| Componente | Origem | Versão | Licença | Modificado? |
|---|---|---|---|---|
| Fonte Atkinson Hyperlegible Next (subconjunto latin, `web/fontes/`) | Google Fonts (Braille Institute) | v7, baixada em 29/09/2026 | SIL Open Font License 1.1 | Não |
| Modelo canônico de rosto (`web/malha-rosto.js`, 468 pontos e 898 triângulos) | Google MediaPipe, `mediapipe/modules/face_geometry/data/canonical_face_model.obj` | branch master, baixado em 30/09/2026 | Apache 2.0 (texto em `web/licencas/mediapipe-LICENSE.txt`) | Sim: convertido para JSON com 2 casas; `web/rosto.js` afina queixo e mandíbula, enche os lábios e aumenta os olhos em tempo de execução |
