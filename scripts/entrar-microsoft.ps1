# Entra na conta Microsoft para a Clarisse ler a agenda e os e-mails. Abre o navegador para escolher a conta.
$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)
uv run python -m clarisse.microsoft entrar
