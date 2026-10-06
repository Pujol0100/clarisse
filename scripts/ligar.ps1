# Liga a Clarisse a partir da pasta do projeto, onde quer que ela esteja.
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
uv run python -u run.py
