# Medição: qual modelo local escolhe a ferramenta certa

Data: 28/09/2026. Máquina: Predator Helios Neo 16 AI, RTX 5070 Laptop (8 GB de
VRAM, 7,4 GB livres para o Ollama), 30 GB de RAM, Ubuntu 26.04. Ollama 0.34.4.

Pergunta: um modelo que cabe nesta placa entende pedidos falados em português e
escolhe a ferramenta certa, rápido o bastante para voz?

**Resposta: sim — `gemma4:e4b-it-qat`, 29 de 32 pedidos, mediana de 0,27 s.**

## Como foi medido

`medir_roteador.py`: 17 ferramentas no formato do Ollama, 32 pedidos em português
com a ferramenta esperada e trechos que os argumentos devem conter. Inclui erro
real de transcrição ("homem in api" no lugar de `omni-api`) e cinco pedidos que
**não** devem chamar ferramenta. `think: false`, temperatura 0, contexto 8192.
Cada modelo rodou uma vez; a primeira chamada (carga do modelo) fica fora da conta.

Os nomes de pessoas nos pedidos foram trocados por fictícios antes de versionar, e
o prompt diz "usuário" onde dizia o nome dele; uma nova rodada pode variar em um
pedido por isso.

## Resultado

Primeira rodada, prompt base:

| Modelo | Origem | Acertos | Mediana | Pior | Memória | Onde roda |
|---|---|---|---|---|---|---|
| qwen3.5:4b | Alibaba | 31 | 0,72 s | 1,11 s | 3,3 GB | 100% GPU |
| qwen3.5:9b | Alibaba | 30 | 0,89 s | 1,38 s | 5,6 GB | 100% GPU |
| gemma4:12b-it-qat | Google | 30 | 1,92 s | 4,17 s | 7,7 GB | 15% CPU |
| granite4.1:8b | IBM | 28 | 0,48 s | 1,67 s | 6,6 GB | 100% GPU |
| ministral-3:8b | Mistral | 28 | 0,43 s | 2,10 s | 7,4 GB | 18% CPU |
| llama3.1:8b | Meta | 27 | 0,39 s | 0,74 s | 5,8 GB | 100% GPU |
| gemma4:e4b-it-qat | Google | 26 | 0,36 s | 2,40 s | 3,1 GB | 100% GPU |
| llama3.2:3b | Meta | 21 | 0,17 s | 0,47 s | 3,1 GB | 100% GPU |
| phi4-mini | Microsoft | 5 | 0,28 s | 3,31 s | 3,7 GB | 100% GPU |

Os Qwen estão vetados pela regra da empresa (sem IA chinesa); ficam como régua.

Segunda rodada, com a regra "não peça confirmação nem detalhes: chame a
ferramenta direto; o sistema confirma sozinho as ações arriscadas; perguntas de
conhecimento geral você responde direto":

| Modelo | Acertos | Mediana | Pior |
|---|---|---|---|
| **gemma4:e4b-it-qat** | **29** | **0,27 s** | 0,55 s |
| llama3.1:8b | 28 | 0,38 s | 0,84 s |
| granite4.1:8b | 28 | 0,48 s | 1,48 s |

## O que os erros ensinam

- **O Gemma e4b erra perguntando** ("Qual site do GitHub você gostaria de
  abrir?"). O Llama e o Granite erram **agindo**: "obrigado" virou `parar`,
  "revisar o PR" virou `git log`. Para quem executa ações, errar perguntando é o
  modo de falha seguro.
- **Sem a regra, o Gemma pedia confirmação** em vez de agir. Confirmação é papel
  do sistema, não do modelo.
- **"Para, Clarisse" falhou em quase todos.** Parar não pode depender do modelo.
- **Todos inventam fatos.** O qwen3.5:4b contou que a abelha "voa em sentido
  inverso ao sol"; o qwen3.5:9b respondeu "hoje é 25 de maio de 2024" sem chamar a
  ferramenta de data. O modelo local escolhe a ação; fato vem de ferramenta.
- O gemma4:12b não cabe inteiro nem com contexto de 4096 (15% fica na CPU), e
  numa vez disse "vou abrir o Claude" sem chamar a ferramenta.
- O phi4-mini não emite `tool_calls` no Ollama com este formato de prompt.

## Limites

32 frases escritas por quem fez o teste, uma rodada por modelo. Diferença de um ou
dois acertos é empate. O conjunto deve crescer com frases reais do uso.

## Como refazer

```
ollama pull gemma4:e4b-it-qat
python3 medir_roteador.py gemma4:e4b-it-qat
REGRA_EXTRA="..." SUFIXO=_regra python3 medir_roteador.py gemma4:e4b-it-qat
```

Só biblioteca padrão do Python; o Ollama precisa estar ouvindo em
`127.0.0.1:11434`.
