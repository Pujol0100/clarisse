# Clarisse

Assistente de voz que roda no seu computador Linux. Você fala, ela entende com um
modelo de linguagem **local** (Gemma), executa a ação na máquina e responde falando.
Por padrão ela não passa nada para o [Claude Code](https://claude.com/claude-code):
abre o Claude na tela quando você pede e lê o que ele respondeu, mas não manda
pedidos a ele (veja `CLARISSE_USAR_CLAUDE`).

A tela é um anel dourado, nas cores da Smart Compass (preto, branco e dourado), com
um globo de linhas girando dentro e filamentos de energia em volta, que se agitam
com a voz. Ao redor fica a constelação das ferramentas (Agenda, E-mail, Notícias,
GitHub, Notas, Servidores, Lembretes, Claude, Código…): o nó acende e pulsos de luz
correm até o anel enquanto ela usa aquela ferramenta.

A resposta aparece num **cartão** na frente do anel — o clima com a temperatura e os
três dias, a agenda com os horários, as manchetes numeradas — e, quando ela termina de
falar, o cartão desce para a fileira do rodapé, com o mais novo à esquerda. Quem monta
o cartão é a ferramenta, a partir do dado de verdade, nunca o modelo. No topo aparece
o que você disse e o estado (Ouvindo, Pensando, Consultando, Falando); embaixo do
anel, a legenda do que ela está dizendo.

A voz é o principal. O botão **Escrever**, no canto, abre o chat à direita (a Clarisse
desliza para a esquerda) para quando o microfone falha ou o lugar está barulhento.

O visual partiu de dois vídeos de assistentes estilo Jarvis; o protótipo está em
[`docs/prototipos/2026-10-01-orbe-e-cartoes.html`](docs/prototipos/2026-10-01-orbe-e-cartoes.html).

> O código antigo, que dava voz ao Claude Code no Windows, está em
> [`legado-windows/`](legado-windows/README.md).

## O que ela faz

| Você diz | Ela faz |
|---|---|
| "que horas são?" | Diz a hora e a data |
| "vai chover amanhã?", "como está o tempo em São Paulo?" | Previsão pelo Open-Meteo, em °C e km/h, com cartão dos três dias; sem cidade, usa a sua (`CLARISSE_CIDADE`) |
| "me dá as notícias de tecnologia" | Mostra as manchetes do g1 numeradas e pergunta se você quer que ela leia alguma |
| "lê a segunda", "lê a do WhatsApp" (ou clicar na manchete) | O cartão vira um bloco com foto, título e a matéria inteira, que ela lê com o parágrafo da vez aceso; "para" interrompe |
| "o que eu tenho na agenda hoje?", "e amanhã?", "e na semana?" | Lê o Outlook pela conta Microsoft do GNOME e mostra os horários |
| "tenho e-mail não lido?" | Fala quantos são e os 5 mais recentes (remetente e assunto); o cartão lista 10 |
| "lê o e-mail 2" (ou clicar nele) | Lê o e-mail inteiro, sem o histórico da conversa citado embaixo |
| "quais PRs minhas estão abertas?", "tem PR para eu revisar?" | Consulta o GitHub pelo `gh` |
| "o CI da PR 9 da clarisse passou?" | Diz quantas checagens passaram, falharam ou estão rodando |
| "o omni-app está no ar?" | Situação no Dokploy e como foi o último deploy |
| "procura nas notas sobre sicoob captcha", "lê a nota 1" | Busca no cofre do Obsidian (`CLARISSE_COFRE_DE_NOTAS`) e lê a nota sem a marcação do Markdown |
| "me lembra em 20 minutos de ligar para o financeiro", "me lembra às 9h de…" | Marca o lembrete; na hora, ela fala e mostra o cartão. "Quais lembretes?" e "cancela o lembrete 1" também |
| "lê o que o Claude disse no projeto omni-api", "lê a última resposta do Claude" | Lê na íntegra a última resposta do Claude Code: da conversa mais recente que mexeu no projeto, ou da mais recente de todas |
| "abre o Claude no omni api e pede pra ele corrigir o teste" | Abre o VS Code e um terminal com o Claude já trabalhando no pedido |
| "abre o chrome", "fecha o chrome" | Abre ou fecha um aplicativo cadastrado (fechar pede confirmação) |
| "quais programas estão abertos?" | Diz quais aplicativos cadastrados estão abertos |
| "abre a pasta de downloads" | Abre a pasta (só dentro da sua pasta pessoal) |
| "abre o github", "abre o kanban" | Abre o site no navegador (inclui os sistemas da empresa no Dokploy) |
| "abaixa o volume pra trinta" | Ajusta o volume |
| "abre o projeto omni api no VS Code" | Abre o projeto cadastrado no VS Code |
| "roda um git status no omni api" | Roda e resume; `git pull` pede confirmação |
| "traz o VS Code pra frente", "coloca o WhatsApp na frente" | Traz para a frente uma janela já aberta, sem abrir outra |
| "escreve bom dia equipe no WhatsApp" | Pede confirmação, traz a janela e cola o texto onde o cursor estiver; não aperta Enter |
| "salva", "aperta enter", "desfaz", "fecha essa aba" | Aperta o atalho na janela pedida ou na da frente; fechar aba ou janela pede confirmação |
| "abre a planilha de boletos", "abre o readme do smart anchor" | Procura o arquivo na pasta pessoal e abre; com vários, lista os 3 mais recentes |
| "roda o smart anchor", "sobe o omni app" | Acha o projeto, abre um terminal por parte, instala as dependências se faltarem e abre o site quando responder; a confirmação diz qual banco o `.env` usa |
| "qual a cotação do dólar?" | Sem o Claude ligado, diz que não sabe: o modelo local inventa fatos quando tenta |
| "para", "cancela" | Para na hora, sem passar pelo modelo |

Ações que alteram algo esperam o seu **"sim"** falado. Qualquer outra resposta cancela.

### Com o Claude ligado (`CLARISSE_USAR_CLAUDE=true`)

| Você diz | Ela faz |
|---|---|
| "pergunta pro Claude por que o build quebra", "o que é a Smart Compass?" | Manda para o Claude em segundo plano (ele pesquisa na internet) e fala a resposta quando chega |
| "marca uma reunião com o João amanhã às três" | Pede confirmação e cria pelo Claude; o Claude acha a pessoa e **não cria** se o nome for ambíguo |
| "manda pra conversa omni do Claude: roda os testes de novo" | Pede confirmação e entrega a mensagem numa conversa do Claude **já aberta** |
| "vê no navegador quanto está o dólar hoje" | Pede confirmação e manda um Claude que só enxerga o navegador; ele lê e navega, mas não envia formulário |
| "abre o kanban e depois me diz o tempo" (com "e depois", "em seguida"…) | Vai inteiro para um Claude que usa as ferramentas da própria Clarisse, etapa por etapa |

## Como funciona

```
navegador (anel e cartões)                  servidor local (127.0.0.1:8765)
┌──────────────────────┐   WebSocket    ┌──────────────────────────────────┐
│ microfone            │ ─── áudio ───► │ transcrição: faster-whisper      │
│ anel + constelação   │ ◄── eventos ── │ agente ─► Ollama (Gemma 4 e4b)   │
│ cartões e fileira    │ ◄── cartões ── │   └─► segurança ─► ferramentas   │
│ voz da Clarisse      │ ◄── mp3 ────── │ voz: edge-tts                    │
└──────────────────────┘                └──────────────────────────────────┘
atalho do GNOME ─► scripts/alternar-escuta.sh ─► liga/desliga o microfone
```

O modelo **não executa nada**. Ele só escolhe uma ferramenta de uma lista fechada;
o sistema valida os argumentos, decide se precisa de confirmação, executa e registra.
Cada ferramenta diz em que nó da constelação acende e pode devolver um cartão.

O que vem de fora e foi escrito por outra pessoa — lista de e-mails, corpo do e-mail,
matéria, título de PR — é falado direto pelo sistema, sem passar pelo modelo: um
e-mail não consegue virar instrução para ela.

As escolhas foram medidas, não supostas:

- [`docs/medicoes/2026-09-28-roteador/`](docs/medicoes/2026-09-28-roteador/README.md):
  por que o `gemma4:e4b-it-qat` (29 de 32 pedidos certos, 0,27 s, cabe inteiro em
  8 GB de placa de vídeo). O Qwen acertou 31, mas levou 0,72 s.
- [`docs/planos/2026-10-01-visual-novo-e-so-gemma-plano.md`](docs/planos/2026-10-01-visual-novo-e-so-gemma-plano.md):
  o visual novo, o modo só Gemma e os conectores.

## Requisitos

- Linux com GNOME (testado no Ubuntu 26.04, Wayland) e PipeWire.
- [uv](https://docs.astral.sh/uv/) — ele instala o Python 3.12 sozinho.
- [Ollama](https://ollama.com) com o modelo `gemma4:e4b-it-qat`.
- Placa de vídeo com pelo menos 6 GB é recomendada; a transcrição roda no processador.
- Chrome ou Firefox, para a tela e o microfone.
- Para a agenda e o e-mail: a conta Microsoft 365 ligada em Configurações → Contas on-line.
- Para o GitHub: o `gh` instalado e logado.
- Para mexer nas janelas: a extensão [Window Calls](https://extensions.gnome.org/extension/4724/window-calls/)
  do GNOME e o teclado virtual (`scripts/instalar-teclado-virtual.sh`).
- Só com o Claude ligado: Claude Code instalado e logado, e Node.js (`npx`).

## Instalação

```bash
git clone https://github.com/Pujol0100/clarisse.git
cd clarisse
uv sync
ollama pull gemma4:e4b-it-qat
cp config/projetos.exemplo.json config/projetos.json
cp config/aplicativos.exemplo.json config/aplicativos.json
cp config/pastas.exemplo.json config/pastas.json
```

Edite os três arquivos em `config/` com os seus projetos, aplicativos e pastas.
Eles nunca vão para o git.

Opcional: `config/bancos.json` (copie de `config/bancos.exemplo.json`) dá nome aos
bancos que os seus projetos usam e marca os de produção. Ao rodar um projeto, a
Clarisse fala o nome do banco e **recusa** os marcados como produção.

Opcional, uma vez só:

```bash
scripts/instalar-no-menu.sh    # põe a Clarisse no menu de aplicativos
scripts/instalar-atalho.sh     # Ctrl+Alt+C liga e desliga o microfone, com qualquer janela na frente
scripts/instalar-teclado-virtual.sh   # ydotool e wl-clipboard, para colar texto e apertar atalhos (pede senha)
```

O atalho guarda o caminho do script: se a pasta da Clarisse mudar de lugar, rode
`scripts/instalar-atalho.sh` de novo a partir da pasta nova.

O teclado virtual precisa de permissão no `/dev/uinput`. O script dá essa permissão
só a quem está usando a máquina, sem pôr o usuário no grupo `input`, que também
lê tudo o que é digitado no teclado de verdade.

O texto entra **colado**, não digitado letra por letra: o `ydotool` digita como
teclado americano e, no ABNT2, perderia os acentos e trocaria símbolos. Por isso
o texto colado fica na área de transferência depois.

## Uso

```bash
scripts/ligar.sh
```

Ela confere o ambiente, liga o Ollama se precisar e abre a página. Na primeira vez,
clique em qualquer lugar da página e autorize o microfone.

- **Falar:** `Ctrl+Alt+C` de qualquer lugar, a barra de espaço com a página em foco,
  ou o botão no canto inferior direito. Aperta, fala, aperta de novo para enviar.
- **Escolher numa lista** (manchetes, e-mails, notas): diga o número ou clique no item.
  O cartão de escolha fica na tela até o próximo cartão chegar.
- **Escrever:** botão Escrever, no canto inferior esquerdo. O chat também mostra a
  conversa por voz. O × fecha e volta só para a voz.
- **Desligar:** `Ctrl+C` na janela do terminal, ou `scripts/desligar.sh`.

Ajustes ficam em `.env`; veja `.env.example`. Os principais:

| Variável | Para quê |
|---|---|
| `CLARISSE_CIDADE` | Cidade da previsão do tempo quando você não diz uma |
| `CLARISSE_COFRE_DE_NOTAS` | Pasta do cofre do Obsidian; sem ela, não há busca nas notas |
| `CLARISSE_USAR_CLAUDE` | `true` volta a mandar pedidos ao Claude (padrão: desligado) |
| `CLARISSE_MODELO`, `CLARISSE_VOZ` | Modelo local e voz |

### Calendário do Linux

O calendário do GNOME é uma cópia da agenda do Outlook, e sozinho ele quase não
atualiza (em 29/09/2026 ficou duas horas parado). Enquanto está ligada, a
Clarisse pede ao Linux que busque as mudanças a cada 5 minutos
(`CLARISSE_AGENDA_INTERVALO_MINUTOS`). A leitura da agenda pela Clarisse vai direto
ao Outlook e não depende dessa cópia.

## Testes

```bash
uv run pytest
```

## Privacidade

- O modelo, a transcrição, a auditoria, as notas do Obsidian e os lembretes ficam na máquina.
- **O texto da resposta vai para a Microsoft** para virar voz (edge-tts), inclusive
  o e-mail ou a matéria que ela lê.
- A agenda e o e-mail são lidos no Microsoft Graph com o acesso da conta do GNOME, só leitura.
- O GitHub é lido pelo `gh`; o Dokploy, com a chave de leitura que o Claude Code já usa.
- As notícias vêm do feed do g1; as fotos das matérias, do servidor de imagens da Globo.
- A previsão do tempo consulta o Open-Meteo (gratuito para uso pessoal, sem conta).
- Com o Claude ligado, o que é delegado a ele vai para a Anthropic.
- Logs, áudio, auditoria, lembretes e o registro da conversa ficam em `dados/`, fora do git.

Detalhes e riscos aceitos em [`SEGURANCA.md`](SEGURANCA.md).

## Ainda não faz

- Acordar com a palavra "Clarisse" (em agosto nenhum motor gratuito acertou isso em
  português; fica para uma medição nova).
- Criar compromisso na agenda sem o Claude.
- Pesquisar na internet sem o Claude.
- Escolher o contato no WhatsApp: ela cola o texto na conversa que estiver aberta
  (não existe API oficial para conta pessoal).
- Clicar com o mouse em outros programas: ela traz janelas, cola texto e aperta
  atalhos, mas não clica.
- Voz 100% offline.

## Licença

MIT — veja [LICENSE](LICENSE).
