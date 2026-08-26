# O texto ditado chega na janela em foco pela area de transferencia, e nao tecla
# a tecla: acento por SendKeys e fonte conhecida de caractere perdido.
#
# A area de transferencia e do usuario, nao nossa. Ela e emprestada por um
# instante e devolvida como estava - inclusive quando o colar estoura no meio.
#
# O teste passa a acao de colar por parametro. Sem isso, rodar a suite dispararia
# um Ctrl+V de verdade em qualquer janela que estivesse em foco.

. (Join-Path $PSScriptRoot '..\clarisse\nucleo.ps1')

Describe 'Resolve-ProjetoDoTitulo' {
    $projetos = @('voz-ao-claude', 'omni-api', 'financeiro-areceber', 'compliance-app')

    It 'acha o projeto quando o titulo e o nome dele' {
        Resolve-ProjetoDoTitulo 'omni-api' $projetos | Should Be 'omni-api'
    }
    It 'ignora diferenca de maiuscula e minuscula' {
        Resolve-ProjetoDoTitulo 'OMNI-API' $projetos | Should Be 'omni-api'
    }
    It 'acha pelo pedaco do nome que o terminal mostra' {
        # O Windows Terminal mostra o titulo da aba ativa, e ele vem cortado:
        # a aba do financeiro-areceber aparece so como "areceber".
        Resolve-ProjetoDoTitulo 'areceber' $projetos | Should Be 'financeiro-areceber'
    }
    It 'acha o nome no meio da sujeira que o terminal poe em volta' {
        Resolve-ProjetoDoTitulo 'voz-ao-claude - Claude Code' $projetos | Should Be 'voz-ao-claude'
    }
    It 'escolhe o nome mais especifico quando dois casam' {
        $ambiguos = @('api', 'omni-api')
        Resolve-ProjetoDoTitulo 'omni-api' $ambiguos | Should Be 'omni-api'
    }
    It 'devolve vazio para titulo em branco' {
        Resolve-ProjetoDoTitulo '   ' $projetos | Should BeNullOrEmpty
    }
    It 'devolve vazio quando nenhum projeto casa' {
        Resolve-ProjetoDoTitulo 'Bloco de Notas' $projetos | Should BeNullOrEmpty
    }
    It 'devolve vazio quando nao ha projeto nenhum' {
        Resolve-ProjetoDoTitulo 'omni-api' @() | Should BeNullOrEmpty
    }
    It 'titulo curto demais nao casa com nada' {
        # Duas letras casariam com quase todo projeto, e marcar o turno do
        # projeto errado faria a Clarisse falar na sessao errada.
        Resolve-ProjetoDoTitulo 'ap' $projetos | Should BeNullOrEmpty
    }
}

# O texto ditado e digitado por SendInput com KEYEVENTF_UNICODE, e nao colado.
#
# Medido em 26/08/2026: a area de transferencia desta maquina ficou indisponivel
# de forma persistente, e antes disso falhava calada em 2 de 25 idas deixando a
# area vazia. Ela e recurso disputado da maquina inteira - testar contra ela
# seria escrever teste que passa conforme o que mais estiver aberto.
#
# O envio de verdade nao e testado aqui de proposito: disparar tecla sintetica
# durante a suite digitaria na janela que estivesse em foco. Ele entra por
# parametro, e a verificacao real e manual, com o usuario na frente.

Describe 'Send-TextoNaJanela' {
    It 'devolve falso e nao digita nada quando o texto e vazio' {
        $visto = @{ chamou = $false }

        $r = Send-TextoNaJanela '   ' -Enviar { $visto.chamou = $true }

        $r | Should Be $false
        $visto.chamou | Should Be $false
    }

    It 'entrega o texto exatamente como veio' {
        $visto = @{}

        Send-TextoNaJanela 'roda os testes' -Enviar { param($t) $visto.texto = $t } | Out-Null

        $visto.texto | Should Be 'roda os testes'
    }

    It 'preserva acento, que e o motivo de nao usar SendKeys' {
        $comAcento = 'concilia' + [char]0xE7 + [char]0xE3 + 'o banc' + [char]0xE1 + 'ria'
        $visto = @{}

        Send-TextoNaJanela $comAcento -Enviar { param($t) $visto.texto = $t } | Out-Null

        $visto.texto | Should Be $comAcento
    }

    It 'nunca deixa passar quebra de linha' {
        # No prompt do Claude Code, quebra de linha ENVIA a mensagem. Enviar por
        # engano e a unica coisa que este desenho nao pode fazer.
        $visto = @{}

        Send-TextoNaJanela "roda os testes`nagora" -Enviar { param($t) $visto.texto = $t } | Out-Null

        $visto.texto | Should Be 'roda os testes agora'
    }

    It 'nunca deixa passar quebra de linha do Windows' {
        $visto = @{}

        Send-TextoNaJanela "roda os testes`r`nagora" -Enviar { param($t) $visto.texto = $t } | Out-Null

        $visto.texto | Should Be 'roda os testes agora'
    }

    It 'devolve verdadeiro quando digitou' {
        Send-TextoNaJanela 'roda os testes' -Enviar { } | Should Be $true
    }

    It 'o digitador de verdade existe e compila' {
        # Compila o interop sem disparar tecla nenhuma: texto vazio devolve zero
        # eventos enviados.
        Send-TextoUnicode '' | Should Be 0
    }
}
