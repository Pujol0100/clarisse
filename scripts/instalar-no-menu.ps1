# Põe a Clarisse no menu Iniciar. Rode de dentro da pasta onde ela vai ficar.
$ErrorActionPreference = 'Stop'
$raiz = Split-Path -Parent $PSScriptRoot
$destino = Join-Path ([Environment]::GetFolderPath('Programs')) 'Clarisse.lnk'

$atalho = (New-Object -ComObject WScript.Shell).CreateShortcut($destino)
$atalho.TargetPath = (Get-Command wt.exe).Source
$atalho.Arguments = "-d `"$raiz`" powershell.exe -NoExit -ExecutionPolicy Bypass -File `"$raiz\scripts\ligar.ps1`""
$atalho.WorkingDirectory = $raiz
$atalho.Description = 'Assistente de voz local'
$atalho.Save()

Write-Output "Clarisse no menu Iniciar: $destino"
