# A área de transferência não serve para o ditado

Data: 26/08/2026
Máquina: Windows 11, PowerShell 5.1, OneDrive ativo (3 processos), ~10 sessões do
Claude Code abertas.

## O que esta medição derrubou

**Colar por área de transferência, que era o desenho da Tarefa 7.** O plano dizia
`Set-Clipboard` mais `Ctrl+V`, com o conteúdo anterior restaurado depois. Não
funciona nesta máquina.

### Primeiro sintoma: falha calada, com perda

Escrevendo e restaurando em sequência, 25 idas:

| | |
|---|---|
| voltas | 25 |
| voltas em que a área terminou **vazia** | 2 |

O `Set-Clipboard` não lançou erro em nenhuma delas. O usuário perderia o que
tinha copiado, sem nenhum aviso.

Isso levou a uma primeira correção — escrever, **conferir lendo de volta**, e
tentar de novo — que passou nos testes rodados isoladamente.

### Segundo sintoma: indisponibilidade total

Com a suíte inteira rodando, a mesma correção falhou. Não foi lentidão: as oito
tentativas estouraram, cada teste levou de 6 a 28 segundos, e **a leitura também
estourou**:

```
ExternalException: A operação de Área de Transferência solicitada
não foi bem-sucedida.
```

Testado de novo três vezes com meio segundo de intervalo, fora do Pester: falhou
nas três. Não é um piscar — é uma condição que se instala e fica.

## A consequência para o desenho

**O ditado passou a digitar por `SendInput` com `KEYEVENTF_UNICODE`.** Ele injeta
o código do caractere direto na fila de entrada, sem passar pela área de
transferência.

Isso resolve, de uma vez, o motivo pelo qual o plano tinha escolhido colar: o
`SendKeys` perde acento porque manda *tecla*; o `KEYEVENTF_UNICODE` manda
*caractere*. Não há mais nada emprestado do usuário para devolver.

**A contingência do Handy não resolveria isto.** Ele também cola pela área de
transferência, então herdaria a mesma falha.

## O que isto mudou nos testes

Os testes da colagem foram reescritos. A versão anterior batia na área de
transferência de verdade e por isso passava ou falhava conforme o que mais
estivesse aberto — o mesmo erro que a medição de threads de 25/08 cometeu, agora
dentro da suíte.

Hoje o envio da tecla entra por parâmetro e a suíte nunca dispara tecla
sintética: rodar os testes com uma janela em foco digitaria nela.

## O que falta verificar, e só o usuário pode

Que a tecla chega mesmo na janela em foco. Nenhum teste automático pode fazer
isso sem digitar na janela de quem está rodando a suíte.
