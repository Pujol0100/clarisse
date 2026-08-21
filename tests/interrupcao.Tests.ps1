# O hook Notification falava sozinho, de proposito, com comentario explicando
# que "aqui o Claude esta parado esperando voce". Na pratica, com quatro sessoes
# abertas, isso virou a Clarisse anunciando em voz alta que um terminal precisa
# de atencao - no meio de uma reuniao, na frente de outras pessoas.
#
# A regra que substitui: audio toca sozinho apenas dentro de um turno que o
# usuario abriu. Fora dele, bipa e espera ser pedido. O modo notify nao abre
# turno nenhum, entao ele nao fala.
#
# Estes testes olham o codigo em vez de rodar a fala, seguindo o mesmo motivo do
# saida.Tests.ps1: verificar de verdade exigiria gerar audio a cada execucao.

$raizClarisse = Join-Path $PSScriptRoot '..\clarisse'

# Recorta um caso do switch de modos, do rotulo ate o proximo rotulo no mesmo
# nivel de indentacao. Sem isso o teste leria o arquivo inteiro e passaria por
# acidente, porque outros modos legitimamente falam.
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

Describe 'o modo notify nao interrompe quem nao pediu' {

    $arquivo = Join-Path $raizClarisse 'clarisse.ps1'
    $bloco = Get-BlocoDoModo $arquivo 'notify'

    It 'o modo notify existe no clarisse.ps1' {
        $bloco | Should Not BeNullOrEmpty
    }

    It 'o modo notify nao dispara fala' {
        # Qualquer chamada de fala aqui reintroduz a interrupcao em reuniao.
        $bloco | Should Not Match 'Start-FalaAssincrona'
        $bloco | Should Not Match 'Invoke-Fala'
        $bloco | Should Not Match 'Start-Modo'
    }

    It 'o modo notify bipa, para o aviso nao desaparecer' {
        # Remover a fala sem por o bipe troca um defeito por outro: a sessao
        # travada esperando permissao ficaria invisivel.
        $bloco | Should Match 'Send-Bipe'
    }

    It 'o modo notify guarda a mensagem na fila, para poder ser pedida depois' {
        # O conteudo nao se perde: ele espera o F7 ou o atalho de leitura.
        $bloco | Should Match 'Add-Pendente'
    }

    It 'o modo notify identifica o projeto na mensagem guardada' {
        # Com varias sessoes, "precisa da sua permissao" sem projeto nao diz
        # para qual terminal ir - e rotulo errado e pior que rotulo nenhum.
        $bloco | Should Match 'Get-NomeProjeto'
    }
}

Describe 'nenhum hook automatico fala sem pedido' {

    It 'o modo stop tambem nao dispara fala' {
        # Guarda de regressao: o stop sempre bipou. Se alguem o fizer falar, a
        # mesma interrupcao volta por outra porta.
        $bloco = Get-BlocoDoModo (Join-Path $raizClarisse 'clarisse.ps1') 'stop'
        $bloco | Should Not BeNullOrEmpty
        $bloco | Should Not Match 'Start-FalaAssincrona'
        $bloco | Should Match 'Send-Bipe'
    }
}
