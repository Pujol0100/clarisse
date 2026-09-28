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

Describe 'New-IdDitado' {
    It 'devolve dois pedacos separados por hifen' {
        New-IdDitado | Should Match '^\d+-\d+$'
    }

    It 'nao repete em duas chamadas seguidas' {
        $a = New-IdDitado
        Start-Sleep -Milliseconds 3
        $b = New-IdDitado
        $a | Should Not Be $b
    }
}

Describe 'Read-MedidaDitado' {
    BeforeEach {
        $script:pasta = Nova-Pasta
    }
    AfterEach {
        Remove-Item $script:pasta -Recurse -Force -ErrorAction SilentlyContinue
    }

    It 'devolve zeros quando o servidor nao deixou medida' {
        $m = Read-MedidaDitado $script:pasta
        $m.segundos_audio | Should Be 0
        $m.segundos_transcricao | Should Be 0
    }

    It 'devolve o que o servidor mediu' {
        Set-Content (Join-Path $script:pasta 'medida.json') '{"segundos_audio":4.2,"segundos_transcricao":3.1}' -Encoding utf8
        $m = Read-MedidaDitado $script:pasta
        $m.segundos_audio | Should Be 4.2
        $m.segundos_transcricao | Should Be 3.1
    }

    It 'devolve zeros quando a medida esta estragada' {
        Set-Content (Join-Path $script:pasta 'medida.json') 'isto nao e json' -Encoding utf8
        $m = Read-MedidaDitado $script:pasta
        $m.segundos_audio | Should Be 0
    }
}

Describe 'o id que liga as duas metades do par' {
    BeforeEach {
        Remove-Item (Join-Path $OuvinteDir 'ditado-id.txt') -Force -ErrorAction SilentlyContinue
    }

    It 'nao devolve nada quando nenhum ditado aconteceu' {
        Read-IdDitadoRecente -Agora $AGORA | Should BeNullOrEmpty
    }

    It 'devolve o id que o ditado deixou' {
        Set-IdDitadoRecente -Id 'abc-1' -Agora $AGORA
        (Read-IdDitadoRecente -Agora $AGORA).id | Should Be 'abc-1'
    }

    It 'serve uma vez so, para nao fechar o par de dois prompts' {
        Set-IdDitadoRecente -Id 'abc-1' -Agora $AGORA
        Read-IdDitadoRecente -Agora $AGORA | Out-Null
        Read-IdDitadoRecente -Agora $AGORA | Should BeNullOrEmpty
    }

    It 'diz quantos segundos o usuario passou revisando' {
        Set-IdDitadoRecente -Id 'abc-1' -Agora $AGORA
        (Read-IdDitadoRecente -Agora ($AGORA + 18)).segundos_ate_enviar | Should Be 18
    }

    It 'aceita revisao demorada, ao contrario do turno' {
        Set-IdDitadoRecente -Id 'abc-1' -Agora $AGORA
        (Read-IdDitadoRecente -Agora ($AGORA + 300)).id | Should Be 'abc-1'
    }

    It 'id de mais de quinze minutos nao fecha par nenhum' {
        Set-IdDitadoRecente -Id 'abc-1' -Agora $AGORA
        Read-IdDitadoRecente -Agora ($AGORA + 901) | Should BeNullOrEmpty
    }

    It 'marcador do futuro nao vale' {
        Set-IdDitadoRecente -Id 'abc-1' -Agora ($AGORA + 60)
        Read-IdDitadoRecente -Agora $AGORA | Should BeNullOrEmpty
    }

    It 'marcador estragado nao vale, e some' {
        [System.IO.File]::WriteAllText((Join-Path $OuvinteDir 'ditado-id.txt'), 'lixo sem tempo', $Utf8SemBom)
        Read-IdDitadoRecente -Agora $AGORA | Should BeNullOrEmpty
        Test-Path (Join-Path $OuvinteDir 'ditado-id.txt') | Should Be $false
    }
}

# As duas metades do par sao escritas por processos diferentes, e nenhum teste de
# funcao prova que os modos do clarisse.ps1 chamam o diario. Estes olham o codigo
# que vai rodar, no mesmo estilo dos guardas do modo notify.

function Get-BlocoDoModo([string]$arquivo, [string]$modo) {
    $linhas = @([System.IO.File]::ReadAllText($arquivo, [System.Text.Encoding]::UTF8) -split "`r?`n")
    $inicio = -1
    for ($i = 0; $i -lt $linhas.Count; $i++) {
        if ($linhas[$i] -match "^(\s*)'$modo'\s*\{") { $inicio = $i; break }
    }
    if ($inicio -lt 0) { return '' }

    $recuo = $Matches[1].Length
    $fim = $linhas.Count - 1
    for ($i = $inicio + 1; $i -lt $linhas.Count; $i++) {
        if ($linhas[$i] -match "^\s{$recuo}'[a-z-]+'\s*\{") { $fim = $i - 1; break }
    }
    return ($linhas[$inicio..$fim] -join "`n")
}

Describe 'os modos que alimentam o diario' {

    $script = Join-Path $PSScriptRoot '..\clarisse\clarisse.ps1'

    It 'o modo ditar registra o que o motor entendeu' {
        $bloco = Get-BlocoDoModo $script 'ditar'
        $bloco | Should Not BeNullOrEmpty
        $bloco | Should Match 'Add-LinhaDiario'
        $bloco | Should Match "tipo\s*=\s*'ditado'"
    }

    It 'o modo ditar guarda o id para o prompt fechar o par' {
        $bloco = Get-BlocoDoModo $script 'ditar'
        $bloco | Should Match 'Set-IdDitadoRecente'
    }

    It 'o modo ditar so registra o que chegou a ser digitado' {
        # Texto que nao entrou na janela nao e ditado: registrar isso poria no
        # diario uma frase que o usuario nunca viu, e o par nunca fecharia.
        $bloco = Get-BlocoDoModo $script 'ditar'
        $bloco | Should Match 'Send-TextoNaJanela'
        $linhas = @(($bloco -split "`n"))
        $iEnvio = ($linhas | Select-String -Pattern 'Send-TextoNaJanela').LineNumber
        $iDiario = ($linhas | Select-String -Pattern 'Add-LinhaDiario').LineNumber
        $iDiario | Should BeGreaterThan $iEnvio
    }

    It 'o modo prompt fecha o par com o texto enviado' {
        $bloco = Get-BlocoDoModo $script 'prompt'
        $bloco | Should Match 'Add-LinhaDiario'
        $bloco | Should Match "tipo\s*=\s*'enviado'"
        $bloco | Should Match 'Get-PromptDoHook'
    }

    It 'o modo prompt le o stdin uma vez so' {
        # Read-StdinDoHook consome o fluxo ate o fim. Uma segunda chamada
        # devolveria vazio, e o diario guardaria prompt em branco para sempre.
        #
        # Linha de comentario nao conta: o que se mede aqui e chamada, e o nome
        # aparece tambem na explicacao acima dela.
        $bloco = Get-BlocoDoModo $script 'prompt'
        $chamadas = @(($bloco -split "`n") |
            Where-Object { $_ -notmatch '^\s*#' -and $_ -match 'Read-StdinDoHook' })
        $chamadas.Count | Should Be 1
    }

    It 'o modo prompt continua sem falar e sem bipar' {
        # A regra de 21/08 nao muda por causa da medicao.
        $bloco = Get-BlocoDoModo $script 'prompt'
        $bloco | Should Not Match 'Invoke-Fala'
        $bloco | Should Not Match 'Start-Modo'
        $bloco | Should Not Match 'Send-Bipe'
    }
}

Describe 'Get-PromptDoHook' {
    It 'tira o prompt do JSON que o Claude Code manda no stdin' {
        Get-PromptDoHook '{"cwd":"/p/omni","prompt":"roda os testes"}' | Should Be 'roda os testes'
    }

    It 'devolve vazio quando o JSON nao tem prompt' {
        Get-PromptDoHook '{"cwd":"/p/omni"}' | Should Be ''
    }

    It 'nao quebra com entrada que nao e JSON' {
        Get-PromptDoHook 'isto nao e json' | Should Be ''
    }

    It 'nao quebra com entrada vazia' {
        Get-PromptDoHook '' | Should Be ''
    }

    It 'preserva acento vindo do JSON' {
        $esperado = 'f' + [char]0xE9 + 'rias'
        Get-PromptDoHook '{"prompt":"f\u00e9rias"}' | Should Be $esperado
    }
}

Describe 'o diario no config e no instalador' {

    It 'o config de referencia traz o diario, desligado' {
        $c = Get-Content (Join-Path $PSScriptRoot '..\clarisse\config.json') -Raw -Encoding utf8 | ConvertFrom-Json
        ($c.ouvinte.PSObject.Properties.Name -join ',') | Should Match 'diario'
        $c.ouvinte.diario | Should Be $false
    }

    It 'o padrao embutido no nucleo traz o diario, desligado' {
        # Quem roda sem config.json nenhum tem que cair no mesmo lugar: ligado
        # por omissao seria gravar o que o usuario dita sem ele ter pedido.
        $texto = Get-Content (Join-Path $PSScriptRoot '..\clarisse\nucleo.ps1') -Raw -Encoding utf8
        $texto | Should Match 'diario\s*=\s*\$false'
    }

    It 'o instalador acrescenta o diario a quem ja tinha o bloco do ouvinte' {
        $texto = Get-Content (Join-Path $PSScriptRoot '..\instalar.ps1') -Raw -Encoding utf8
        $texto | Should Match "notcontains 'diario'"
    }

    It 'o status diz quantas linhas o diario ja tem' {
        # Sem isso nao ha como saber quando a amostra fechou sem abrir o Python.
        $bloco = Get-BlocoDoModo (Join-Path $PSScriptRoot '..\clarisse\clarisse.ps1') 'status'
        $bloco | Should Match 'Test-DiarioLigado'
    }
}
