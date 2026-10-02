#!/usr/bin/env bash
# Liga ou desliga o microfone da Clarisse. Feito para ser chamado por um atalho de teclado do GNOME.
set -euo pipefail

porta="${CLARISSE_PORTA:-8765}"
chave_arquivo="$HOME/.config/clarisse/chave"

if [[ ! -r "$chave_arquivo" ]]; then
  notify-send "Clarisse" "Ela não está ligada. Abra a Clarisse primeiro." 2>/dev/null || true
  exit 1
fi

curl --silent --fail --ipv4 --max-time 3 \
  -X POST \
  -H "X-Clarisse-Chave: $(cat "$chave_arquivo")" \
  "http://127.0.0.1:${porta}/api/escutar" >/dev/null \
  || notify-send "Clarisse" "Ela não respondeu. Confira se está ligada." 2>/dev/null || true
