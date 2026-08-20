# Clarisse ao Vivo — conversa falada em tempo real (design)

Data: 20/08/2026
Etapa: 1 de 3 — o laço de voz
Status: desenho aprovado nas quatro seções; aguardando revisão desta especificação

## O problema

Hoje a Clarisse é um caminho de mão única. O Claude escreve um resumo, um hook
enfileira, o usuário aperta `Ctrl+Alt+L` e ela lê. Não existe entrada de áudio
no projeto.

O pedido é fechar o ciclo: falar com ela, ela responder falando, e ela executar
o que foi pedido — com o Claude Code por dentro fazendo o trabalho.

O caminho assíncrono que já existe **não muda**. Este é um segundo caminho, ao
vivo, que roda em paralelo e reaproveita o motor de voz.

## O que este design não é

- Não é cancelamento de eco acústico. Cortar a fala dela falando por cima, sem
  usar tecla, fica fora. A interrupção é pela tecla.
- Não é integração com ClickUp nem Microsoft 365. Isso é a etapa 2, e depende de
  resolver antes a questão de dado de terceiro entrando num laço de voz.
- Não é automação de interface gráfica do Windows. Abrir programas e mexer em
  janelas fica fora, por decisão explícita: automação de interface quebra a cada
  atualização.
- Ela nunca inicia conversa. Só responde.
- Não funciona sem internet.

## Decisões fechadas com o usuário

| Decisão | Escolha | Por quê |
|---|---|---|
| Quem executa a ação | Um agente próprio, com o Claude Agent SDK | Ela conversa e age por conta própria, independente de haver terminal aberto |
| Transcrição da fala | Serviço de fala da Azure, em streaming | Português do Brasil de qualidade e fechamento rápido; local nesta máquina custaria de 1,5 a 3 s por frase |
| Palavra de ativação | Modelo local da Azure (arquivo `.table`), gerado no Speech Studio | Roda offline; nenhum áudio sai da máquina antes dela ouvir o nome |
| Formas de ativar | **As duas**: tecla `F6` e a palavra "Clarisse" | Decisão do usuário, reafirmada depois de eu argumentar contra a palavra |
| Comportamento da tecla | Aperta liga, aperta desliga | Melhor para pedido longo e coerente com o modo mãos-livres |
| Modo mãos-livres | **Desligado por padrão** | Ele mantém o microfone aberto; ligar tem que ser decisão consciente |
| Em qual projeto ela age | O usuário nomeia ao ativar; ela confirma falando e fica nele | Com cerca de dez sessões abertas, adivinhar é falhar em silêncio na pasta errada |
| Autorização para agir | Ler é livre; alterar pede voz; destrutivo exige teclado | Transcrição erra, e um "pode" mal ouvido não pode custar um arquivo |
| Fim do turno | Janela de conversa de ~20 s; silêncio fecha | Continuar o diálogo sem repetir o nome dela |
| Fim de ação longa | **Bipe, sem falar.** O resultado só sai quando pedido | Aplica ao caminho ao vivo a regra que o projeto já tem: voz que dispara sozinha atropela quem está no meio de outra coisa |

## Recorte em etapas

| Etapa | Entrega |
|---|---|
| **1 (esta)** | Laço de voz completo: ativação por tecla e por palavra, transcrição, agente conversando, permissão falada, trabalho de código no projeto |
| 2 | ClickUp e Microsoft 365 nas mãos dela, depois de resolvidas as regras de dado sensível |
| 3 | Cancelamento de eco acústico — só se a etapa 1 provar que a tecla não basta |

## Arquitetura

Um processo residente novo, a **Clarisse ao Vivo**, sobe junto com o escutador de
atalhos que já existe. Quatro partes, cada uma com uma responsabilidade só.

| Parte | Responsabilidade única | Depende de |
|---|---|---|
| **Ouvinte** | Abrir e fechar o microfone, detectar a palavra falada, entregar a frase do usuário como texto | SDK de fala da Azure |
| **Agente** | Receber o texto, conversar com o Claude, executar as ações, devolver a resposta em pedaços | Claude Agent SDK |
| **Voz ao vivo** | Falar os pedaços conforme chegam; calar na hora quando mandado | O `falar.py` que já existe |
| **Portaria** | Decidir se uma ação é livre, pede voz, ou exige teclado | Só a configuração |

### Por que a Portaria é isolada

A Portaria é a peça que protege os arquivos do usuário, e por isso ela **não sabe
falar nem ouvir**. Recebe "qual ferramenta, com quais argumentos" e devolve uma
de três decisões. Isso a torna testável sem microfone, sem internet e sem custo:
a parte mais perigosa do sistema passa a ser a mais fácil de testar.

### O painel

O processo ao vivo tem uma janela pequena e visível. Ela mostra três coisas:

1. O estado: calada / ouvindo / pensando / falando.
2. **O texto exato que ela entendeu que o usuário disse.**
3. As confirmações destrutivas esperando teclado.

O painel não é enfeite. Quando a transcrição errar — e vai errar — ver
"roda os testes" virar "roda os testos" na tela é a diferença entre entender o
problema em dois segundos ou concluir que a Clarisse é inútil. É também o único
lugar onde uma confirmação de teclado pode aparecer, já que o processo é
residente e não tem terminal próprio.

### Estado compartilhado

O estado (ouvindo / pensando / falando / projeto atual) fica num arquivo pequeno,
pelo mesmo mecanismo que a pausa da fala já usa hoje. É isso que permite ao
atalho e ao processo conversarem sem um travar no outro.

### A tecla `F6`

Entra no `atalhos.ps1`, junto com as quatro combinações que já existem, e faz
três coisas dependendo do estado:

| Estado ao apertar | O que acontece |
|---|---|
| Calada | Abre o microfone, bipe curto de confirmação |
| Ouvindo | Fecha o microfone e manda processar |
| **Falando** | **Cala a boca dela e abre o microfone** |

O terceiro caso é a interrupção sem cancelamento de eco: em vez de detectar a voz
do usuário por cima da dela, o usuário aperta a tecla.

Custo aceito e registrado: um atalho global registrado com uma tecla sozinha,
sem `Ctrl` ou `Alt`, faz o Windows entregar essa tecla só para a Clarisse. `F6`
deixa de funcionar no navegador, no editor, em tudo. A tecla é configurável.

### Modo mãos-livres

A mesma máquina com uma chave diferente: em vez de esperar a tecla, o Ouvinte
roda continuamente o modelo local de palavra de ativação. Nasce desligado na
configuração.

## O fluxo de um turno

O usuário aperta `F6` e diz "no voz-ao-claude, roda os testes":

1. `F6` — microfone abre, bipe curto. Imediato.
2. O usuário fala; a Azure transcreve em fluxo.
3. `F6` de novo — microfone fecha. Texto final em cerca de 0,3 a 0,5 s.
4. A Portaria vê "rodar teste" na faixa do meio: precisa de voz.
5. Ela fala: "No voz-ao-claude. Vou rodar os testes, pode?" — primeira voz em
   cerca de 1 s.
6. O usuário: "pode". O microfone abre sozinho aqui; ninguém aperta nada.
7. Ela roda. Fala **"rodando"** e **cala**.
8. Terminou: **dois bipes curtos**, distintos do bipe simples do resumo
   assíncrono. Nenhuma palavra.
9. O resultado fica guardado como "última conclusão do voz-ao-claude" e **também
   entra na fila que já existe** — então `Ctrl+Alt+L` funciona nele igual.
10. O usuário aperta `F6`: "o que aconteceu?", "o que deu nos testes?",
    "fala o do voz-ao-claude". **Aí** ela fala.

Se o usuário não perguntar, ela não fala. Nunca.

### Quando exatamente o microfone está aberto

Esta é a parte do design que mais importa para privacidade, e por isso está
enumerada de forma exaustiva. O microfone está aberto em exatamente quatro
situações, e em nenhuma outra:

1. Entre um `F6` que liga e o `F6` que desliga.
2. Durante a **janela de conversa** de cerca de 20 s depois dela terminar de
   falar uma resposta — é o que permite continuar o diálogo sem repetir o nome.
   O silêncio fecha a janela. A janela é configurável, e defini-la como zero
   transforma o comportamento em turno único.
3. Durante os cerca de 10 s em que ela espera a resposta a um pedido de
   autorização. **Esta é a única situação em que o microfone abre sem o usuário
   ter apertado nada**, e ela é deliberada: exigir uma tecla para responder
   "pode" destruiria a conversa no momento em que ela mais importa. A abertura é
   anunciada pela própria pergunta dela, e fecha na resposta ou no fim dos 10 s.
4. Continuamente, se e somente se o modo mãos-livres estiver ligado — e ele nasce
   desligado.

**A janela de conversa fecha ao iniciar uma ação longa.** Depois de "rodando", o
microfone está fechado, mesmo que a ação leve minutos. O bipe de conclusão é o
ponto de reentrada: para falar com ela de novo, o usuário aperta `F6`.

### Orçamento de tempo

**Estimativa, não medição:** 2 a 4 s entre o usuário calar a boca e a voz dela
começar. Composição estimada: fechamento da transcrição 0,3–0,5 s, primeiro
texto do Claude 0,8–2 s, primeiro pedaço de áudio ~1 s.

**O primeiro item do plano de implementação é medir esse caminho de ponta a ponta
na máquina do usuário, antes de construir as quatro partes.** Se der 8 s, o
design está errado, e isso precisa aparecer na primeira semana e não na última.

### Dois detalhes que decidem se soa vivo ou robótico

- Ela fala a **primeira frase**, não a resposta pronta. O Claude ainda está
  escrevendo o resto quando a voz já começou. As duas pontas já existem: o Agent
  SDK entrega texto parcial, e o `falar.py` já sintetiza em fluxo.
- Ela narra o que está fazendo ("abrindo o arquivo", "rodando"), porque numa
  conversa falada silêncio não é espera, é falha.

## A Portaria

Três faixas, e uma regra que vale mais que as três: **o que a Portaria não
reconhece cai na faixa mais restritiva.** Ferramenta nova, comando estranho,
argumento inesperado — vai para o teclado.

Isso é o contrário do costume em software, e é o certo aqui: errar para o lado
seguro custa uma tecla; errar para o outro lado custa um arquivo.

| Faixa | O que entra | Comportamento |
|---|---|---|
| **Livre** | Ler arquivo, buscar texto, listar pasta, pesquisar na web, comando que só consulta | Faz e nem comenta |
| **Pergunta falando** | Escrever ou editar arquivo **dentro** da pasta do projeto, rodar teste, criar branch, fazer commit | "Vou editar o núcleo, pode?" e espera a voz |
| **Exige teclado** | Apagar, sobrescrever, `push`, desfazer histórico, **qualquer caminho fora da pasta do projeto**, enviar mensagem, e **tudo que não for reconhecido** | Fala "isso eu não faço por voz", mostra no painel, espera a tecla |

### A assimetria do "sim"

A defesa contra transcrição errada não é aumentar a precisão — é tornar o erro
inofensivo. **Só um "sim" claro é sim; qualquer outra coisa é não.**

- Lista curta e **fechada** de aprovações: "pode", "sim", "manda", "pode sim".
  Nada fora dela aprova.
- Silêncio é não. Ruído é não. "pode ser?" é não. "poder" é não. Transcrição com
  confiança baixa reportada pela Azure é não.
- A pergunta **expira em cerca de dez segundos** e ela cancela a ação dizendo que
  cancelou — não fica pendurada.
- **Não existe "pode em tudo"** por voz. Uma aprovação vale para uma ação. Modo
  permissivo, se o usuário quiser, é configuração digitada.

Consequência desejada: um erro de audição custa repetir uma palavra, nunca um
arquivo.

## Contexto de projeto

O usuário nomeia o projeto ao ativar. Ela confirma falando em qual entrou e fica
nele até ser trocado. Sem nome dito, usa o último; no primeiro pedido da sessão,
sem projeto definido, ela pergunta.

O nome dito é resolvido contra a lista de projetos conhecidos. Nome que não
resolve para exatamente um projeto faz ela perguntar em vez de escolher.

## Reaproveitamento do que já existe

| Peça existente | Uso no laço ao vivo |
|---|---|
| `falar.py` | Síntese em fluxo da resposta do agente. Já corta o texto em pedaços e começa a falar no primeiro |
| `atalhos.ps1` | Ganha `F6`. A infraestrutura de atalho global e processo residente já está de pé e testada |
| Arquivo de controle da fala | Pausa e cancelamento durante a fala ao vivo |
| Fila e caixa de entrada | Conclusão de ação longa entra na fila; `Ctrl+Alt+L` já a lê, com a origem certa |
| Bipe | Sinal de conclusão. Dois curtos para distinguir do resumo assíncrono |
| `config.json` | Ganha uma seção `aovivo` |

## Consequência estrutural: uma segunda suíte de testes

As duas bibliotecas necessárias — SDK de fala da Azure e Claude Agent SDK — são
Python. O laço ao vivo é, portanto, Python.

O repositório hoje testa em PowerShell com Pester: **126 testes, todos passando**
na linha de base de 20/08/2026. O laço ao vivo adiciona uma suíte `pytest`. As
duas convivem; o comando de verificação passa a ser dois comandos.

Isso é uma mudança estrutural real do projeto, registrada aqui deliberadamente e
não escondida num rodapé.

## Falhas e como cada uma se anuncia

Nenhuma pode falhar em silêncio.

| O que quebra | Como o usuário percebe |
|---|---|
| Sem internet, ou chave inválida | Bipe de erro e o motivo no painel |
| Apertou e não falou | Ela ignora, sem custo e sem resposta |
| Cota da Azure esgotada | Painel diz, com a palavra "cota" |
| Comando falhou no projeto | Ela fala **uma frase** com o erro, não o despejo técnico |
| Processo ao vivo morreu | `F6` avisa em vez de não fazer nada — a lição que o projeto já aprendeu com o atalho |
| Windows recusou registrar `F6` | Motivo no log, como já acontece com as outras teclas |

## Estratégia de teste

O que importa: **a parte perigosa é a que não precisa de microfone.** Portaria e
interpretação do "sim" são funções puras — entra texto, sai decisão. Escritas com
teste primeiro.

Cobertura automatizada:

- Tabela de ferramenta mais argumento para faixa esperada, com os destrutivos um
  por um.
- **O caso do desconhecido:** ferramenta inventada precisa cair no teclado.
- **A assimetria do sim:** "pode" aprova; "pode não", "poder", "pode ser", vazio,
  ruído e confiança baixa **todos** recusam.
- Extração do nome do projeto da frase falada, incluindo nome ambíguo.
- Máquina de estados do `F6`, inclusive apertar durante a fala.
- Conclusão de ação longa entra na fila com a origem certa e **não** dispara fala.
- **A janela de conversa fecha ao iniciar uma ação longa** — o microfone não fica
  aberto durante uma execução de minutos.
- A janela de autorização fecha na resposta, e fecha sozinha no fim dos 10 s.
- Janela de conversa configurada como zero produz turno único.

Verificação manual, pelo usuário, porque não há como automatizar:

- Microfone e escolha de dispositivo de entrada.
- Palavra de ativação: acerta o nome, e não dispara com conversa ao redor.
- Qualidade da transcrição do português falado do jeito que o usuário fala.

## Riscos conhecidos

| Risco | Gravidade | Mitigação |
|---|---|---|
| A latência real ficar muito acima de 4 s e a conversa soar morta | Alta | Medir antes de construir. É o primeiro item do plano |
| O agente da Clarisse **não vê** a conversa da sessão do Claude Code do usuário | Alta | Consequência inevitável da arquitetura de agente próprio. Registrado para não frustrar: "continua o que a gente estava fazendo" não vai funcionar |
| Custo por turno: tokens do agente mais minuto de transcrição | Média | Não é proibitivo, mas conversar é mais caro que digitar. Turno único evita o desperdício da conversa sempre aberta |
| Palavra de ativação disparando com conversa ao redor | Média | Modo mãos-livres desligado por padrão; a tecla é o caminho principal |
| A janela de conversa de 20 s mantém o microfone aberto depois de cada resposta — conversa alheia no ambiente vai para a Azure sem o usuário ter apertado nada | Média | Enumeração exaustiva das quatro situações de microfone aberto; janela configurável; zero produz turno único; a janela fecha ao iniciar ação longa |
| `F6` sozinha rouba a tecla de todos os programas | Baixa | Tecla configurável e documentada |
| Um "pode" mal ouvido | Baixa, por construção | A assimetria do sim. Grave nunca aceita voz |
| Segunda suíte de testes divide a verificação do projeto | Baixa | Documentar os dois comandos |

## Verificações pendentes antes de implementar

Itens que eu confirmei existirem, mas cuja forma exata em Python precisa ser
verificada contra a biblioteca instalada, e não assumida:

1. Reconhecimento de palavra de ativação em Python: a documentação da Azure
   confirma que o recurso existe e **roda no dispositivo, offline**, a partir de
   um arquivo de modelo gerado no Speech Studio. Os exemplos que eu li eram em
   C# e iOS. A forma em Python precisa ser confirmada contra o pacote instalado.
2. Nível de confiança da transcrição: a assimetria do sim depende de conseguir
   ler a confiança que a Azure reporta. Precisa ser confirmado qual formato de
   saída expõe isso em Python.
3. Definir a pasta de trabalho do agente por opção do Claude Agent SDK: o
   mecanismo de permissão (`can_use_tool`), o texto parcial
   (`include_partial_messages`) e a retomada de sessão (`resume`) estão
   confirmados na documentação. A opção de pasta de trabalho precisa ser
   confirmada.
4. Custo real por turno, medido, não estimado.

## Pré-requisito que depende do usuário

Criar na Azure um recurso de fala e obter a chave de assinatura, e gerar o modelo
da palavra "Clarisse" no Speech Studio. Isso exige login na conta do usuário e
não pode ser feito por mim.

O plano de implementação começa com um roteiro numerado para isso, dizendo em
que tela clicar e o que deve aparecer quando der certo.
