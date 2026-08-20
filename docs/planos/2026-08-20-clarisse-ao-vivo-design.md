# Clarisse ao Vivo — ela lê o dia todo no seu lugar (design)

Data: 20/08/2026
Etapa: 1 de 3 — o laço de voz
Status: desenho revisado após correção de propósito; aguardando revisão desta especificação

## O problema

Hoje a Clarisse é um caminho de mão única. O Claude termina uma resposta, um hook
enfileira um resumo, o usuário aperta `Ctrl+Alt+L` e ela lê. Não existe entrada
de áudio no projeto.

Mas o problema real do usuário não é falta de microfone. É que **ele tem cerca de
dez sessões do Claude Code abertas e não consegue ler tudo o dia todo** — e ler
na tela é justamente a dificuldade de acessibilidade que deu origem ao projeto.
O resumo de fim de resposta ajuda, mas ele só cobre o instante em que uma sessão
termina. Não responde "o que está rolando no omni-api agora", "algum projeto
travou", "o que ele decidiu sobre a conciliação".

## O propósito, na ordem certa

1. **Ela lê no lugar do usuário.** Todas as sessões, ao vivo, e responde
   perguntas faladas sobre qualquer uma delas. Isso é leitura: não altera nada,
   não pede permissão, não corre risco. É o valor principal.
2. **Ela age.** Executa trabalho de código, por voz, com autorização falada.
   Isso é o valor secundário, e é a parte que precisa de proteção.

Uma versão inicial deste design tratou o item 1 como impossível e o item 2 como o
projeto. Estava errado, e a correção veio do usuário.

## A descoberta que sustenta o item 1

O Claude Code grava a conversa de cada sessão em disco, ao vivo, em
`~/.claude/projects/<projeto>/<sessão>.jsonl` — uma linha por evento.

Verificado em 20/08/2026: 18 projetos com histórico, e o arquivo da sessão em
andamento sendo escrito durante a própria verificação.

Cada linha traz quem falou, o conteúdo, o horário, a pasta de trabalho, a branch,
qual ferramenta foi usada e o que ela devolveu. Existe também uma linha de título
gerado da conversa.

Portanto a Clarisse **pode** ver o que está rolando no Claude Code. Não pela
memória do agente dela — por leitura.

## O que este design não é

- Não é cancelamento de eco acústico. A interrupção da fala é pela tecla.
- Não é ClickUp nem Microsoft 365. Etapa 2, depois de resolver dado de terceiro.
- Não é automação de interface do Windows.
- **Ela nunca digita numa janela ou aba de terminal.** Ver a seção sobre pedidos
  de permissão.
- Ela nunca inicia conversa. Só responde.
- Não funciona sem internet.

## Decisões fechadas com o usuário

| Decisão | Escolha | Por quê |
|---|---|---|
| Valor principal | **Ler as sessões e relatar por voz** | É o problema real: não conseguir ler dez sessões o dia todo |
| Quem executa a ação | Agente próprio, com o Claude Agent SDK | Age independente de haver terminal aberto |
| Agir com o contexto de uma sessão | `--resume <sessão> --fork-session` | Herda todo o contexto daquela conversa **sem tocar na sessão viva** |
| Transcrição da fala | Serviço de fala da Azure, em streaming | Português do Brasil de qualidade; local nesta máquina custaria 1,5 a 3 s por frase |
| Palavra de ativação | Modelo local da Azure, gerado no Speech Studio | Roda offline; nenhum áudio sai antes dela ouvir o nome |
| Formas de ativar | **As duas**: tecla `F6` e a palavra "Clarisse" | Decisão do usuário, reafirmada após eu argumentar contra |
| Comportamento da tecla | Aperta liga, aperta desliga | Melhor para pedido longo, coerente com o modo mãos-livres |
| Modo mãos-livres | **Desligado por padrão** | Mantém o microfone aberto; ligar é decisão consciente |
| Em qual projeto ela age | O usuário nomeia ao ativar; ela confirma falando | Adivinhar é falhar em silêncio na pasta errada |
| Autorização para agir | Ler é livre; alterar pede voz; destrutivo exige teclado | Transcrição erra, e um "pode" mal ouvido não pode custar um arquivo |
| Fim do turno | Janela de conversa de ~20 s; silêncio fecha | Continuar o diálogo sem repetir o nome |
| Fim de ação longa | **Bipe, sem falar.** O resultado sai quando pedido | Voz que dispara sozinha atropela quem está no meio de outra coisa |
| Pedido de permissão travado | **Consertar a causa na lista de permissões; ela só avisa** | Aba de terminal não pode ser alvejada, e o problema real é pedir permissão para o que sempre se aprova |

## Recorte em etapas

| Etapa | Entrega |
|---|---|
| **1 (esta)** | Ler e relatar as sessões; laço de voz completo; agente que age com autorização falada; agir com o contexto de uma sessão existente |
| 2 | ClickUp e Microsoft 365, depois de resolvidas as regras de dado sensível |
| 3 | Cancelamento de eco acústico — só se a tecla provar não bastar |

## Arquitetura

Um processo residente novo, a **Clarisse ao Vivo**, sobe junto com o escutador de
atalhos que já existe. Cinco partes, cada uma com uma responsabilidade só, mais o
painel.

| Parte | Responsabilidade única | Depende de |
|---|---|---|
| **Ouvinte** | Abrir e fechar o microfone, detectar a palavra falada, entregar a frase como texto | SDK de fala da Azure |
| **Leitora** | Ler as transcrições das sessões e responder o que está acontecendo | Só o sistema de arquivos |
| **Agente** | Conversar com o Claude, executar as ações, devolver a resposta em pedaços | Claude Agent SDK |
| **Voz ao vivo** | Falar os pedaços conforme chegam; calar na hora quando mandado | O `falar.py` que já existe |
| **Portaria** | Decidir se uma ação é livre, pede voz, ou exige teclado | Só a configuração |
| **Painel** | Mostrar estado, o texto entendido, e confirmações esperando teclado | Nada |

### A Leitora

É a peça que entrega o valor principal, e é a mais simples de todas: lê arquivos e
não escreve nada. Ela não interpreta nem resume — isso é trabalho do Agente. Ela
entrega recortes:

- Os eventos mais recentes de um projeto.
- O que aconteceu num intervalo de tempo.
- Se uma sessão está parada esperando permissão, e **o que exatamente** está sendo
  pedido.
- Quais sessões existem, de quais projetos, e quando cada uma se moveu por último.
- O identificador de sessão de um projeto, para o Agente poder retomar o contexto.

Perguntas que isso passa a atender, nenhuma delas exigindo autorização:

- "O que está rolando no omni-api?"
- "Algum projeto travou esperando permissão?"
- "O que o Claude fez no api-gestora na última meia hora?"
- "Ele decidiu o quê sobre a conciliação?"
- "Me dá um resumo de tudo que andou hoje."

### Requisito de privacidade que a Leitora cria

As transcrições contêm **tudo** — código, dado de cliente, qualquer coisa colada
num terminal. Quando ela resume uma transcrição e fala, esse resumo vai para a
Microsoft virar áudio.

Hoje existe uma regra no `CLAUDE.md` que instrui o Claude a não pôr credencial,
dado pessoal de terceiro, nome de cliente nem valor exato de contrato no resumo
falado. Essa regra passa a valer para **a Clarisse resumindo transcrição bruta**, e
por dois mecanismos, porque um só não basta:

1. Instrução explícita no prompt do Agente, no mesmo espírito da regra existente.
2. Um filtro mecânico antes do texto ir para a síntese, que barra formatos
   evidentes de segredo — chave, token, senha, cabeçalho de autorização.

**Risco residual declarado:** o filtro pega formato, não sentido. Um nome de
cliente dito em texto corrido passa. A mitigação real é o item 1, que é uma
instrução e não uma garantia. Quem usa isso com dado de cliente precisa saber.

### A Portaria

Três faixas, e uma regra que vale mais que as três: **o que a Portaria não
reconhece cai na faixa mais restritiva.** Ferramenta nova, comando estranho,
argumento inesperado — vai para o teclado.

Isso é o contrário do costume em software, e é o certo aqui: errar para o lado
seguro custa uma tecla; errar para o outro lado custa um arquivo.

| Faixa | O que entra | Comportamento |
|---|---|---|
| **Livre** | Ler arquivo, buscar texto, listar pasta, **ler transcrição de sessão**, pesquisar na web, comando que só consulta | Faz e nem comenta |
| **Pergunta falando** | Escrever ou editar arquivo **dentro** da pasta do projeto, rodar teste, criar branch, fazer commit | "Vou editar o núcleo, pode?" e espera a voz |
| **Exige teclado** | Apagar, sobrescrever, `push`, desfazer histórico, **qualquer caminho fora da pasta do projeto**, enviar mensagem, e **tudo que não for reconhecido** | Fala "isso eu não faço por voz", mostra no painel, espera a tecla |

Toda a Leitora vive na faixa livre. É por isso que o valor principal do projeto
não carrega risco nenhum.

### A assimetria do "sim"

A defesa contra transcrição errada não é aumentar a precisão — é tornar o erro
inofensivo. **Só um "sim" claro é sim; qualquer outra coisa é não.**

- Lista curta e **fechada**: "pode", "sim", "manda", "pode sim". Nada fora dela
  aprova.
- Silêncio é não. Ruído é não. "pode ser?" é não. "poder" é não. Confiança baixa
  reportada pela Azure é não.
- A pergunta **expira em cerca de dez segundos** e ela cancela dizendo que
  cancelou.
- **Não existe "pode em tudo"** por voz. Uma aprovação vale para uma ação. Modo
  permissivo é configuração digitada.

Consequência desejada: um erro de audição custa repetir uma palavra, nunca um
arquivo.

### O painel

Uma janela pequena e visível, mostrando estado (calada / ouvindo / pensando /
falando), **o texto exato que ela entendeu**, e as confirmações destrutivas
esperando teclado.

Não é enfeite. Quando a transcrição errar — e vai errar — ver "roda os testes"
virar "roda os testos" na tela é a diferença entre entender o problema em dois
segundos ou concluir que ela é inútil. É também o único lugar onde uma
confirmação de teclado pode aparecer, já que o processo é residente.

### Estado compartilhado

O estado fica num arquivo pequeno, pelo mesmo mecanismo que a pausa da fala já
usa hoje. É o que permite ao atalho e ao processo conversarem sem travar um no
outro.

### A tecla `F6`

Entra no `atalhos.ps1`, junto com as quatro combinações existentes:

| Estado ao apertar | O que acontece |
|---|---|
| Calada | Abre o microfone, bipe curto |
| Ouvindo | Fecha o microfone e manda processar |
| **Falando** | **Cala a boca dela e abre o microfone** |

O terceiro caso é a interrupção sem cancelamento de eco.

Custo aceito: um atalho global com tecla sozinha faz o Windows entregar essa
tecla só para a Clarisse. `F6` deixa de funcionar no navegador e no editor. A
tecla é configurável.

## Agir com o contexto de uma sessão existente

Quando o pedido é "no omni-api, continua o que a gente estava fazendo", a Clarisse
não precisa do contexto dela — precisa do **daquela conversa**.

O Claude Code permite retomar uma sessão por identificador. Combinado com
`--fork-session`, a retomada **cria uma sessão nova** em vez de reusar a
original. Verificado na ajuda do CLI em 20/08/2026:

- `-r, --resume [valor]` — retoma por identificador de sessão.
- `--fork-session` — ao retomar, cria um identificador novo em vez de reusar.
- `--output-format stream-json` com `--include-partial-messages` — resposta em
  fluxo, que é o que a voz progressiva precisa.

Fluxo: a Leitora encontra o identificador da última sessão daquele projeto; o
Agente retoma com fork; o trabalho acontece numa sessão separada; a resposta sai
em fluxo e vira voz.

**A sessão viva do usuário não é tocada.** Isso é melhor que injetar texto: tem o
contexto *e* não corre risco.

## Pedidos de permissão travados: consertar a causa

Uma sessão parada pedindo permissão é um processo bloqueado esperando uma tecla.
Nenhum arquivo, comando ou API desbloqueia — só uma tecla naquele terminal.

E o alvo não é endereçável. Verificado em 20/08/2026: o título da janela do
terminal traz o **título da conversa**, não o projeto; e sessões em **abas** de uma
janela do Windows Terminal não podem ser alvejadas individualmente — a tecla vai
para a aba ativa.

**Decisão: atacar a causa.** Se sessões travam todo dia pedindo permissão, o
problema não é a dificuldade de responder — é que estão pedindo permissão para o
que o usuário sempre aprova. Isso se resolve ajustando a lista de permissões do
Claude Code. Existe ferramenta instalada para isso, que varre o histórico e propõe
a lista.

Para o que sobrar, a Clarisse **avisa**: fala qual projeto travou e **o que
exatamente** está sendo pedido, com detalhe suficiente para o usuário decidir sem
ler nada. A tecla é dele.

Isso aplica a regra do próprio projeto: achar a causa, não remendar o sintoma.

## O fluxo de um turno

O usuário aperta `F6` e diz "no voz-ao-claude, roda os testes":

1. `F6` — microfone abre, bipe curto. Imediato.
2. O usuário fala; a Azure transcreve em fluxo.
3. `F6` de novo — microfone fecha. Texto final em cerca de 0,3 a 0,5 s.
4. A Portaria vê "rodar teste" na faixa do meio: precisa de voz.
5. Ela fala: "No voz-ao-claude. Vou rodar os testes, pode?" — primeira voz em
   cerca de 1 s.
6. O usuário: "pode". O microfone abre sozinho aqui.
7. Ela roda. Fala **"rodando"** e **cala**.
8. Terminou: **dois bipes curtos**, distintos do bipe do resumo assíncrono.
   Nenhuma palavra.
9. O resultado fica guardado como "última conclusão do voz-ao-claude" e **também
   entra na fila que já existe** — `Ctrl+Alt+L` funciona nele igual.
10. O usuário aperta `F6`: "o que aconteceu?", "o que deu nos testes?" — **aí**
    ela fala.

Se o usuário não perguntar, ela não fala. Nunca.

Num pedido de leitura pura — "o que está rolando no omni-api?" — os passos 4 a 6
não existem: a Leitora responde direto.

### Quando exatamente o microfone está aberto

Esta é a parte que mais importa para privacidade, e por isso está enumerada de
forma exaustiva. O microfone está aberto em exatamente quatro situações:

1. Entre um `F6` que liga e o `F6` que desliga.
2. Durante a **janela de conversa** de cerca de 20 s depois dela terminar de
   falar. O silêncio fecha. Configurável; zero produz turno único.
3. Durante os cerca de 10 s de espera por uma autorização. **É a única situação
   em que o microfone abre sem o usuário ter apertado nada**, e é deliberada:
   exigir tecla para dizer "pode" destruiria a conversa no momento em que ela mais
   importa. A abertura é anunciada pela própria pergunta dela.
4. Continuamente, se e somente se o modo mãos-livres estiver ligado — e ele nasce
   desligado.

**A janela de conversa fecha ao iniciar uma ação longa.** Depois de "rodando", o
microfone está fechado, mesmo que a ação leve minutos. O bipe de conclusão é o
ponto de reentrada.

### Orçamento de tempo

**Estimativa, não medição:** 2 a 4 s entre o usuário calar a boca e a voz dela
começar. Composição estimada: fechamento da transcrição 0,3–0,5 s, primeiro texto
do Claude 0,8–2 s, primeiro pedaço de áudio ~1 s.

**O primeiro item do plano é medir esse caminho de ponta a ponta na máquina do
usuário, antes de construir as partes.** Se der 8 s, o design está errado, e isso
precisa aparecer na primeira semana.

Pedido de leitura pura deve ser mais rápido, porque não há trabalho de ferramenta
— o que faz dele o melhor caso para medir primeiro.

### Dois detalhes que decidem se soa vivo ou robótico

- Ela fala a **primeira frase**, não a resposta pronta. As duas pontas já existem:
  o Agent SDK entrega texto parcial, e o `falar.py` já sintetiza em fluxo.
- Ela narra o que está fazendo, porque numa conversa falada silêncio não é espera,
  é falha.

## Contexto de projeto

O usuário nomeia o projeto ao ativar. Ela confirma falando em qual entrou e fica
nele até ser trocado. Sem nome dito, usa o último; no primeiro pedido da sessão,
sem projeto definido, ela pergunta.

O nome dito é resolvido contra a lista de projetos que a Leitora conhece. Nome
que não resolve para exatamente um projeto faz ela perguntar em vez de escolher.

## Reaproveitamento do que já existe

| Peça existente | Uso no laço ao vivo |
|---|---|
| `falar.py` | Síntese em fluxo. Já corta o texto e começa a falar no primeiro pedaço |
| `atalhos.ps1` | Ganha `F6`. Atalho global e processo residente já de pé e testados |
| Arquivo de controle da fala | Pausa e cancelamento durante a fala ao vivo |
| Fila e caixa de entrada | Conclusão de ação longa entra na fila; `Ctrl+Alt+L` já a lê com a origem certa |
| Bipe | Sinal de conclusão. Dois curtos para distinguir do resumo assíncrono |
| Hook de notificação | Já avisa qual projeto pediu permissão; passa a dizer **o que** foi pedido |
| `config.json` | Ganha uma seção `aovivo` |

## Consequência estrutural: uma segunda suíte de testes

As bibliotecas necessárias são Python, então o laço ao vivo é Python.

O repositório hoje testa em PowerShell com Pester: **126 testes, todos passando**
na linha de base de 20/08/2026. O laço ao vivo adiciona uma suíte `pytest`. As
duas convivem; a verificação passa a ser dois comandos.

Registrado deliberadamente, e não num rodapé.

## Falhas e como cada uma se anuncia

| O que quebra | Como o usuário percebe |
|---|---|
| Sem internet, ou chave inválida | Bipe de erro e o motivo no painel |
| Apertou e não falou | Ela ignora, sem custo e sem resposta |
| Cota da Azure esgotada | Painel diz, com a palavra "cota" |
| Transcrição de sessão ilegível ou formato mudou | Ela diz que não conseguiu ler aquele projeto, **nomeando qual** |
| Comando falhou no projeto | Ela fala **uma frase** com o erro, não o despejo técnico |
| Processo ao vivo morreu | `F6` avisa em vez de não fazer nada |
| Windows recusou registrar `F6` | Motivo no log, como já acontece com as outras teclas |

## Estratégia de teste

**A parte perigosa é a que não precisa de microfone.** Portaria, interpretação do
"sim" e Leitora são todas testáveis com arquivo em disco e texto — sem áudio, sem
internet, sem custo.

Cobertura automatizada:

- Portaria: tabela de ferramenta mais argumento para faixa esperada, com os
  destrutivos um por um.
- **O desconhecido:** ferramenta inventada precisa cair no teclado.
- **A assimetria do sim:** "pode" aprova; "pode não", "poder", "pode ser", vazio,
  ruído e confiança baixa **todos** recusam.
- Leitora, contra transcrições de exemplo: encontra a sessão mais recente de um
  projeto; detecta sessão parada em pedido de permissão e extrai **o que** foi
  pedido; ignora linha malformada sem derrubar a leitura; devolve o identificador
  de sessão para retomada.
- **Filtro de segredo:** formatos evidentes de chave, token e senha não chegam à
  síntese.
- Extração do nome do projeto da frase falada, incluindo nome ambíguo.
- Máquina de estados do `F6`, inclusive apertar durante a fala.
- Conclusão de ação longa entra na fila com a origem certa e **não** dispara fala.
- A janela de conversa fecha ao iniciar ação longa.
- Janela de conversa em zero produz turno único.

Verificação manual, pelo usuário:

- Microfone e escolha de dispositivo de entrada.
- Palavra de ativação: acerta o nome, e não dispara com conversa ao redor.
- Qualidade da transcrição do português falado do jeito que ele fala.
- Se o relato falado de "o que está rolando" é realmente útil, ou vira ruído.

## Riscos conhecidos

| Risco | Gravidade | Mitigação |
|---|---|---|
| A latência real ficar muito acima de 4 s e a conversa soar morta | Alta | Medir antes de construir. Primeiro item do plano |
| **Transcrição de sessão indo para a síntese com dado sensível** | Alta | Instrução no prompt mais filtro mecânico de formatos de segredo. Risco residual declarado: o filtro pega formato, não sentido |
| O formato do arquivo de transcrição mudar numa atualização do Claude Code | Média | A Leitora ignora o que não entende e nomeia o projeto que não conseguiu ler, em vez de calar |
| Custo por turno: tokens do agente mais minuto de transcrição | Média | Leitura pura é mais barata que ação. Turno único evita a conversa sempre aberta |
| Palavra de ativação disparando com conversa ao redor | Média | Modo mãos-livres desligado por padrão |
| A janela de conversa de 20 s mantém o microfone aberto após cada resposta | Média | Enumeração exaustiva das quatro situações; janela configurável; zero produz turno único; fecha ao iniciar ação longa |
| `F6` sozinha rouba a tecla de todos os programas | Baixa | Configurável e documentada |
| Um "pode" mal ouvido | Baixa, por construção | A assimetria do sim. Grave nunca aceita voz |
| Segunda suíte de testes divide a verificação | Baixa | Documentar os dois comandos |

## Verificações pendentes antes de implementar

Itens confirmados como existentes, cuja forma exata precisa ser verificada contra
a biblioteca instalada e não assumida:

1. Palavra de ativação em Python: a documentação da Azure confirma que o recurso
   existe e **roda no dispositivo, offline**, a partir de um arquivo de modelo
   gerado no Speech Studio. Os exemplos lidos eram C# e iOS. A forma em Python
   precisa ser confirmada.
2. Nível de confiança da transcrição: a assimetria do sim depende de ler a
   confiança que a Azure reporta. Confirmar qual formato de saída expõe isso.
3. Retomada com fork pelo Claude Agent SDK em Python: confirmado na ajuda do CLI
   (`--resume`, `--fork-session`). Confirmar o nome da opção equivalente no SDK.
4. Definir a pasta de trabalho do agente pelo SDK.
5. Custo real por turno, medido.
6. Se o arquivo de transcrição é gravado com atraso suficiente para atrapalhar o
   relato "ao vivo", e de quanto é esse atraso.

## Pré-requisito que depende do usuário

Criar na Azure um recurso de fala e obter a chave, e gerar o modelo da palavra
"Clarisse" no Speech Studio. Exige login na conta dele.

O plano começa com um roteiro numerado para isso, dizendo em que tela clicar e o
que deve aparecer quando der certo.
