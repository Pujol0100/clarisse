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
