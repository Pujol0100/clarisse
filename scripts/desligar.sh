#!/usr/bin/env bash
# Desliga a Clarisse encontrando quem escuta na porta dela. O Ollama continua ligado.
set -euo pipefail

porta="${CLARISSE_PORTA:-8765}"
pids="$(ss -ltnpH "sport = :${porta}" | grep -o 'pid=[0-9]*' | cut -d= -f2 | sort -u || true)"

if [[ -z "$pids" ]]; then
  echo "A Clarisse não estava ligada na porta ${porta}."
  exit 0
fi

kill $pids
echo "Clarisse desligada."
