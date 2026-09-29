#!/usr/bin/env bash
# Liga a Clarisse a partir da pasta do projeto, onde quer que ela esteja.
set -euo pipefail

cd "$(dirname "$0")/.."
exec uv run python -u run.py
