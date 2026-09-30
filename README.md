# Clarisse

Assistente de voz que roda no seu computador Linux. Você fala, ela entende com um
modelo de linguagem **local**, executa a ação na máquina e responde falando. Quando
a tarefa pede uma IA mais forte, ela passa o pedido para o
[Claude Code](https://claude.com/claude-code) e fala o resultado quando fica pronto.

A cara dela é um enxame de "drones" de luz na tela do navegador: uma esfera que
muda de cor e de ritmo quando ouve, pensa e faz; uma onda que pulsa com a voz
quando fala; e, quando a resposta pede, uma figura — sol, nuvem, chuva,
trovoada, calendário, relógio, jornal, código ou balão de mensagem. Quem escolhe a
figura é o sistema, pela ferramenta usada e pelo dado, nunca o modelo.

> O código antigo, que dava voz ao Claude Code no Windows, está em
> [`legado-windows/`](legado-windows/README.md).

## O que ela faz

| Você diz | Ela faz |
|---|---|
| "que horas são?" | Diz a hora e a data |
| "abre o chrome", "fecha o chrome" | Abre ou fecha um aplicativo cadastrado (fechar pede confirmação) |
| "quais programas estão abertos?" | Diz quais aplicativos cadastrados estão abertos |
| "abre a pasta de downloads" | Abre a pasta (só dentro da sua pasta pessoal) |
| "abre o github" | Abre o site no navegador |
| "abaixa o volume pra trinta" | Ajusta o volume |
| "abre o projeto omni api no VS Code" | Abre o projeto cadastrado no VS Code |
| "roda um git status no omni api" | Roda e resume; `git pull` pede confirmação |
| "me dá as notícias de economia" | Lê as manchetes do g1 |
| "vai chover amanhã?", "como está o tempo em São Paulo?" | Previsão pelo Open-Meteo, em °C e km/h; sem cidade, usa a sua (`CLARISSE_CIDADE`) |
| "o que eu tenho na agenda hoje?" | Pergunta ao Claude, que lê o seu calendário do Microsoft 365 |
| "marca uma reunião com o João amanhã às três" | Pede confirmação e cria pelo Claude; o calendário do Linux é atualizado na hora |
| "abre o Claude no omni api e pede pra ele corrigir o teste" | Abre o VS Code e um terminal com o Claude já trabalhando no pedido |
| "pergunta pro Claude por que o build quebra" | Manda para o Claude em segundo plano e fala a resposta quando chega |
| "manda pra conversa omni do Claude: roda os testes de novo" | Pede confirmação e entrega a mensagem numa conversa do Claude **já aberta** (dê nome à conversa com `/rename`) |
| "vê no navegador quanto está o dólar hoje" | Pede confirmação e manda um Claude que só enxerga o navegador (Playwright, janela visível); ele lê e navega, mas não envia formulário, não compra e não altera nada |
| "traz o VS Code pra frente", "coloca o WhatsApp na frente" | Traz para a frente uma janela já aberta, sem abrir outra |
| "escreve bom dia equipe no WhatsApp" | Pede confirmação, traz a janela e cola o texto onde o cursor estiver; não aperta Enter |
| "salva", "aperta enter", "desfaz", "fecha essa aba" | Aperta o atalho na janela pedida ou na da frente; fechar aba ou janela pede confirmação |
| "marca uma reunião amanhã às 10 com o Bruno Santos" | Pede confirmação dizendo quem será convidado; o Claude acha a pessoa na empresa e **não cria** se o nome for ambíguo |
| "abre a planilha de boletos", "abre o readme do smart anchor" | Procura o arquivo na pasta pessoal (nome e pasta; "planilha", "pdf", "documento" viram tipo) e abre; com vários, lista os 3 mais recentes |
| "roda o smart anchor", "sobe o omni app" | Acha o projeto, abre um terminal por parte (`npm run dev` ou `start:dev`) e abre o site quando responder; a confirmação diz qual banco o `.env` usa |
| "o que é a Smart Compass?", "qual a cotação do dólar?" | Pede ao Claude, que pesquisa na internet, e fala a resposta |
| "para", "cancela" | Para na hora, sem passar pelo modelo |

Ações que alteram algo esperam o seu **"sim"** (ou o botão Confirmar). Qualquer
outra resposta cancela.

## Como funciona

```
navegador (bola neural)                     servidor local (127.0.0.1:8765)
┌──────────────────────┐   WebSocket    ┌──────────────────────────────────┐
│ microfone            │ ─── áudio ───► │ transcrição: faster-whisper      │
│ bola neural          │ ◄── eventos ── │ agente ─► Ollama (Gemma 4 e4b)   │
│ voz da Clarisse      │ ◄── mp3 ────── │   └─► segurança ─► ferramentas   │
└──────────────────────┘                │ voz: edge-tts                    │
                                        └──────────────────────────────────┘
atalho do GNOME ─► scripts/alternar-escuta.sh ─► liga/desliga o microfone
```

O modelo **não executa nada**. Ele só escolhe uma ferramenta de uma lista fechada;
o sistema valida os argumentos, decide se precisa de confirmação, executa e registra.

As escolhas foram medidas, não supostas:

- [`docs/medicoes/2026-09-28-roteador/`](docs/medicoes/2026-09-28-roteador/README.md):
  por que o `gemma4:e4b-it-qat` (29 de 32 pedidos certos, 0,27 s, cabe inteiro em
  8 GB de placa de vídeo).
- [`docs/planos/2026-09-28-clarisse-assistente-local-design.md`](docs/planos/2026-09-28-clarisse-assistente-local-design.md):
  o desenho e as decisões.

## Requisitos

- Linux com GNOME (testado no Ubuntu 26.04, Wayland) e PipeWire.
- [uv](https://docs.astral.sh/uv/) — ele instala o Python 3.12 sozinho.
- [Ollama](https://ollama.com) com o modelo `gemma4:e4b-it-qat`.
- Placa de vídeo com pelo menos 6 GB é recomendada; a transcrição roda no processador.
- Claude Code instalado e logado, para as tarefas delegadas ao Claude.
- Chrome ou Firefox, para a tela e o microfone.
- Node.js (`npx`), para as tarefas no navegador.
- Para mexer nas janelas: a extensão [Window Calls](https://extensions.gnome.org/extension/4724/window-calls/)
  do GNOME e o teclado virtual (`scripts/instalar-teclado-virtual.sh`).

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

- **Falar:** botão Falar, barra de espaço com a página em foco, ou `Ctrl+Alt+C` de
  qualquer lugar. Aperta, fala, aperta de novo.
- **Escrever:** o campo de texto faz o mesmo que a voz.
- **Desligar:** `Ctrl+C` na janela do terminal, ou `scripts/desligar.sh`.

Ajustes (modelo, voz, velocidade, cidade para a previsão do tempo, teto de gasto do
Claude) ficam em `.env`; veja `.env.example`.

### Calendário do Linux

O calendário do GNOME é uma cópia da agenda do Outlook, e sozinho ele quase não
atualiza (em 29/09/2026 ficou duas horas parado). Enquanto está ligada, a
Clarisse pede ao Linux que busque as mudanças a cada 5 minutos
(`CLARISSE_AGENDA_INTERVALO_MINUTOS`) e logo depois de criar um compromisso.

## Testes

```bash
uv run pytest
```

## Privacidade

- O modelo, a transcrição e a auditoria ficam na máquina.
- **O texto da resposta vai para a Microsoft** para virar voz (edge-tts).
- O que é delegado ao Claude vai para a Anthropic.
- A previsão do tempo consulta o Open-Meteo (gratuito para uso pessoal, sem conta).
- Logs, áudio, auditoria e o registro da conversa (`dados/conversa.jsonl`) ficam em
  `dados/`, fora do git.

Detalhes e riscos aceitos em [`SEGURANCA.md`](SEGURANCA.md).

## Ainda não faz

- Acordar com a palavra "Clarisse" (em agosto nenhum motor gratuito acertou isso em
  português; fica para uma medição nova).
- Escolher o contato no WhatsApp: ela cola o texto na conversa que estiver aberta
  (não existe API oficial para conta pessoal).
- Clicar com o mouse em outros programas: ela traz janelas, cola texto e aperta
  atalhos, mas não clica.
- Voz 100% offline.

## Licença

MIT — veja [LICENSE](LICENSE).
