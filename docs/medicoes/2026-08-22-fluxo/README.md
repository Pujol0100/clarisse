# Medição: transcrição em fluxo

Data: 22/08/2026. Mesma máquina de 21/08 (i7-1355U, 15 W, sem GPU), mesmas oito
gravações da voz real, mesmo motor (`faster-whisper small`, `int8`, 8 threads,
busca gulosa), mesma dica, mesma normalização. Só a estratégia de corte muda.

Responde à pergunta que o Plano B tinha como primeira tarefa: **se o motor
transcrever enquanto o usuário ainda fala, a espera de 2,74 s cai para menos de
1 s?**

**Não. Ela dobra.** A aposta de 21/08 estava errada, e a razão é estrutural: o
custo do `faster-whisper` é **por chamada**, não por segundo de áudio. Cortar a
fala em três pedaços não divide o trabalho em três — multiplica por três.

**A transcrição em fluxo sai do projeto.** O Ouvinte transcreve em bloco.

## Como refazer

Ambiente descartável, fora do projeto:

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install faster-whisper jiwer numpy
```

As gravações da voz real ficam em `~/.claude/clarisse/medicoes/voz_real/` (não
versionadas: é a voz do usuário). Depois, nesta ordem:

| Script | O que responde |
|---|---|
| `medir_fluxo.py` | Cinco estratégias de corte: espera, erro, trabalho de CPU |
| `custo_por_duracao.py` | O custo cresce com a duração do áudio? |
| `aquecimento.py` | A ordem de execução enviesou a comparação? |

A lógica de corte é código de produção, com testes: `clarisse/ouvinte/cortador.py`
e `tests/fluxo/test_cortador.py` (10 testes, `python -m pytest tests/fluxo`).

## As cinco estratégias

"Espera" continua sendo a única métrica que o usuário sente: o tempo entre soltar
a tecla e o texto estar pronto.

| Estratégia | Espera mediana | Pior espera | Erro de palavra | Trabalho de CPU | Trechos |
|---|---|---|---|---|---|
| **bloco (como 21/08)** | **3,21 s** | **3,25 s** | **9,2%** | **25,3 s** | 1 |
| silêncio 400 ms | 3,00 s | 6,83 s | 24,6% | 38,3 s | 1 |
| tempo 2,0 s | 6,48 s | 7,93 s | 29,2% | 70,3 s | 2 |
| tempo 2,0 s + contexto | 5,85 s | 8,77 s | 52,3% | 71,2 s | 2 |
| tempo 1,5 s | 15,30 s | 20,71 s | 44,6% | 146,2 s | 3 |

O bloco ganha em tudo que importa. A única estratégia que empata na mediana
— silêncio 400 ms — o faz porque **quase nunca corta**: a mediana de trechos é 1.
Frase de trabalho tem 4 s e não tem pausa no meio. Quando ela corta, a espera vai
a 6,83 s e o erro quase triplica.

## Por que cortar piora: o custo é por chamada

Transcrevendo pedaços de tamanho crescente do **mesmo** áudio, na mesma execução:

| Trecho | Custo mediano | Custo por segundo de áudio |
|---|---|---|
| 0,5 s | 6,17 s | 12,33 s |
| 1,0 s | 6,47 s | 6,47 s |
| 2,0 s | 6,02 s | 3,01 s |
| 3,0 s | 6,57 s | 2,19 s |
| 4,0 s | 6,69 s | 1,67 s |
| 5,0 s | 6,45 s | 1,29 s |

A curva é horizontal. **Transcrever meio segundo custa o mesmo que transcrever
cinco.** O whisper preenche a entrada até 30 s e roda o codificador sobre o
espectrograma inteiro; o que varia com o texto é só a decodificação, que é a
parte barata.

Daí a conclusão em uma linha: **N pedaços custam N × o preço de um.** O motor fica
ocupado moendo os pedaços do começo, e o último pedaço — o único que decide a
espera — entra numa fila que a própria estratégia criou.

### O que isso faz com a "folga" de 21/08

O documento de 21/08 registrou que o `small` roda a 0,66× o tempo real e chamou
isso de folga: *"processa mais rápido do que se fala"*. A medição de hoje mostra
que essa folga **não é aproveitável**, porque ela não é uma taxa. Os 0,66× são a
razão entre um custo praticamente fixo (~3 s nesta máquina) e a duração daquela
frase específica. Falar mais tempo melhora a razão; cortar em pedaços menores não
melhora nada, porque o custo não acompanha o corte para baixo.

## O contexto no `initial_prompt` é veneno

A ideia era compensar a perda de contexto do corte alimentando o motor com o texto
já transcrito. Ela piorou o erro de 29,2% para **52,3%**, e o modo de falha é o
pior possível — repetição em laço:

```
esperado : Clarisse, o que está rolando no omni-api?
saída    : clarisse clarisse clarisse clarisse clarisse

esperado : Clarisse, me conta o que aconteceu com o compliance-app
saída    : clarisse me conta o que aconteceu com o compliance app
           o que aconteceu com o compliance app
```

A dica de vocabulário funciona porque é **estável** entre chamadas: os nomes dos
projetos não mudam. Texto recém-transcrito é instável, e o modelo o trata como
algo a continuar — então ele continua, inventando. **A dica é para vocabulário
fixo, nunca para contexto móvel.**

## A ameaça que eu testei antes de concluir

As estratégias foram medidas em sequência, na mesma máquina de 15 W. Se o
processador afunilasse por calor, as últimas pareceriam piores sem serem piores, e
a comparação inteira desandaria.

Medido: o custo **cai** com o uso, não sobe.

| Momento | Custo da mesma frase |
|---|---|
| frio | 6,65 s |
| depois de 8 passadas | 4,42 s (−34%) |
| depois de 16 passadas | 4,30 s (−35%) |
| depois de 24 passadas | 4,18 s (−37%) |
| depois de 32 passadas | 4,01 s (−40%) |

O viés existe e está **a favor do fluxo**: o bloco foi medido primeiro, frio, no
pior momento possível, e ainda assim ganhou. A conclusão não depende da ordem.

De brinde, isso explica por que o mesmo motor apareceu a 2,74 s em 21/08, a 3,21 s
no primeiro teste de hoje e a 6,65 s no teste frio: **esta máquina varia muito**.
Comparar dois números medidos em execuções diferentes não vale; só a mesma
execução compara.

## O veredito

**Bloco, e a espera de ~3 s é o piso deste motor nesta máquina.** Não existe
arranjo de cortes que a derrube — o custo por chamada é a parede.

Se um dia 3 s virar inaceitável, a saída não é cortar melhor: é **trocar de
família de motor**. Modelos de streaming de verdade (transducer, como o Parakeet
TDT ou o Nemotron streaming, servidos por `sherpa-onnx`) têm custo proporcional ao
áudio e foram desenhados para emitir texto durante a fala. Isso é troca de
arquitetura, não ajuste — e tem um risco conhecido: o Parakeet foi treinado em
português europeu, não brasileiro.

## O que esta medição não provou

1. **Motor transducer com esta voz.** A alternativa arquitetural não foi medida.
   Nem a precisão em pt-BR, nem a espera real.
2. **Microfone embutido do notebook.** Tudo continua sendo headset Bluetooth.
3. **Ruído de fundo real.**
4. **CPU competindo com as dez sessões abertas.** Pior: hoje sabemos que a máquina
   varia 40% sozinha, então essa medição precisa ser feita com carga controlada.
5. **Frases longas.** As oito gravações têm de 3,4 s a 5,1 s. Uma fala de 30 s
   estoura a janela do whisper e volta a ser um problema de corte — aí o corte por
   silêncio deixa de ser inútil e passa a ser necessário.
