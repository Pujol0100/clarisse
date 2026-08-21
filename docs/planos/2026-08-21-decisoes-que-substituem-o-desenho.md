# Decisões de 21/08/2026 que substituem partes do desenho

O desenho de 20/08 (`2026-08-20-clarisse-ao-vivo-design.md`) foi escrito antes de
qualquer medição. Três coisas dele caíram hoje. Este documento é a fonte da
verdade para o Plano B; onde ele contradiz o desenho, ele ganha.

## 1. A palavra de ativação sai do projeto

**Antes:** duas formas de ativar — tecla `F6` **e** a palavra "Clarisse".
Reafirmado pelo usuário depois de eu argumentar contra.

**Agora:** só a tecla. Aperta liga, aperta desliga.

**Por quê:** a Azure não faz palavra de ativação em português; o Porcupine, que
fazia, encerrou a camada gratuita em 30/06/2026; o openWakeWord declara suportar
só inglês; e o Vosk, medido hoje, ou dá 6 falsos positivos em 12 (gramática
restrita) ou perde o nome dito sozinho (vocabulário livre). Ver
`docs/medicoes/2026-08-21-fala-local/`.

**Consequência boa:** cai a dependência do Vosk, cai o problema de falso
positivo, cai uma peça inteira da arquitetura (o Ouvinte fica muito menor).

## 2. Duas teclas, com papéis distintos

| Tecla | O que faz |
|---|---|
| `F6` | Aperta, fala, aperta. O texto transcrito é **digitado na janela em foco**. Você revisa e aperta Enter |
| `F7` | A Clarisse fala o resumo. Primeiro o projeto com quem você falou por último no `F6`; se não houver nada lá, o mais recente da fila; aperta de novo e pula para o próximo |

**Por que o `F6` digita em vez de enviar:** a transcrição erra nome de projeto.
Medido hoje: `omni-api` virou `homem in api` no motor rápido, todas as vezes. Ver
errado antes de enviar evita agir na pasta errada — que é o modo de falha que o
desenho mais teme.

**Por que o `F7` não lê a aba em foco:** foi o pedido literal do usuário, e foi
descartado por medição. Motivos, em ordem de peso:

1. As sessões são **abas de uma única janela** do Windows Terminal. Não existe
   API pública que diga qual `claude.exe` está em qual aba.
2. O título da aba é escrito pela aplicação, não configurado — não há `tabTitle`
   nem `suppressApplicationTitle` no `settings.json` do terminal. Hoje ele dizia
   "Omni"; nada garante que amanhã não diga o nome de uma tarefa.
3. **No momento da medição, a janela em foco era um navegador**, não um terminal.
   O `F7` é apertado justamente quando o usuário saiu do terminal. "O terminal em
   que estou" frequentemente não existe na hora do aperto.

Vincular ao último `F6` usa um dado que o usuário mesmo criou, em vez de inferir
do sistema operacional. Se depois faltar o vínculo com a aba, ele entra como
refinamento — nunca como fundação.

## 3. A regra do áudio automático

**Antes:** "voz que dispara sozinha atropela quem está no meio de outra coisa",
mas o hook `Notification` falava sozinho de propósito, com comentário no código
justificando.

**Agora, a regra:**

> Áudio toca sozinho **apenas dentro de um turno que o usuário abriu**. Fora
> dele, bipa e espera ser pedido.

O `Notification` não abre turno — ele chega quando uma sessão qualquer trava, na
hora dela. Com quatro sessões abertas, isso virou a Clarisse anunciando em voz
alta que um terminal precisa de atenção, no meio de uma reunião. **Corrigido e
instalado em 21/08/2026:** ele agora enfileira com o nome do projeto e bipa.

O `F6` **abre** turno. Então a resposta imediata da Clarisse — o "vou fazer X" —
toca na hora, e está certo tocar: o usuário acabou de falar e está esperando.

## O que isso exige que o Plano B construa

1. **Dois canais de fala por resposta**, não um. Hoje existe um resumo, no fim.
   Passa a existir o aviso imediato ("vou fazer X", toca na hora, dentro do
   turno) e o resultado (espera o `F7`).
2. **Marcador de turno aberto**, derivado do dado e não de qual processo está
   rodando: o `F6` registra qual projeto recebeu o ditado; o aviso escrito
   enquanto o marcador está de pé toca na hora e limpa o marcador.
3. **Ditado para a janela em foco**, com revisão antes do Enter.
4. **`F7` sem menu**, com a ordem de precedência da tabela acima.

## Ainda em aberto

- **Azure ou local para a transcrição.** Com turnos e pausa explícita, os 3,08 s
  do `faster-whisper small` deixam de ser proibitivos, e ele roda a 0,77× o tempo
  real — mais rápido do que se fala. Se a transcrição em fluxo confirmar isso com
  voz real, a Azure sai do projeto inteiro: sem cartão, sem cota, sem nuvem.
  **Não medido.** É a primeira tarefa do Plano B.
- **Qual tecla exatamente.** `F6` e `F7` podem colidir com outros programas. O
  desenho já previu que a tecla seja configurável.
