# Desliga a Clarisse encontrando quem escuta na porta dela. O Ollama continua ligado.
$porta = if ($env:CLARISSE_PORTA) { [int]$env:CLARISSE_PORTA } else { 8765 }
$donos = Get-NetTCPConnection -LocalPort $porta -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique

if (-not $donos) {
    Write-Output "A Clarisse não estava ligada na porta $porta."
    exit 0
}

Stop-Process -Id $donos
for ($i = 0; $i -lt 50; $i++) {
    if (-not (Get-NetTCPConnection -LocalPort $porta -State Listen -ErrorAction SilentlyContinue)) {
        Write-Output 'Clarisse desligada.'
        exit 0
    }
    Start-Sleep -Milliseconds 200
}
Write-Error 'A Clarisse não fechou em 10 segundos.'
exit 1
