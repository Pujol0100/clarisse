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
for _ in $(seq 1 50); do
  ss -ltnH "sport = :${porta}" | grep -q . || { echo "Clarisse desligada."; exit 0; }
  sleep 0.2
done
echo "A Clarisse não fechou em 10 segundos." >&2
exit 1
