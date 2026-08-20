# O instalador copia uma lista de arquivos escrita a mao. Um arquivo novo no
# codigo que ninguem lembra de acrescentar ali gera a pior falha possivel: a
# instalacao termina anunciando sucesso e a Clarisse fica muda, porque a peca
# que faltou so e procurada na hora de falar.

Describe 'instalador' {
    It 'copia todo arquivo de codigo que existe na pasta clarisse' {
        # A busca e recursiva porque a Leitora vive em clarisse\leitora. Sem
        # recursao, uma subpasta inteira ficava fora da vigilancia - justamente
        # onde o codigo novo passou a morar.
        #
        # A comparacao e por nome de arquivo, nao por caminho, porque o
        # instalador monta o caminho com interpolacao e o caminho literal nunca
        # aparece no texto. Limite conhecido: dois arquivos de mesmo nome em
        # pastas diferentes se cobrem. Hoje isso vale so para __init__.py, que o
        # instalador nomeia nas duas listas.
        $origem = Join-Path $PSScriptRoot '..\clarisse'
        $codigo = @(
            Get-ChildItem $origem -File -Recurse |
                Where-Object { @('.ps1', '.py') -contains $_.Extension } |
                ForEach-Object { $_.Name } |
                Sort-Object -Unique
        )
        $codigo.Count | Should BeGreaterThan 0

        $instalador = [System.IO.File]::ReadAllText(
            (Join-Path $PSScriptRoot '..\instalar.ps1'), [System.Text.Encoding]::UTF8)

        $faltando = @($codigo | Where-Object { $instalador -notmatch [regex]::Escape($_) })
        ($faltando -join ', ') | Should BeNullOrEmpty
    }

    It 'cria toda subpasta de codigo que existe na pasta clarisse' {
        # Nomear os arquivos nao basta: sem criar a pasta de destino, o
        # Copy-Item falha na instalacao e a mesma falha silenciosa volta.
        # So conta pasta que tem codigo dentro. Isso exclui __pycache__ e
        # qualquer outro cache de ferramenta sem precisar mante-los numa lista.
        $origem = Join-Path $PSScriptRoot '..\clarisse'
        $pastas = @(
            Get-ChildItem $origem -Directory |
                Where-Object {
                    @(Get-ChildItem $_.FullName -File |
                        Where-Object { @('.ps1', '.py') -contains $_.Extension }).Count -gt 0
                } |
                ForEach-Object { $_.Name }
        )
        $pastas.Count | Should BeGreaterThan 0

        $instalador = [System.IO.File]::ReadAllText(
            (Join-Path $PSScriptRoot '..\instalar.ps1'), [System.Text.Encoding]::UTF8)

        $faltando = @($pastas | Where-Object { $instalador -notmatch [regex]::Escape($_) })
        ($faltando -join ', ') | Should BeNullOrEmpty
    }
}
