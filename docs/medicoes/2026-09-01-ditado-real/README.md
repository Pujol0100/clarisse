# O ditado no uso real

Data de abertura: 01/09/2026
Máquina: Windows 11, PowerShell 5.1, Python 3.14, `faster-whisper` modelo `small`
em `int8`, em condição normal de trabalho (~10 sessões do Claude Code abertas).

**Status: coletando.** Este documento foi escrito antes de existir qualquer
número, e o critério abaixo não pode ser ajustado depois de ver o resultado.

## Por que esta medição existe

O ditado por voz está de pé nesta máquina desde 26/08/2026 e é usado todo dia.
Não havia nenhum número sobre ele em uso real — só o de laboratório, de 26/08:
**10,6% de erro por palavra** nas oito gravações de voz gravadas em 21/08.

O que decide o desenho do Agente não é o número de laboratório. É quanto o
ditado erra quando é o usuário falando no meio do trabalho, com pressa, com
nome de projeto e com o barulho que a máquina faz.

## O que foi tentado antes, e por que não deu

**Reconstruir a semana de 26/08 a 01/09 é impossível.** Verificado em 01/09: o
`clarisse.log` tem sete linhas de Ouvinte, todas de "servidor de pé". O
`texto.txt` com a transcrição é apagado pelo `Wait-DitadoPronto` no instante em
que o texto é digitado na janela, e nada mais foi anotado.

O texto **enviado** existe, guardado pelo Claude Code nas transcrições de
sessão. Mas sem o texto **bruto** ao lado não há par, e sem par não há conta.

Daí o diário: instrumentar primeiro, coletar depois.

## O que esta medição mede

**Taxa de correção:** quanto do texto ditado o usuário mexeu antes de apertar
Enter. Isso **não é** taxa de erro do motor, e confundir os dois repetiria o
erro de leitura que a medição de 26/08 teve que corrigir.

| A diferença | Efeito no número |
|---|---|
| O usuário aceita uma palavra errada e envia assim mesmo | O número **subestima** o erro |
| O usuário reescreve porque mudou de ideia | O número **superestima** o erro |
| O usuário acrescenta uma frase digitada no fim | Excluído da conta pelo analisador |

O terceiro caso é separado mecanicamente: o `script_de_edicao` conta troca,
remoção e acréscimo em separado, e só troca e remoção entram na taxa. Os dois
primeiros não têm como ser separados sem o usuário narrar o que fez, e isso não
será pedido. **A taxa de correção é um indicador, não uma verdade.**

Junto dela saem: latência da transcrição, tempo de revisão, taxa de abandono e
as palavras que mais foram trocadas.

## Critério de decisão

Escrito em 01/09/2026, antes de qualquer coleta. Ele decide **o desenho do
Agente**, não se ele existe.

| Medida | Faixa | O que decide |
|---|---|---|
| Correção mediana | ≤ 5% | Autorização falada vale até para ação que altera arquivo, com a Clarisse repetindo o entendido antes |
| | 5% a 20% | Voz autoriza só o que não altera nada. Alterar exige tecla |
| | > 20% | O Agente não recebe comando por voz; o ditado segue sendo entrada de texto revisada |
| Ditados abandonados | > 15% | Reprova comando por voz em qualquer faixa de correção |
| Latência p95 | > 8 s | O laço conversacional não fecha; o Agente precisa responder em pedaços |
| Revisão mediana | > 15 s | Nenhuma autorização falada se sustenta em cima disso |

**Amostra mínima: 40 pares completos.** Não é "uma semana": uma semana pode dar
5 ou 300.

## Como coletar

1. Instalar a versão com o diário (`instalar.ps1`).
2. Pôr `"diario": true` no bloco `ouvinte` do `~/.claude/clarisse/config.json`.
3. Reiniciar o escutador: `/clarisse atalhos off` e `/clarisse atalhos on`.
4. Trabalhar normalmente. `/clarisse status` mostra a contagem de linhas.
5. Com 80 linhas ou mais (40 pares), rodar `analisar.py`.

## Como o diário é escrito

Duas linhas por ditado, unidas pelo `id`:

```json
{"tipo":"ditado","id":"1756...-13860","quando":"...","bruto":"...","segundos_audio":4.2,"segundos_transcricao":3.1}
{"tipo":"enviado","id":"1756...-13860","quando":"...","projeto":"omni-api","enviado":"...","segundos_ate_enviar":18}
```

A primeira é escrita pelo modo `ditar`, a segunda pelo hook `UserPromptSubmit`.
Ditado sem `enviado` correspondente é ditado abandonado, e conta como tal.

O diário nasce desligado, guarda no máximo 300 linhas e nunca é lido por nenhum
caminho de fala — ele não vira áudio e não sai da máquina.

## Resultado

*(a preencher depois da coleta, com o `resultado.json` ao lado)*

## O que isto decidiu

*(a preencher depois da coleta, segundo a tabela de critério acima)*
