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

## Abrir único (30/09/2026)

Pedido do usuário: "abre o X" abre o programa instalado, o sistema da empresa no
navegador ou roda o projeto local; quando o nome existe como site e como projeto,
**pergunta**. Sites vêm de `config/sites.json` (apelidos) mais o Dokploy (diário).

| Versão (23 casos) | Acertos pelo nome da ferramenta |
|---|---|
| Sem a lista de sistemas no prompt | 12/20 (casos da época) |
| Lista de sistemas no prompt | 14/20 |
| + campo `onde` "só com a palavra do usuário" | 15/23 |
| + VS Code restrito a "quando falar VS Code" | 14/23 (piora: "abre o vs code" pergunta o projeto) |
| + sem `abrir_aplicativo` | 15/23 |
| + sem `abrir_aplicativo` e `abrir_site` | 16/23, mas "sc360" e "smart anchor" continuam indo ao VS Code |

Ficou a versão sem mudar o VS Code e com todas as ferramentas. Pelo efeito, 19 de 23
fazem o certo: "abre o chrome" e "roda o smart anchor" usam as ferramentas antigas,
que fazem o mesmo; `abrir_site` com nome de sistema abre o endereço da empresa (antes
"sc360" virava sc360.com); `abrir_aplicativo` com nome de sistema abre o site e com
nome de projeto pergunta. Erram: "abre o smart anchor" e "abre o sc360" (VS Code,
porque estão na lista de projetos), "painel de inadimplência" (vira painel-fidc) e
"abre o github" (pergunta).

Pelo agente completo: "abre o omni" → "O omni tem o site no ar e o projeto nesta
máquina. Quer abrir o site ou rodar o projeto local?"; "o site" → abriu.
