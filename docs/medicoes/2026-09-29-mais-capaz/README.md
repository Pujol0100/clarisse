# Medição — plano "Clarisse mais capaz" (29/09/2026)

Modelo `gemma4:e4b-it-qat`, temperatura 0, registro e prompt reais.
`medir.py` faz uma chamada ao modelo por pedido (sem a segunda chance do agente).

## Tarefa 2 — participantes no compromisso

| Versão | Acertos | Observação |
|---|---|---|
| Antes do campo `participantes` | 4/8 | Os três pedidos com pessoa ficam sem convidado; "boleto" só anuncia |
| Com `participantes` | 6/8 | Os três com pessoa corretos; "boleto" e "dentista" só anunciam ("Vou criar…") |

Pelo agente completo (com a segunda chance quando o modelo anuncia sem agir), os
três casos chegaram à confirmação certa, sem responder "sim":

- "marca dentista quinta às 14h" → "Vou criar na sua agenda: Dentista, próxima quinta-feira às 14h. Confirma?"
- "me lembra de pagar o boleto sexta às nove" → "… Pagar boleto, sexta às nove. Confirma?"
- "cria uma reunião amanhã às 10 com o Bruno Santos" → "… Reunião, amanhã às 10h, convidando Bruno Santos. Confirma?"

## Tarefa 3 — abrir arquivo

| Versão | Pedidos de arquivo | Total |
|---|---|---|
| Descrição "procura um arquivo pelo nome" | 3/5 ("planilha" e "pdf" recusados: o modelo achou que a ferramenta não abria esse tipo) | 9/13 |
| Descrição que cita planilha, PDF, documento, imagem | 5/5 | 9/13 |

Efeito colateral: com a ferramenta nova, o modelo passou a anunciar ("Vou criar…")
em vez de chamar `criar_compromisso` em 3 pedidos. Pelo agente completo, 3 de 4
chegaram à confirmação; o quarto ("criar um evento hoje às 18 horas e colocar o
Bruno Santos na reunião") pergunta o título. É o limite do modelo pequeno que a
fase 2 (Claude planejando) ataca.

Busca real na pasta do usuário: 0,05 s para uns 9.600 arquivos. "readme do smart
anchor" acha 39 (várias cópias do projeto e o espelho do vault): ela lista os 3
mais recentes e pede um pedaço a mais do nome.

## Tarefa 4 — rodar aplicação local

- Gemma: 5/5 ("roda o smart anchor", "consegue abrir o smart-anchor local",
  "rodar o smart-anchor no Google Chrome", "sobe o omni app", "inicia o sc360
  local"), sem confundir com "abre o projeto no vs code".
- Primeira regra (varrer todas as variáveis de banco do `.env`) recusava o
  smart-anchor: o `.env` do backend tem `PD_DB_PORT` e `SYNC_URL_ORIGEM` de scripts
  de sincronização apontando para produção. Trocada por olhar só as variáveis que
  o servidor de desenvolvimento usa por convenção (`DATABASE_URL`, `DB_HOST`…).
- Teste real no smart-anchor: os dois terminais falharam com `nest: not found`.
  **Nenhum projeto em PROGRAMASSMART tem `node_modules` nesta máquina Linux.** A
  ferramenta passou a dizer "falta rodar npm install em: backend, frontend" em vez
  de abrir terminal que morre.
- Caminho completo provado com um projeto de teste fora das pastas do usuário:
  terminal aberto, site no ar em 2 s, navegador aberto, aviso falado.

## Tarefa 5 — perguntas de conhecimento

| Versão | Empresa, pessoa, cotação, jogo | Perguntas simples |
|---|---|---|
| Antes | 0/4 (responde "não tenho essa informação") | 3/3 |
| Regra no prompt + descrição | 2/4 | 3/3 |
| + garantia (modelo que só fala em pesquisar ou no Claude tem a pergunta levada ao Claude), pelo agente completo | 3/3 testadas | 3/3 |

O Claude tinha a busca na web liberada e não usava: respondia sobre a Smart Compass
só com o que sabia das configurações. Com a instrução explícita de pesquisar,
respondeu com o site oficial em 25 s.
