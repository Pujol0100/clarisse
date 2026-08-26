# O marcador que autoriza a Clarisse a falar sozinha.
#
# A regra de 21/08, depois de ela interromper uma reuniao: a fala automatica so
# acontece dentro de um turno que o usuario abriu. Ditar abre; o hook Stop gasta.
# Sem marcador, o hook so bipa e espera o atalho.
#
# Sao duas etapas, e a divisao existe por um motivo:
#
#   1. Ditar deixa um marcador SEM projeto. O servidor do Ouvinte e um por
#      maquina e nao sabe em qual sessao o texto caiu.
#   2. O prompt enviado logo depois diz o projeto - o hook UserPromptSubmit sabe
#      o cwd dele. So entao o turno ganha dono.
#
# O UserPromptSubmit nao abre turno sozinho, e isso e deliberado: ele dispara em
# todo prompt, inclusive digitado, e a Clarisse voltaria a falar nas dez sessoes.
# Ele so da nome a um turno que o ditado ja abriu.

$ClarisseRoot = Join-Path $env:TEMP ("clarisse-turno-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force $ClarisseRoot | Out-Null

. (Join-Path $PSScriptRoot '..\clarisse\nucleo.ps1')

$AGORA = 1800000000
$QUINZE_MIN = 900

function Limpar-Turnos {
    Remove-Item (Join-Path $ClarisseRoot 'turno') -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item (Join-Path $ClarisseRoot 'ditado.txt') -Force -ErrorAction SilentlyContinue
}

Describe 'do ditado ao turno do projeto' {
    It 'o prompt enviado depois de ditar abre o turno daquele projeto' {
        Limpar-Turnos
        Set-DitadoRecente -Agora $AGORA

        Resolve-TurnoDoProjeto -Projeto 'voz-ao-claude' -Agora ($AGORA + 8) | Should Be $true
        Read-Turno -Projeto 'voz-ao-claude' -Agora ($AGORA + 20) | Should Be $true
    }

    It 'prompt digitado, sem ditado antes, nao abre turno nenhum' {
        Limpar-Turnos

        Resolve-TurnoDoProjeto -Projeto 'voz-ao-claude' -Agora $AGORA | Should Be $false
        Read-Turno -Projeto 'voz-ao-claude' -Agora $AGORA | Should Be $false
    }

    It 'ditado velho nao vira turno' {
        Limpar-Turnos
        Set-DitadoRecente -Agora $AGORA

        Resolve-TurnoDoProjeto -Projeto 'voz-ao-claude' -Agora ($AGORA + 61) | Should Be $false
    }

    It 'um ditado abre um turno so, e nao um em cada sessao' {
        Limpar-Turnos
        Set-DitadoRecente -Agora $AGORA

        Resolve-TurnoDoProjeto -Projeto 'voz-ao-claude' -Agora ($AGORA + 5) | Should Be $true
        Resolve-TurnoDoProjeto -Projeto 'omni-api' -Agora ($AGORA + 6) | Should Be $false
    }

    It 'ditar de novo renova a chance de abrir turno' {
        Limpar-Turnos
        Set-DitadoRecente -Agora $AGORA
        Resolve-TurnoDoProjeto -Projeto 'voz-ao-claude' -Agora ($AGORA + 5) | Out-Null

        Set-DitadoRecente -Agora ($AGORA + 100)

        Resolve-TurnoDoProjeto -Projeto 'omni-api' -Agora ($AGORA + 105) | Should Be $true
    }
}

Describe 'Read-Turno' {
    It 'o turno serve uma vez so' {
        Limpar-Turnos
        Set-DitadoRecente -Agora $AGORA
        Resolve-TurnoDoProjeto -Projeto 'voz-ao-claude' -Agora $AGORA | Out-Null

        Read-Turno -Projeto 'voz-ao-claude' -Agora $AGORA | Should Be $true
        Read-Turno -Projeto 'voz-ao-claude' -Agora $AGORA | Should Be $false
    }

    It 'turno vencido nao deixa falar' {
        Limpar-Turnos
        Set-DitadoRecente -Agora $AGORA
        Resolve-TurnoDoProjeto -Projeto 'voz-ao-claude' -Agora $AGORA | Out-Null

        Read-Turno -Projeto 'voz-ao-claude' -Agora ($AGORA + $QUINZE_MIN + 1) | Should Be $false
    }

    It 'turno no limite ainda vale' {
        Limpar-Turnos
        Set-DitadoRecente -Agora $AGORA
        Resolve-TurnoDoProjeto -Projeto 'voz-ao-claude' -Agora $AGORA | Out-Null

        Read-Turno -Projeto 'voz-ao-claude' -Agora ($AGORA + $QUINZE_MIN) | Should Be $true
    }

    It 'turno de um projeto nao deixa outro falar' {
        Limpar-Turnos
        Set-DitadoRecente -Agora $AGORA
        Resolve-TurnoDoProjeto -Projeto 'voz-ao-claude' -Agora $AGORA | Out-Null

        Read-Turno -Projeto 'omni-api' -Agora $AGORA | Should Be $false
        Read-Turno -Projeto 'voz-ao-claude' -Agora $AGORA | Should Be $true
    }

    It 'marcador do futuro nao vale' {
        # Relogio da maquina mexido. Um marcador que valeria por horas e pior do
        # que marcador nenhum.
        Limpar-Turnos
        Set-DitadoRecente -Agora ($AGORA + 3600)
        Resolve-TurnoDoProjeto -Projeto 'voz-ao-claude' -Agora ($AGORA + 3600) | Out-Null

        Read-Turno -Projeto 'voz-ao-claude' -Agora $AGORA | Should Be $false
    }

    It 'marcador estragado nao deixa falar, e some' {
        Limpar-Turnos
        Set-DitadoRecente -Agora $AGORA
        Resolve-TurnoDoProjeto -Projeto 'voz-ao-claude' -Agora $AGORA | Out-Null
        $arquivo = Join-Path (Join-Path $ClarisseRoot 'turno') 'voz-ao-claude.txt'
        [System.IO.File]::WriteAllText($arquivo, 'nao e um instante')

        Read-Turno -Projeto 'voz-ao-claude' -Agora $AGORA | Should Be $false
        Test-Path $arquivo | Should Be $false
    }

    It 'projeto sem nome nao abre nem gasta turno' {
        Limpar-Turnos
        Set-DitadoRecente -Agora $AGORA

        Resolve-TurnoDoProjeto -Projeto '' -Agora $AGORA | Should Be $false
        Read-Turno -Projeto '' -Agora $AGORA | Should Be $false
    }

    It 'nome com caractere proibido nao escapa da pasta' {
        Limpar-Turnos
        Set-DitadoRecente -Agora $AGORA
        Resolve-TurnoDoProjeto -Projeto 'cliente/projeto' -Agora $AGORA | Out-Null

        $marcadores = @(Get-ChildItem (Join-Path $ClarisseRoot 'turno') -File | ForEach-Object { $_.Name })
        $marcadores | Should Be 'cliente-projeto.txt'
        Read-Turno -Projeto 'cliente/projeto' -Agora $AGORA | Should Be $true
    }

    It 'pasta que nunca existiu nao quebra' {
        Limpar-Turnos

        Read-Turno -Projeto 'voz-ao-claude' -Agora $AGORA | Should Be $false
    }
}
