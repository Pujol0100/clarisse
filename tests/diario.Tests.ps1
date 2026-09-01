# O diario do ditado: dado para medir, nao log para ler.
#
# Ele guarda o que o motor entendeu e o que o usuario acabou enviando, para que
# a taxa de correcao possa ser calculada depois. Sao duas metades escritas por
# processos diferentes - o modo 'ditar' e o hook UserPromptSubmit - unidas por
# um identificador.
#
# Ditado que nunca virou 'enviado' e ditado abandonado, e ele precisa mesmo
# aparecer sozinho: desistir no meio e o sinal mais forte que a medicao tem.

$ClarisseRoot = Join-Path $env:TEMP ("clarisse-diario-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force $ClarisseRoot | Out-Null

. (Join-Path $PSScriptRoot '..\clarisse\nucleo.ps1')

$AGORA = 1800000000

function Nova-Pasta {
    $p = Join-Path $env:TEMP ("diario-" + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Force $p | Out-Null
    return $p
}

Describe 'Add-LinhaDiario' {
    BeforeEach {
        $script:pasta = Nova-Pasta
        $script:arquivo = Join-Path $script:pasta 'diario.jsonl'
    }
    AfterEach {
        Remove-Item $script:pasta -Recurse -Force -ErrorAction SilentlyContinue
    }

    It 'nao escreve nada quando o diario esta desligado' {
        Add-LinhaDiario -Arquivo $script:arquivo -Dados @{ tipo = 'ditado' } -Ligado $false
        Test-Path $script:arquivo | Should Be $false
    }

    It 'escreve uma linha por chamada' {
        Add-LinhaDiario -Arquivo $script:arquivo -Dados @{ tipo = 'ditado'; id = 'a' } -Ligado $true
        Add-LinhaDiario -Arquivo $script:arquivo -Dados @{ tipo = 'enviado'; id = 'a' } -Ligado $true
        @(Get-Content $script:arquivo).Count | Should Be 2
    }

    It 'grava o que foi pedido, e devolve como objeto' {
        Add-LinhaDiario -Arquivo $script:arquivo -Dados @{ tipo = 'ditado'; bruto = 'ola mundo' } -Ligado $true
        $linha = (Get-Content $script:arquivo -Raw -Encoding utf8) | ConvertFrom-Json
        $linha.tipo | Should Be 'ditado'
        $linha.bruto | Should Be 'ola mundo'
    }

    It 'preserva acento na ida e na volta' {
        # O acento e montado por codigo, e nao escrito no arquivo: os .ps1 deste
        # projeto nao tem BOM, e o PowerShell 5.1 le arquivo sem BOM como ANSI -
        # um literal acentuado aqui seria corrompido antes do teste comecar, e o
        # que falharia seria o teste, nao o codigo.
        $ditado = 'concilia' + [char]0xE7 + [char]0xE3 + 'o de f' + [char]0xE9 + 'rias'

        Add-LinhaDiario -Arquivo $script:arquivo -Dados @{ bruto = $ditado } -Ligado $true

        $linha = (Get-Content $script:arquivo -Raw -Encoding utf8) | ConvertFrom-Json
        $linha.bruto | Should Be $ditado
    }

    It 'a poda nao estraga o acento das linhas que ficam' {
        $ditado = 'f' + [char]0xE9 + 'rias'
        1..25 | ForEach-Object {
            Add-LinhaDiario -Arquivo $script:arquivo -Dados @{ bruto = $ditado } -Ligado $true -Teto 20
        }

        $linhas = @(Get-Content $script:arquivo -Encoding utf8)
        ($linhas[-1] | ConvertFrom-Json).bruto | Should Be $ditado
    }

    It 'nunca deixa um registro quebrar em duas linhas' {
        Add-LinhaDiario -Arquivo $script:arquivo -Dados @{ bruto = "uma`nlinha`r`noutra" } -Ligado $true
        @(Get-Content $script:arquivo).Count | Should Be 1
    }

    It 'descarta os mais antigos quando passa do teto' {
        1..25 | ForEach-Object {
            Add-LinhaDiario -Arquivo $script:arquivo -Dados @{ n = $_ } -Ligado $true -Teto 20
        }
        $linhas = @(Get-Content $script:arquivo)
        $linhas.Count | Should Be 20
        ($linhas[0] | ConvertFrom-Json).n | Should Be 6
        ($linhas[-1] | ConvertFrom-Json).n | Should Be 25
    }

    It 'cria a pasta quando ela ainda nao existe' {
        $fundo = Join-Path $script:pasta 'que\nao\existe\diario.jsonl'
        Add-LinhaDiario -Arquivo $fundo -Dados @{ tipo = 'ditado' } -Ligado $true
        Test-Path $fundo | Should Be $true
    }
}

Describe 'Test-DiarioLigado' {
    AfterEach {
        Remove-Item (Join-Path $ClarisseRoot 'config.json') -Force -ErrorAction SilentlyContinue
    }

    It 'e falso quando o config nao diz nada sobre o diario' {
        Test-DiarioLigado | Should Be $false
    }

    It 'e falso quando o config diz false' {
        Set-Content (Join-Path $ClarisseRoot 'config.json') '{"ouvinte":{"diario":false}}' -Encoding utf8
        Test-DiarioLigado | Should Be $false
    }

    It 'e verdadeiro quando o config diz true' {
        Set-Content (Join-Path $ClarisseRoot 'config.json') '{"ouvinte":{"diario":true}}' -Encoding utf8
        Test-DiarioLigado | Should Be $true
    }
}
