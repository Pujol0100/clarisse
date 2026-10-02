# Medição — ferramentas de janela (29/09/2026)

Modelo `gemma4:e4b-it-qat`, temperatura 0, registro e prompt reais da Clarisse.
Uma chamada ao modelo por pedido; a segunda chance do agente (quando ele anuncia "vou…") não entra na conta.

| Versão | Acertos |
|---|---|
| Descrições iniciais, sem regra de pedido curto | 6/19 |
| Mesma coisa, sem as ferramentas de janela | 4/19 (o costume de perguntar já existia) |
| Com a regra "pedido curto já está completo" no prompt | 17/24 |
| Regra + descrições que citam os programas e os atalhos | **19/24** |
| Cutucada quando a resposta termina em "?" (descartada) | 15/24 — o modelo passa a recusar |
| Depois do teste real: casos que citam o programa no atalho (25 casos; programa aceito no `aplicativo` ou no `titulo`) | 19/25, igual em duas rodadas |
| Mesma coisa com a descrição antiga do campo `aplicativo` | 18/25 |

Nenhuma frase de conversa (cumprimento, conta, pergunta geral) passou a chamar ferramenta.

O teste real de 29/09/2026 mostrou que o modelo às vezes manda o programa só no
`titulo` ("salva o rascunho clarisse" → `titulo: "clarisse"`); o atalho passou a
usar o título também quando o `aplicativo` vem vazio.

Erros que sobraram:

- "salva o arquivo no vs code" → chama sem o programa, e o atalho vai para a janela da frente.
- "abre uma aba nova no navegador" → também sem o programa.
- "abre o vs code" → oscila entre abrir e perguntar qual projeto.
- "volta pro terminal" → `abrir_aplicativo`, que abre um terminal novo.
- "digita git status no terminal" → pergunta o projeto, confunde com a ferramenta de git.
- "desfaz isso" → ainda pergunta.
