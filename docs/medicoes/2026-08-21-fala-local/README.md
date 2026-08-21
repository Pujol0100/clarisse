# Medição: fala para texto local nesta máquina

Data: 21/08/2026. Máquina: i7-1355U (15 W, 10 núcleos físicos / 12 lógicos),
15,7 GB de RAM, **sem GPU dedicada**. Python 3.14.4.

Responde à pergunta que o design deixou aberta: dá para transcrever português
localmente, sem a nuvem, com latência e precisão aceitáveis?

**Não para transcrever. Sim para acordar.**

## Como refazer

Precisa de um ambiente descartável, fora do projeto:

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install faster-whisper vosk edge-tts jiwer psutil
```

E do modelo de português do Vosk, extraído numa pasta `modelos/` ao lado dos
scripts:

```
https://alphacephei.com/vosk/models/vosk-model-small-pt-0.3.zip
```

Depois, nesta ordem:

| Script | O que faz |
|---|---|
| `gerar_audio.py` | Sintetiza as amostras em pt-BR com a mesma voz da Clarisse |
| `bench.py` | Compara os quatro motores: latência, taxa de erro, memória |
| `threads.py` | Verifica se mais threads derrubam a latência do whisper |
| `ativacao.py` | Palavra de ativação com gramática restrita, e limiar de confiança |
| `ativacao_livre.py` | Palavra de ativação com vocabulário livre |

Os modelos do whisper são baixados sob demanda pelo `faster-whisper`, cerca de
700 MB somando `tiny`, `base` e `small`. O `resultado.json` guarda a corrida de
21/08/2026 para comparação.

## Transcrever a frase

Cinco frases de 3,0 a 5,4 s, voz sintética, `int8`, CPU, busca gulosa. Latência é
a mediana de três execuções quentes.

| Motor | Carga | Latência | Pior | × tempo real | Erro de palavra | RAM |
|---|---|---|---|---|---|---|
| faster-whisper tiny | 6,8 s | **0,64 s** | 0,66 s | 0,15× | 38,5% | 136 MB |
| vosk small pt | 0,4 s | 2,36 s | 3,04 s | 0,56× | 36,5% | 117 MB |
| faster-whisper base | 6,9 s | 1,03 s | 1,49 s | 0,26× | 25,0% | 141 MB |
| faster-whisper small | 16,9 s | 3,08 s | 4,08 s | 0,77× | **13,5%** | 324 MB |

Threads não salvam o `small`: melhor caso 3,08 s com 8 threads; com 2 threads
piora para 5,43 s. O `base` fica entre 1,03 s e 1,60 s.

### O que a taxa de erro esconde

Todos escreveram `clarice` no lugar de `Clarisse` — homófono, e irrelevante,
porque o nome é tratado pela ativação e descartado. Descontando o nome, o `small`
acertou o conteúdo de todas as cinco frases; o único resto foi `omni` → `omin`.

O `base` é outra história. Ele destrói o nome dos projetos, sempre:

```
falado : Clarisse, o que está rolando no omni-api?
base   : clarice o que esta rolando no homem in api
small  : clarice o que esta rolando no omin api

falado : Clarisse, roda os testes do projeto e me avisa quando terminar.
base   : tua a ris rodos testes do projeto e me avisa quando terminar
small  : clarice roda os testes do projeto e me avisa quando terminar
```

O design diz que adivinhar o projeto é falhar em silêncio na pasta errada. Um
motor que ouve `omni-api` e escreve `homem in api` não pode decidir onde agir.

**Conclusão:** local é rápido e errado (`base`, 1,03 s) ou certo e lento
(`small`, 3,08 s). Os dois reprovam. A transcrição fica na Azure, em `pt-BR`,
região `brazilsouth`.

## Acordar quando você chama

Cinco formas de chamar o nome. Doze frases de trabalho que colidem com ele em
português: *clareza, esclarecimento, esclareceu, classificar, esclarecimentos,
claro, Alice*.

| Modo do Vosk | Acordou quando devia | Acordou sem dever | Latência |
|---|---|---|---|
| Gramática restrita a `["clarisse","[unk]"]` | 5/5 | **6/12** | 60 ms |
| Vocabulário livre | 3/5 | **0/12** | 1096 ms (pior 1597 ms) |

### Por que a gramática restrita reprovou

Travada em duas opções, o reconhecedor é **obrigado** a encaixar todo som em
`clarisse` ou em `[unk]`. Não existe "clareza" no vocabulário para explicar o que
ele ouviu, então "clareza" vira "clarisse".

Cortar por confiança não resolve, porque as distribuições estão **invertidas**:

```
falso positivo  conf 1.00  "Preciso revisar a clareza desse texto"
falso positivo  conf 1.00  "Ela esclareceu tudo na reuniao"
falso positivo  conf 1.00  "O cliente pediu esclarecimentos"
acerto real     conf 0.76  "Clarisse."
```

Nenhum limiar separa 0,76 de 1,00 na direção certa. Subir para 0,95 derruba o
acerto para 3/5 e ainda deixa 5/12 falsos passarem.

Com o vocabulário inteiro, o mesmo modelo escreve "clareza", "esclareceu" e
"classificar" corretamente, e nunca acorda. As duas perdas do modo livre foram as
falas mais curtas: o nome sozinho, e "Clarisse, escuta".

**Conclusão:** vocabulário livre, e a tecla `F6` como forma garantida de chamar.

## Ganho lateral

Como a detecção do nome é local e não fala com nuvem nenhuma, a afirmação do
design — *"nenhum áudio sai antes dela ouvir o nome"* — deixa de ser intenção e
passa a ser propriedade do desenho. E nada obriga mais o recurso da Azure a viver
fora do Brasil.

## O que esta medição **não** provou

1. **Voz real.** Tudo aqui é voz sintética limpa. Fala real tem hesitação, ruído
   de teclado e acústica de sala. A precisão vai cair.
2. **Falsos por hora.** Doze negativos não medem uma jornada. A métrica que
   decide é quantas vezes ela acorda sozinha em uma hora de trabalho.
3. **O nome curto que escapou.** Testar um chamado de duas palavras antes de
   aceitar que a tecla cubra esse caso.
4. **Consumo real da cota de cinco horas por mês.**
5. **CPU com dez sessões abertas.** O reconhecimento contínuo foi medido sozinho,
   não competindo pelos mesmos 15 W.

Cada item acima é tarefa do Plano B, antes de fechar o Ouvinte.
