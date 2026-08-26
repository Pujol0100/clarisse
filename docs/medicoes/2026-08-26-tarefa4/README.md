# A dica montada da máquina, verificada com o código que vai rodar

Data: 26/08/2026
Máquina: a mesma de 25/08, em condição normal de trabalho (~10 sessões do Claude
Code abertas). `faster-whisper` 1.2.1, modelo `small`, `int8`, threads na escolha
da biblioteca.

Esta é a verificação de fronteira da Tarefa 4. Ao contrário das medições
anteriores, ela chama **o código instalado** — `clarisse.ouvinte.motor.transcrever`
e `clarisse.ouvinte.dica.montar_dica` — e não uma cópia escrita no script.

## O que esta medição decidiu

**A dica montada dos projetos da máquina fica.** Ela é a melhor das três
configurações, e por uma margem que não cabe no ruído.

| dica | erro médio | pior frase | espera mediana |
|---|---|---|---|
| sem dica nenhuma | 54,4% | 171,4% | 4,84 s |
| **dos projetos da máquina** | **10,6%** | **37,5%** | 4,59 s |
| escrita à mão, a de 21/08 | 28,7% | 171,4% | 4,53 s |

O que sustenta a conclusão não é a média: é a comparação frase a frase. A dica da
máquina **empata ou ganha em sete das oito frases**, e a única em que perde
(`omni`, 37,5% contra 25,0%) fica longe de qualquer catástrofe.

Script: `comparar_dica.py`. Resultado: `resultado_dica.json`.

### O nome dela só sai certo com a dica

Sem dica, "Clarisse" virou **"Clarice"** nas oito frases, sem exceção. Com
qualquer uma das duas dicas — as duas terminam com `Clarisse.` — o nome sai certo
sempre. É o efeito mais consistente de toda a medição.

## O erro de leitura que esta medição corrigiu

A primeira passada (`verificar.py`, uma configuração só, sem intercalar) deu
**26,3% de erro médio** e levou à conclusão de que a dica da máquina tinha
reprovado, por ter nomes ruins dentro (`PROGRAMASSMART`, `meusProgramas`,
`conciliacao` e `Conciliacao` duplicados na caixa).

**Estava errado.** A frase `conciliacao` deu 114,3% naquela passada e 14,3% na
medição intercalada, **com a mesma configuração e o mesmo áudio**. A diferença
inteira era ruído da máquina.

É a lição de 25/08 aplicada à risca: nesta máquina, configuração medida em
sequência não se compara. O `comparar_dica.py` inverte a ordem das configurações
a cada frase — corrigindo, de passagem, a falha que o script de 25/08 tinha, onde
a primeira configuração de cada rodada sempre pagava o custo frio.

## O que continua sem resposta

**A latência.** A espera mediana ficou em ~4,6 s, contra os 3,21 s de 22/08 e os
6 s a 116 s de 25/08. Continua sendo propriedade do que mais está rodando na
máquina, não do desenho. Nada aqui muda isso.

**A duplicata na caixa.** `conciliacao` e `Conciliacao` ocupam duas das doze vagas
da dica. Não atrapalhou o suficiente para aparecer nos números, e mexer nisso sem
medição seria adivinhação — mas é desperdício conhecido de espaço na dica.
