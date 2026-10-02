# A conversa entre a tecla e o servidor do Ouvinte, pelo lado do PowerShell.
#
# O sentinela e o ponto que importa: o texto so pode ser lido depois que o
# servidor levantou o pronto.flag. Ler o arquivo pela presenca dele foi o erro
# que o projeto ja cometeu com o mp3, e o resultado foi audio pela metade - aqui
# seria frase pela metade digitada na janela do usuario.

$ClarisseRoot = Join-Path $env:TEMP ("clarisse-ouvinte-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Force $ClarisseRoot | Out-Null

. (Join-Path $PSScriptRoot '..\clarisse\nucleo.ps1')

function Limpar-Ouvinte {
    Remove-Item (Join-Path $ClarisseRoot 'ouvinte') -Recurse -Force -ErrorAction SilentlyContinue
}

function Responder([string]$texto) {
    $pasta = Join-Path $ClarisseRoot 'ouvinte'
    New-Item -ItemType Directory -Force $pasta | Out-Null
    [System.IO.File]::WriteAllText((Join-Path $pasta 'texto.txt'), $texto)
    [System.IO.File]::WriteAllText((Join-Path $pasta 'pronto.flag'), '')
}

Describe 'Set-ComandoOuvinte' {
    It 'deixa o comando onde o servidor procura' {
        Limpar-Ouvinte

        Set-ComandoOuvinte 'gravar'

        [System.IO.File]::ReadAllText((Join-Path $ClarisseRoot 'ouvinte\comando.txt')) | Should Be 'gravar'
    }

    It 'o comando novo substitui o anterior' {
        Limpar-Ouvinte
        Set-ComandoOuvinte 'gravar'

        Set-ComandoOuvinte 'parar'

        [System.IO.File]::ReadAllText((Join-Path $ClarisseRoot 'ouvinte\comando.txt')) | Should Be 'parar'
    }
}

Describe 'Wait-DitadoPronto' {
    It 'devolve o texto que o servidor deixou' {
        Limpar-Ouvinte
        Responder 'roda os testes'

        Wait-DitadoPronto -TimeoutS 1 | Should Be 'roda os testes'
    }

    It 'nao le o texto enquanto o sinal nao chega' {
        # Sem o sentinela, um arquivo ainda em escrita viraria frase pela metade
        # digitada na janela do usuario.
        Limpar-Ouvinte
        $pasta = Join-Path $ClarisseRoot 'ouvinte'
        New-Item -ItemType Directory -Force $pasta | Out-Null
        [System.IO.File]::WriteAllText((Join-Path $pasta 'texto.txt'), 'metade da fra')

        Wait-DitadoPronto -TimeoutS 1 | Should BeNullOrEmpty
    }

    It 'desiste no prazo quando o servidor nao responde' {
        Limpar-Ouvinte

        Wait-DitadoPronto -TimeoutS 1 | Should BeNullOrEmpty
    }

    It 'limpa a resposta depois de entregar' {
        Limpar-Ouvinte
        Responder 'roda os testes'

        Wait-DitadoPronto -TimeoutS 1 | Out-Null

        Test-Path (Join-Path $ClarisseRoot 'ouvinte\pronto.flag') | Should Be $false
        Test-Path (Join-Path $ClarisseRoot 'ouvinte\texto.txt')   | Should Be $false
    }

    It 'nao entrega a mesma frase duas vezes' {
        Limpar-Ouvinte
        Responder 'roda os testes'
        Wait-DitadoPronto -TimeoutS 1 | Out-Null

        Wait-DitadoPronto -TimeoutS 1 | Should BeNullOrEmpty
    }

    It 'preserva acento no caminho de volta' {
        Limpar-Ouvinte
        $comAcento = 'concilia' + [char]0xE7 + [char]0xE3 + 'o banc' + [char]0xE1 + 'ria'
        Responder $comAcento

        Wait-DitadoPronto -TimeoutS 1 | Should Be $comAcento
    }
}
