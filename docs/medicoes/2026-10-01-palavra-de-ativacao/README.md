# Medição: a transcrição que a Clarisse já tem serve para a palavra "Clarisse"?

Data: 01–02/10/2026, em casa. Microfone do notebook (Predator Helios Neo 16 AI), faster-whisper
`small` no processador, `int8`, `language="pt"`, `beam_size=5`, filtro de silêncio ligado — o mesmo
transcritor da Clarisse.

**Resposta: sim, com a dica "Clarisse" e voz em volume normal. 25 de 25 acertos e 1 alarme falso
em 20 frases (o nome "Clarice", que soa igual).**

## Como foi medido

`gravar.py` guiou 50 gravações pela voz da Clarisse (bipe para começar e para acabar):

- 20 × "Clarisse" sozinho, de jeitos diferentes (normal, baixo, alto, rápido, devagar, chamando,
  olhando para o lado, de longe, voz cansada);
- 10 × "Clarisse" seguido de um pedido ("Clarisse, que horas são?");
- 20 frases do dia a dia sem o nome, algumas de som parecido ("Clarice Lispector é uma escritora",
  "A clareza do texto…", "Essa classe…", "A Clara chegou", "Clareia a tela", "A Carla…").

As gravações ficam em `dados/ativacao/`, **fora do git** (é a voz do usuário). `medir.py` transcreve
cada uma sem dica e com a dica `hotwords="Clarisse"` e procura o nome no texto.

## Resultado

| | Sem dica | Com a dica "Clarisse" |
|---|---|---|
| "Clarisse" sozinho (20) | 0 escrito certo; 11 viram "Clarice" | **15** |
| "Clarisse, pedido…" (10) | 0 escrito certo; 8 viram "Clarice" | **10** |
| Frases sem o nome (20), alarme falso | 0 (1 no modo folgado) | **1** ("Clarice Lispector" virou "Clarisse") |
| Tempo por gravação (mediana) | 0,89 s | 0,91 s |

**As 5 falhas com a dica são as 5 primeiras gravações**, todas com a transcrição vazia. O volume
máximo delas mal passa do ruído da casa (pico ~2.700 contra 4.600–5.700 nas seguintes). Sem o
filtro de silêncio, 3 das 5 viram "Clarisse" (com 62–73% de chance de ser silêncio, pelo próprio
Whisper). Fala baixa ou longe do notebook se perde; em volume normal, 25 de 25.

## O que isso diz

- **Sem a dica não serve**: o Whisper escreve "Clarice" (o nome comum). Com a dica, escreve "Clarisse".
- **"Clarice" e "Clarisse" soam iguais**; o alarme falso que sobrou é esse. Raro na rotina de trabalho.
- **Não precisa de detector separado**: a mesma transcrição que já roda serve. E "Clarisse, que horas
  são?" dito de uma vez já traz o pedido junto — não precisa acordar e depois ouvir de novo.
- **Custo**: cada trecho de fala na sala custa ~0,9 s de processador. Com conversa o tempo todo
  perto do notebook, o processador fica ocupado nesse tempo.
- **Falta medir**: escuta contínua de verdade (fala corrida, TV, outras pessoas), que esta medição
  com trechos curtos já recortados não cobre.
