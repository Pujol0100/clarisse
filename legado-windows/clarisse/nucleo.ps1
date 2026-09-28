#Requires -Version 5.1
<#
    Nucleo da Clarisse: tudo que clarisse.ps1 e atalhos.ps1 compartilham.
    Carregado por dot-source. Nao executa nada sozinho.

    Para apontar para outra pasta (testes), defina $ClarisseRoot antes do dot-source.
#>

if (-not $ClarisseRoot) { $ClarisseRoot = $PSScriptRoot }

$Root           = $ClarisseRoot
$ConfigPath     = Join-Path $Root 'config.json'
$FalaPath       = Join-Path $Root 'fala.txt'
$EntradaDir     = Join-Path $Root 'entrada'
$FilaDir        = Join-Path $Root 'fila'
$PendenteLegado = Join-Path $Root 'pendente.txt'
$ControlePath   = Join-Path $Root 'controle.txt'
$EmLeituraPath  = Join-Path $Root 'emleitura.txt'
$SelecaoPath    = Join-Path $Root 'selecao.txt'
$HistPath       = Join-Path $Root 'historico.txt'
$PidPath        = Join-Path $Root 'player.pid'
$AtalhosPidPath = Join-Path $Root 'atalhos.pid'
$PendDir        = Join-Path $Root 'pending'
$TurnoDir       = Join-Path $Root 'turno'
$DitadoPath     = Join-Path $Root 'ditado.txt'
$OuvinteDir     = Join-Path $Root 'ouvinte'
$LogPath        = Join-Path $Root 'clarisse.log'
$Separador      = '---CLARISSE---'
$MaxHist        = 5

$Utf8SemBom = New-Object System.Text.UTF8Encoding($false)

function Write-Log($msg) {
    try {
        $stamp = (Get-Date).ToString('dd/MM/yyyy HH:mm:ss')
        Add-Content -Path $LogPath -Value "[$stamp] $msg" -Encoding utf8
    } catch { }
}

function Get-Config {
    if (Test-Path $ConfigPath) {
        try { return Get-Content $ConfigPath -Raw -Encoding utf8 | ConvertFrom-Json } catch { }
    }
    return [pscustomobject]@{
        enabled   = $true
        autoStart = $true
        voice     = 'pt-BR-ThalitaMultilingualNeural'
        rate      = '+12%'
        volume    = '+0%'
        maxChars  = 1800
        python    = ''
        triagem   = $true
        atalhos   = [pscustomobject]@{
            ativo    = $true
            ler      = 'Ctrl+Alt+L'
            pular    = 'Ctrl+Alt+J'
            pausar   = 'Ctrl+Alt+P'
            cancelar = 'Ctrl+Alt+X'
        }
        ouvinte   = [pscustomobject]@{
            # Desligado por padrao: o modelo ocupa 500 a 700 MB de RAM e a
            # instalacao das bibliotecas passa de 1 GB. Quem quer ditar liga.
            ativo  = $false
            ditar  = 'Ctrl+Alt+D'
            modelo = 'small'
            # O diario guarda o texto ditado em disco. Ligado por omissao seria
            # gravar o que o usuario fala sem ele ter pedido.
            diario = $false
        }
    }
}

function Save-Config($cfg) {
    $cfg | ConvertTo-Json -Depth 5 | Out-File -FilePath $ConfigPath -Encoding utf8
}

# Descobre como invocar o Python. O campo "python" do config tem prioridade;
# sem ele, procura instalacoes comuns e cai no launcher "py -3" como ultimo recurso.
function Get-PythonInvocacao($cfg) {
    if ($cfg.python -and (Test-Path $cfg.python)) {
        return @{ exe = $cfg.python; pre = @() }
    }
    $candidatos = @(
        "$env:LOCALAPPDATA\Python\bin\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python313\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe"
    )
    foreach ($c in $candidatos) {
        if (Test-Path $c) { return @{ exe = $c; pre = @() } }
    }
    $cmd = Get-Command python.exe -ErrorAction SilentlyContinue
    # O stub da Microsoft Store abre a loja em vez de rodar Python.
    if ($cmd -and $cmd.Source -and $cmd.Source -notlike '*WindowsApps*') {
        return @{ exe = $cmd.Source; pre = @() }
    }
    if (Get-Command py.exe -ErrorAction SilentlyContinue) {
        return @{ exe = 'py'; pre = @('-3') }
    }
    return $null
}

# Remove marcacao que nao faz sentido em audio e limita o tamanho da fala.
function ConvertTo-Falavel([string]$raw, [int]$maxChars) {
    if ([string]::IsNullOrWhiteSpace($raw)) { return '' }
    $t = $raw
    $t = [regex]::Replace($t, '(?s)```.*?```', ' ')
    $t = [regex]::Replace($t, '`([^`]*)`', '$1')
    $t = [regex]::Replace($t, '!?\[([^\]]*)\]\([^)]*\)', '$1')
    $t = [regex]::Replace($t, '^\s{0,3}#{1,6}\s*', '', 'Multiline')
    $t = [regex]::Replace($t, '\*\*([^*]*)\*\*', '$1')
    $t = [regex]::Replace($t, '(?<!\w)\*([^*]+)\*(?!\w)', '$1')
    $t = [regex]::Replace($t, '^\s*[-*+]\s+', '', 'Multiline')
    $t = [regex]::Replace($t, '\|', ' ')
    $t = [regex]::Replace($t, '\s+', ' ')
    $t = $t.Trim()
    if ($t.Length -gt $maxChars) {
        $corte = $t.Substring(0, $maxChars)
        $ultimo = $corte.LastIndexOfAny([char[]]@('.', '!', '?', ';'))
        if ($ultimo -gt ($maxChars * 0.5)) { $corte = $corte.Substring(0, $ultimo + 1) }
        $t = $corte.TrimEnd() + '...'
    }
    return $t
}

# Quebra o texto nos pedacos que serao sintetizados um a um.
#
# O primeiro segmento e deliberadamente curto: e ele que decide quanto tempo o
# usuario espera em silencio depois de pedir a leitura. Os seguintes podem ser
# maiores, porque a sintese e cerca de tres vezes mais rapida que a fala e ganha
# folga enquanto o primeiro toca. Fragmentar demais tambem custa: cada segmento
# e uma ida ao servidor de voz.
function Split-EmSegmentos {
    param(
        [string]$Texto,
        [int]$PrimeiroMax = 110,
        [int]$DemaisMax   = 320
    )
    if ([string]::IsNullOrWhiteSpace($Texto)) { return @() }
    $t = ([regex]::Replace($Texto, '\s+', ' ')).Trim()

    # Fim de frase e pontuacao seguida de espaco. Numero decimal fica inteiro de
    # graca: em "1.500" o ponto nao vem seguido de espaco.
    $frases = @([regex]::Split($t, '(?<=[.!?;])\s+') | ForEach-Object { $_.Trim() } | Where-Object { $_ })

    # Frase maior que o teto e cortada entre palavras, nunca no meio de uma.
    $unidades = New-Object System.Collections.ArrayList
    foreach ($f in $frases) {
        if ($f.Length -le $PrimeiroMax) { [void]$unidades.Add($f); continue }
        $acc = ''
        foreach ($p in ($f -split ' ')) {
            if (-not $acc)                                          { $acc = $p }
            elseif (($acc.Length + 1 + $p.Length) -le $PrimeiroMax) { $acc = "$acc $p" }
            else                                                    { [void]$unidades.Add($acc); $acc = $p }
        }
        if ($acc) { [void]$unidades.Add($acc) }
    }

    $segs = New-Object System.Collections.ArrayList
    $acc = ''
    foreach ($u in $unidades) {
        $limite = if ($segs.Count -eq 0) { $PrimeiroMax } else { $DemaisMax }
        if (-not $acc)                                      { $acc = $u }
        elseif (($acc.Length + 1 + $u.Length) -le $limite)  { $acc = "$acc $u" }
        else                                                { [void]$segs.Add($acc); $acc = $u }
    }
    if ($acc) { [void]$segs.Add($acc) }

    # Sem o operador virgula aqui de proposito: quem chama envolve em @(), e os
    # dois juntos criariam um array dentro de um array - o texto inteiro voltaria
    # a ser um unico segmento e a espera voltaria com ele.
    return $segs.ToArray()
}

function Get-ItensHistorico {
    if (-not (Test-Path $HistPath)) { return @() }
    try {
        $bruto = [System.IO.File]::ReadAllText($HistPath, [System.Text.Encoding]::UTF8)
    } catch { return @() }
    return @($bruto -split [regex]::Escape($Separador) | ForEach-Object { $_.Trim() } | Where-Object { $_ })
}

function Add-Historico([string]$texto) {
    if ([string]::IsNullOrWhiteSpace($texto)) { return }
    $itens = @($texto) + (Get-ItensHistorico)
    if ($itens.Count -gt $MaxHist) { $itens = $itens[0..($MaxHist - 1)] }
    [System.IO.File]::WriteAllText($HistPath, ($itens -join "`n$Separador`n"), $Utf8SemBom)
}

# Converte "+12%" para "-13%" quando o usuario pede repeticao mais lenta.
function Get-RateMaisLento([string]$rate) {
    $n = 0
    if ($rate -match '^([+-]?\d+)%$') { $n = [int]$Matches[1] }
    $n = $n - 25
    if ($n -lt -40) { $n = -40 }
    if ($n -ge 0) { return "+$n%" }
    return "$n%"
}

# ------------------------------------------------------- controle do audio

# 'tocar' | 'pausado' | 'cancelar'. O processo que reproduz le isso em laco.
function Get-Controle {
    if (-not (Test-Path $ControlePath)) { return 'tocar' }
    try { $v = ([System.IO.File]::ReadAllText($ControlePath)).Trim().ToLower() } catch { return 'tocar' }
    if (@('tocar', 'pausado', 'cancelar') -contains $v) { return $v }
    return 'tocar'
}

function Set-Controle([string]$estado) {
    [System.IO.File]::WriteAllText($ControlePath, $estado, $Utf8SemBom)
}

function Switch-Pausa {
    $novo = if ((Get-Controle) -eq 'pausado') { 'tocar' } else { 'pausado' }
    Set-Controle $novo
    return $novo
}

# ------------------------------------------------------- fila de pendencia
#
# Uma pasta com um arquivo por resumo, nome ordenavel pelo instante de criacao.
# Tem que ser uma fila, e nao um arquivo unico: todas as sessoes do Claude Code
# compartilham esta pasta, e com arquivo unico a sessao que termina depois apaga
# o resumo da que terminou antes - o usuario nunca ouve o primeiro.

$MaxFila = 20

function Get-ArquivosFila {
    Import-PendenteLegado
    if (-not (Test-Path $FilaDir)) { return @() }
    return @(Get-ChildItem -Path $FilaDir -Filter '*.json' -File -ErrorAction SilentlyContinue | Sort-Object Name)
}

# Aproveita o pendente.txt de uma instalacao anterior em vez de descarta-lo.
function Import-PendenteLegado {
    if (-not (Test-Path $PendenteLegado)) { return }
    try {
        $t = [System.IO.File]::ReadAllText($PendenteLegado, [System.Text.Encoding]::UTF8)
        Remove-Item $PendenteLegado -Force -ErrorAction SilentlyContinue
        Add-Pendente $t ''
    } catch { }
}

function Add-Pendente([string]$texto, [string]$projeto) {
    if ([string]::IsNullOrWhiteSpace($texto)) { return }
    if (-not (Test-Path $FilaDir)) { New-Item -ItemType Directory -Force $FilaDir | Out-Null }

    # Duas sessoes podem terminar no mesmo milissegundo, e o relogio do Windows
    # tem granularidade grossa demais para separa-las - Import-Entradas ainda
    # enfileira todas as caixas em laco, no mesmo processo. Medido: 34% dos
    # pares caem no mesmo milissegundo. Com o guid aleatorio como unico
    # desempate, a fila saia invertida em 22% das vezes; o contador preserva a
    # ordem de chegada e o guid fica so para evitar colisao entre processos.
    $ms = (Get-Date).ToString('yyyyMMddHHmmssfff')
    $seq = @(Get-ChildItem -Path $FilaDir -Filter "$ms-*.json" -File -ErrorAction SilentlyContinue).Count
    $nome = "$ms-$('{0:d3}' -f $seq)-$([guid]::NewGuid().ToString('N').Substring(0,8)).json"
    $dados = [pscustomobject]@{ projeto = $projeto; texto = $texto }
    [System.IO.File]::WriteAllText((Join-Path $FilaDir $nome), ($dados | ConvertTo-Json -Depth 3), $Utf8SemBom)

    $arquivos = @(Get-ChildItem -Path $FilaDir -Filter '*.json' -File | Sort-Object Name)
    if ($arquivos.Count -gt $MaxFila) {
        $arquivos[0..($arquivos.Count - $MaxFila - 1)] | Remove-Item -Force -ErrorAction SilentlyContinue
    }
}

function Get-PendenteCount {
    return (Get-ArquivosFila).Count
}

function Test-Pendente {
    return (Get-ArquivosFila).Count -gt 0
}

# Le o conteudo de um arquivo da fila. Devolve $null se veio corrompido.
function Read-DadosFila($arquivo) {
    try {
        return [System.IO.File]::ReadAllText($arquivo.FullName, [System.Text.Encoding]::UTF8) | ConvertFrom-Json
    } catch {
        return $null
    }
}

# Entrega um resumo para leitura, sem apaga-lo. Com -Projeto, entrega o mais
# recente daquele projeto em vez do mais recente da fila.
#
# O resumo so sai do disco quando a fala termina de verdade (Complete-Leitura).
# Antes, o arquivo era apagado no momento da entrega: quem cancelasse ao ouvir
# "no projeto tal" e perceber que era o projeto errado perdia aquele resumo para
# sempre. Cacar o resumo certo destruia todos os que passavam na frente.
function Read-Pendente {
    param([string]$Projeto = '')

    # Uma leitura anterior que nao terminou devolve o resumo para a fila: se o
    # processo que falava foi morto, ninguem chamou Complete nem Abort. Assim o
    # pior caso e ouvir o mesmo resumo de novo, nunca perde-lo.
    Abort-Leitura | Out-Null

    $arquivos = Get-ArquivosFila
    if ($arquivos.Count -eq 0) { return $null }

    $alvo  = $null
    $dados = $null

    if ($Projeto) {
        $busca = $Projeto.ToLower()
        for ($i = $arquivos.Count - 1; $i -ge 0; $i--) {
            $d = Read-DadosFila $arquivos[$i]
            if (-not $d) { continue }
            $nome = [string]$d.projeto
            # Nome parcial serve: digitar "concil" tem de achar a conciliacao.
            if ($nome -and $nome.ToLower().Contains($busca)) {
                $alvo = $arquivos[$i]; $dados = $d; break
            }
        }
        if (-not $alvo) { return $null }
    } else {
        $alvo  = $arquivos[-1]
        $dados = Read-DadosFila $alvo
        if (-not $dados) {
            Remove-Item $alvo.FullName -Force -ErrorAction SilentlyContinue
            return $null
        }
    }

    [System.IO.File]::WriteAllText($EmLeituraPath, $alvo.Name, $Utf8SemBom)
    return @{
        texto     = [string]$dados.texto
        projeto   = [string]$dados.projeto
        restantes = $arquivos.Count - 1
    }
}

# A fala chegou ao fim: agora o resumo pode sair da fila.
function Complete-Leitura {
    if (-not (Test-Path $EmLeituraPath)) { return $false }
    try { $nome = ([System.IO.File]::ReadAllText($EmLeituraPath)).Trim() } catch { $nome = '' }
    Remove-Item $EmLeituraPath -Force -ErrorAction SilentlyContinue
    if (-not $nome) { return $false }
    $alvo = Join-Path $FilaDir $nome
    if (Test-Path $alvo) {
        Remove-Item $alvo -Force -ErrorAction SilentlyContinue
        return $true
    }
    return $false
}

# A fala foi cortada: o resumo continua na fila esperando a vez.
function Abort-Leitura {
    if (-not (Test-Path $EmLeituraPath)) { return $false }
    Remove-Item $EmLeituraPath -Force -ErrorAction SilentlyContinue
    return $true
}

# Quem esta esperando e quantos resumos cada um deixou, do mais recente para o
# mais antigo. E o que a triagem falada anuncia.
function Get-ResumoDaFila {
    $ordem  = New-Object System.Collections.ArrayList
    $contas = @{}
    $arquivos = Get-ArquivosFila
    for ($i = $arquivos.Count - 1; $i -ge 0; $i--) {
        $d = Read-DadosFila $arquivos[$i]
        if (-not $d) { continue }
        $nome = if ($d.projeto) { [string]$d.projeto } else { 'sem nome' }
        if (-not $contas.ContainsKey($nome)) {
            $contas[$nome] = 0
            [void]$ordem.Add($nome)
        }
        $contas[$nome] = $contas[$nome] + 1
    }
    $saida = New-Object System.Collections.ArrayList
    foreach ($n in $ordem) { [void]$saida.Add(@{ projeto = $n; quantos = $contas[$n] }) }
    return $saida.ToArray()
}

# Traduz um numero pequeno para palavra, para a voz nao soletrar digito.
function Get-PorExtenso([int]$n) {
    if ($NumeroPorExtenso.ContainsKey($n)) { return $NumeroPorExtenso[$n] }
    return "$n"
}

# Quantos nomes a triagem cita antes de resumir o resto. Medido com a fila real:
# listar seis projetos com a contagem de cada um dava 334 caracteres, uns 25
# segundos so para anunciar a lista - ouvir isso a cada leitura seria pior que o
# problema que a triagem resolve.
$MaxNomesTriagem = 5

# A frase que a Clarisse fala antes de ler, quando ha mais de um projeto na fila.
# Diz os totais e os nomes, nao a contagem de cada projeto: o que o usuario
# precisa para escolher e saber quem esta esperando, e o resto ele ouve depois.
# O hifen sai porque nome de pasta soletrado em voz alta e ilegivel.
function Format-FalaTriagem($itens) {
    $lista = @($itens)
    if ($lista.Count -eq 0) { return '' }

    $n = $lista.Count
    $total = 0
    foreach ($i in $lista) { $total += [int]$i.quantos }

    $citados = @($lista | Select-Object -First $MaxNomesTriagem |
                 ForEach-Object { ([string]$_.projeto).Replace('-', ' ') })
    $sobram = $n - $citados.Count

    if ($citados.Count -eq 1) {
        $nomes = $citados[0]
    } else {
        # "alfa, beta e gama" soa melhor que "alfa, beta, gama".
        $nomes = ($citados[0..($citados.Count - 2)] -join ', ') + " e $($citados[-1])"
    }
    if ($sobram -gt 0) {
        # "e mais um" solto soa como mais um resumo; o que sobra e projeto.
        $pSobra = if ($sobram -eq 1) { 'projeto' } else { 'projetos' }
        $nomes = ($citados -join ', ') + ", e mais $(Get-PorExtenso $sobram) $pSobra"
    }

    $pProj = if ($n -eq 1)     { 'projeto' } else { 'projetos' }
    $pRes  = if ($total -eq 1) { 'resumo' }  else { 'resumos' }
    return "$(Get-PorExtenso $n) $pProj esperando, $(Get-PorExtenso $total) ${pRes}: $nomes."
}

# O nome do projeto como a voz deve dizer: hifen soletrado em voz alta e
# ilegivel, e "velocimetro-tokens" sai como "velocimetro traco tokens".
function Format-FalaProjeto([string]$projeto) {
    if ([string]::IsNullOrWhiteSpace($projeto)) { return '' }
    return $projeto.Replace('-', ' ')
}

# ------------------------------------------------------- modo selecao
#
# Com varios projetos na fila, o atalho de leitura anuncia quem esta esperando e
# entra em modo selecao: uma tecla passeia pelos projetos e a de leitura confirma.
# Passear nao consome nem apaga nada.

function Get-Selecao {
    if (-not (Test-Path $SelecaoPath)) { return '' }
    try { $nome = ([System.IO.File]::ReadAllText($SelecaoPath)).Trim() } catch { return '' }
    if (-not $nome) { return '' }
    # Sem virgula em @() aqui: Get-ProjetosNaFila ja devolve o array protegido,
    # e envolver de novo criaria array dentro de array.
    $projetos = Get-ProjetosNaFila
    if ($projetos -notcontains $nome) {
        # A selecao expira junto com o motivo dela existir.
        Clear-Selecao
        return ''
    }
    return $nome
}

function Set-Selecao([string]$projeto) {
    [System.IO.File]::WriteAllText($SelecaoPath, $projeto, $Utf8SemBom)
}

function Clear-Selecao {
    Remove-Item $SelecaoPath -Force -ErrorAction SilentlyContinue
}

function Start-Selecao {
    $projetos = Get-ProjetosNaFila
    if ($projetos.Count -eq 0) { Clear-Selecao; return '' }
    Set-Selecao $projetos[0]
    return $projetos[0]
}

# Passa para o proximo projeto, dando a volta no fim da lista.
function Move-Selecao {
    $projetos = Get-ProjetosNaFila
    if ($projetos.Count -eq 0) { Clear-Selecao; return '' }
    $atual = Get-Selecao
    $i = [array]::IndexOf([array]$projetos, $atual)
    $prox = if ($i -lt 0) { 0 } else { ($i + 1) % $projetos.Count }
    Set-Selecao $projetos[$prox]
    return $projetos[$prox]
}

# ------------------------------------------------- caixa de entrada por projeto
#
# O Claude escreve o resumo aqui, num arquivo com o nome do projeto. Nao pode
# ser um arquivo unico: as sessoes compartilham esta pasta e a que escreve por
# ultimo apagaria o resumo da anterior antes de qualquer hook ler.
#
# O nome do arquivo e a fonte da verdade sobre a origem. Por isso o hook recolhe
# TODAS as caixas, e nao so a do proprio projeto: qualquer sessao que termine
# recolhe o que estiver parado, sempre com a atribuicao certa, e nada fica preso
# esperando aquela sessao especifica terminar de novo.

function Get-CaminhoEntrada([string]$projeto) {
    if ([string]::IsNullOrWhiteSpace($projeto)) { return '' }
    $limpo = $projeto
    foreach ($c in [System.IO.Path]::GetInvalidFileNameChars()) { $limpo = $limpo.Replace($c, '-') }
    return (Join-Path $EntradaDir "$limpo.txt")
}

# Move tudo que esta na caixa de entrada para a fila de leitura.
# Devolve o que enfileirou, para o chamador historiar e decidir se bipa.
function Import-Entradas {
    $novos = New-Object System.Collections.ArrayList

    if (Test-Path $EntradaDir) {
        $caixas = @(Get-ChildItem -Path $EntradaDir -Filter '*.txt' -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime)
        foreach ($caixa in $caixas) {
            try { $texto = [System.IO.File]::ReadAllText($caixa.FullName, [System.Text.Encoding]::UTF8) } catch { continue }
            Remove-Item $caixa.FullName -Force -ErrorAction SilentlyContinue
            if ([string]::IsNullOrWhiteSpace($texto)) { continue }
            Add-Pendente $texto $caixa.BaseName
            [void]$novos.Add(@{ projeto = $caixa.BaseName; texto = $texto })
        }
    }

    # fala.txt de uma instalacao anterior: entra sem projeto, porque nao da para
    # saber de qual sessao veio - e etiqueta errada e pior que etiqueta nenhuma.
    if (Test-Path $FalaPath) {
        try { $texto = [System.IO.File]::ReadAllText($FalaPath, [System.Text.Encoding]::UTF8) } catch { $texto = '' }
        Remove-Item $FalaPath -Force -ErrorAction SilentlyContinue
        if (-not [string]::IsNullOrWhiteSpace($texto)) {
            Add-Pendente $texto ''
            [void]$novos.Add(@{ projeto = ''; texto = $texto })
        }
    }

    # A virgula impede o PowerShell de desembrulhar array de um elemento so,
    # o que faria .Count devolver o numero de chaves do hashtable.
    return ,$novos.ToArray()
}

# Quem esta esperando, do mais recente para o mais antigo, sem repetir projeto.
function Get-ProjetosNaFila {
    $nomes = New-Object System.Collections.ArrayList
    $arquivos = Get-ArquivosFila
    for ($i = $arquivos.Count - 1; $i -ge 0; $i--) {
        try { $dados = [System.IO.File]::ReadAllText($arquivos[$i].FullName, [System.Text.Encoding]::UTF8) | ConvertFrom-Json } catch { continue }
        $nome = if ($dados.projeto) { [string]$dados.projeto } else { 'sem nome' }
        if (-not $nomes.Contains($nome)) { [void]$nomes.Add($nome) }
    }
    return ,$nomes.ToArray()
}

# Vai ate vinte porque vinte e o teto da fila. Digito solto na fala sai lido de
# formas imprevisiveis, entao todo numero que o sistema pode produzir tem de ter
# palavra aqui.
$NumeroPorExtenso = @{
    1 = 'um';    2 = 'dois';    3 = 'tres';    4 = 'quatro';   5 = 'cinco'
    6 = 'seis';  7 = 'sete';    8 = 'oito';    9 = 'nove';    10 = 'dez'
    11 = 'onze'; 12 = 'doze';  13 = 'treze';  14 = 'quatorze'; 15 = 'quinze'
    16 = 'dezesseis'; 17 = 'dezessete'; 18 = 'dezoito'; 19 = 'dezenove'; 20 = 'vinte'
}

# Monta o que sai pela voz: de onde veio, o resumo, e quantos ainda esperam.
function Format-FalaPendente($item) {
    $t = $item.texto
    if ($item.projeto) { $t = "No projeto $($item.projeto): $t" }
    $n = [int]$item.restantes
    if ($n -eq 1) {
        $t = "$t Tem mais um resumo esperando."
    } elseif ($n -gt 1) {
        $q = if ($NumeroPorExtenso.ContainsKey($n)) { $NumeroPorExtenso[$n] } else { "$n" }
        $t = "$t Tem mais $q resumos esperando."
    }
    return $t
}

# Com varias sessoes abertas, "estou esperando sua resposta" nao diz nada:
# o usuario precisa saber para qual terminal ir.
function Format-FalaNotificacao([string]$msg, [string]$projeto) {
    if ([string]::IsNullOrWhiteSpace($msg)) { return '' }
    $traducoes = @(
        @{ chave = 'needs your permission';  comProjeto = 'precisa da sua permissao para continuar.'; sozinho = 'Preciso da sua permissao para continuar.' },
        @{ chave = 'waiting for your input'; comProjeto = 'esta esperando sua resposta.';             sozinho = 'Estou esperando sua resposta.' },
        @{ chave = 'is waiting';             comProjeto = 'esta esperando sua resposta.';             sozinho = 'Estou esperando sua resposta.' }
    )
    foreach ($t in $traducoes) {
        if ($msg -like "*$($t.chave)*") {
            if ($projeto) { return "O projeto $projeto $($t.comProjeto)" }
            return $t.sozinho
        }
    }
    if ($projeto) { return "No projeto ${projeto}: $msg" }
    return $msg
}

function Get-NomeProjeto([string]$cwd) {
    if ([string]::IsNullOrWhiteSpace($cwd)) { return '' }
    try { return Split-Path -Leaf $cwd.TrimEnd('\', '/') } catch { return '' }
}

# O Claude Code manda um JSON no stdin dos hooks, com o diretorio da sessao.
function Get-CwdDoHook([string]$bruto) {
    if ([string]::IsNullOrWhiteSpace($bruto)) { return '' }
    try {
        $dados = $bruto | ConvertFrom-Json
        if ($dados.cwd) { return [string]$dados.cwd }
    } catch { }
    return ''
}

# O texto que o usuario enviou, depois de revisar o que o ditado digitou. E a
# outra metade do par que o diario mede.
function Get-PromptDoHook([string]$bruto) {
    if ([string]::IsNullOrWhiteSpace($bruto)) { return '' }
    try {
        $dados = $bruto | ConvertFrom-Json
        if ($dados.prompt) { return [string]$dados.prompt }
    } catch { }
    return ''
}

# Le o stdin sem travar quando o script e chamado a mao num terminal.
function Read-StdinDoHook {
    try {
        if (-not [Console]::IsInputRedirected) { return '' }
        return [Console]::In.ReadToEnd()
    } catch { return '' }
}

# Aviso curto de "tem resumo esperando". Silencioso se o hardware recusar.
function Send-Bipe {
    try {
        [console]::Beep(880, 120)
        [console]::Beep(1175, 160)
    } catch { }
}

# ------------------------------------------------------- atalhos de teclado

# Traduz "Ctrl+Alt+L" nos codigos que o RegisterHotKey do Win32 espera.
# MOD_ALT=1 MOD_CONTROL=2 MOD_SHIFT=4 MOD_WIN=8 MOD_NOREPEAT=0x4000
function ConvertTo-CodigoAtalho([string]$combinacao) {
    if ([string]::IsNullOrWhiteSpace($combinacao)) { return $null }
    Add-Type -AssemblyName System.Windows.Forms
    $mods = @{ 'ctrl' = 2; 'control' = 2; 'alt' = 1; 'shift' = 4; 'win' = 8; 'windows' = 8 }
    $mod = 0
    $tecla = $null
    foreach ($parte in ($combinacao -split '\+')) {
        $p = $parte.Trim().ToLower()
        if (-not $p) { continue }
        if ($mods.ContainsKey($p)) { $mod = $mod -bor $mods[$p] }
        elseif ($tecla) { return $null }
        else { $tecla = $p }
    }
    if ($mod -eq 0 -or -not $tecla) { return $null }
    try { $vk = [int]([Enum]::Parse([System.Windows.Forms.Keys], $tecla, $true)) } catch { return $null }
    return @{ mod = ($mod -bor 0x4000); vk = $vk }
}

function Test-AtalhosAtivos {
    if (-not (Test-Path $AtalhosPidPath)) { return $false }
    try { $id = [int](Get-Content $AtalhosPidPath -Raw).Trim() } catch { return $false }
    $proc = Get-Process -Id $id -ErrorAction SilentlyContinue
    if ($proc -and $proc.ProcessName -like 'powershell*') { return $true }
    Remove-Item $AtalhosPidPath -Force -ErrorAction SilentlyContinue
    return $false
}

# Sobe o escutador. Com -Aguardar, espera ele confirmar que registrou as teclas
# (a compilacao do codigo nativo leva alguns segundos na primeira vez) e devolve
# $false se o Windows recusou as combinacoes.
function Start-Atalhos([switch]$Aguardar) {
    Start-Process -FilePath 'powershell.exe' `
        -ArgumentList '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-ExecutionPolicy', 'Bypass', '-File', "`"$(Join-Path $Root 'atalhos.ps1')`"" `
        -WindowStyle Hidden | Out-Null
    if (-not $Aguardar) { return $true }
    $limite = [datetime]::Now.AddSeconds(20)
    while ([datetime]::Now -lt $limite) {
        if (Test-AtalhosAtivos) { return $true }
        Start-Sleep -Milliseconds 400
    }
    return $false
}

function Stop-Atalhos {
    if (-not (Test-AtalhosAtivos)) { return $false }
    try {
        $id = [int](Get-Content $AtalhosPidPath -Raw).Trim()
        Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
    } catch { }
    Remove-Item $AtalhosPidPath -Force -ErrorAction SilentlyContinue
    return $true
}

# ------------------------------------------------------------- reproducao

# ------------------------------------------------- sintese progressiva
#
# O texto vai para um script Python que sintetiza segmento por segmento, e a
# reproducao acontece aqui, na ordem em que cada pedaco fica pronto. Assim a
# fala comeca em cerca de dois segundos em vez de esperar o audio inteiro:
# sintetizar e cerca de tres vezes mais rapido que falar, entao depois do
# primeiro segmento a geracao sempre corre na frente da voz.
#
# O sinal de "pode tocar" e a sentinela .ok, escrita somente depois de o mp3
# ser fechado. A existencia do mp3 nao serve: um arquivo ainda em gravacao abre
# no player com duracao errada e a fala corta no meio.

function Get-CaminhoSegmento([string]$pasta, [int]$indice) {
    return (Join-Path $pasta ('seg{0:d3}.mp3' -f $indice))
}

function Get-CaminhoSentinela([string]$pasta, [int]$indice) {
    return (Join-Path $pasta ('seg{0:d3}.ok' -f $indice))
}

function Test-SegmentoPronto([string]$pasta, [int]$indice) {
    if (-not (Test-Path (Get-CaminhoSentinela $pasta $indice))) { return $false }
    return [bool](Test-Path (Get-CaminhoSegmento $pasta $indice))
}

# Espera o proximo pedaco de audio. Devolve 'pronto', 'erro', 'timeout' ou
# 'cancelado'. A ordem das checagens importa: um segmento que ja esta pronto
# vale mesmo que o Python tenha falhado num segmento posterior.
function Wait-SegmentoPronto([string]$pasta, [int]$indice, [int]$timeoutSegundos) {
    $limite = [datetime]::Now.AddSeconds($timeoutSegundos)
    while ($true) {
        if (Test-SegmentoPronto $pasta $indice)      { return 'pronto' }
        if ((Get-Controle) -eq 'cancelar')           { return 'cancelado' }
        if (Test-Path (Join-Path $pasta 'erro.txt')) { return 'erro' }
        if ([datetime]::Now -ge $limite)             { return 'timeout' }
        Start-Sleep -Milliseconds 60
    }
}

function Stop-Reproducao {
    if (-not (Test-Path $PidPath)) { return $false }
    $parou = $false
    try {
        $id = [int](Get-Content $PidPath -Raw).Trim()
        $proc = Get-Process -Id $id -ErrorAction SilentlyContinue
        if ($proc -and $proc.ProcessName -like 'powershell*' -and $id -ne $PID) {
            Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
            $parou = $true
        }
    } catch { }
    Remove-Item $PidPath -Force -ErrorAction SilentlyContinue
    return $parou
}

# Corta a fala em curso. Grava o pedido de cancelamento (o laco de reproducao
# responde em ate 120ms) e, se o edge-tts ainda estiver gerando o audio numa
# chamada bloqueante, mata o processo.
function Stop-Fala {
    Set-Controle 'cancelar'
    Start-Sleep -Milliseconds 350
    $matou = Stop-Reproducao
    Set-Controle 'tocar'
    return $matou
}

# Toca um pedaco de audio ate o fim, obedecendo pausa e cancelamento.
# Devolve 'fim', 'cancelado' ou 'ilegivel' - o laco de reproducao trata os tres
# de formas diferentes, e um booleano nao daria para distinguir.
function Invoke-TocaArquivo([string]$mp3) {
    # Antes de abrir o arquivo, para o Ctrl+Alt+X responder na hora em vez de
    # esperar o pedaco atual carregar.
    if ((Get-Controle) -eq 'cancelar') { return 'cancelado' }
    if (-not (Test-Path $mp3))         { return 'ilegivel' }

    Add-Type -AssemblyName PresentationCore
    $player = New-Object System.Windows.Media.MediaPlayer
    try {
        $player.Open([uri]$mp3)
        # O MediaPlayer carrega o arquivo de forma assincrona e nao lanca erro
        # em arquivo invalido: a duracao nunca aparecer e o sinal de que veio
        # corrompido.
        $espera = 0
        while (-not $player.NaturalDuration.HasTimeSpan -and $espera -lt 60) {
            Start-Sleep -Milliseconds 50
            $espera++
        }
        if (-not $player.NaturalDuration.HasTimeSpan) { return 'ilegivel' }
        $dur = $player.NaturalDuration.TimeSpan.TotalSeconds

        $player.Play()
        $pausado = $false
        # Trava de seguranca: uma pausa esquecida nao pode prender o mutex.
        $limite = [datetime]::Now.AddMinutes(20)
        while ($player.Position.TotalSeconds -lt $dur -and [datetime]::Now -lt $limite) {
            switch (Get-Controle) {
                'cancelar' { return 'cancelado' }
                'pausado'  { if (-not $pausado) { $player.Pause(); $pausado = $true } }
                'tocar'    { if ($pausado)      { $player.Play();  $pausado = $false } }
            }
            Start-Sleep -Milliseconds 120
        }
        # Evita cortar a ultima silaba; entre segmentos soa como pausa de frase.
        Start-Sleep -Milliseconds 120
        return 'fim'
    } finally {
        $player.Stop()
        $player.Close()
    }
}

# Gera o audio e toca. Bloqueia ate terminar; um mutex evita falas sobrepostas.
#
# A sintese acontece em pedacos, num processo Python a parte, e a reproducao
# comeca no primeiro pedaco em vez de esperar o audio inteiro. Medido num resumo
# de mil e quinhentos caracteres: 33 segundos de espera antes, cerca de dois
# depois. Sintetizar e umas tres vezes mais rapido que falar, entao a geracao
# corre na frente da voz e nao engasga entre os pedacos.
function Invoke-Fala {
    param(
        [string]$texto,
        [string]$RateOverride = '',
        [switch]$PularHistorico,
        [switch]$RespeitaEnabled
    )
    $cfg = Get-Config
    $falavel = ConvertTo-Falavel $texto $cfg.maxChars
    if ([string]::IsNullOrWhiteSpace($falavel)) { return 'vazio' }

    $inv = Get-PythonInvocacao $cfg
    if (-not $inv) {
        Write-Log 'Python nao encontrado. Defina o caminho no campo "python" do config.json.'
        return 'erro'
    }

    $rate = if ($RateOverride) { $RateOverride } else { $cfg.rate }

    $mutex = New-Object System.Threading.Mutex($false, 'Global\ClarisseVoz')
    $obteve = $false
    try {
        $obteve = $mutex.WaitOne(60000)
        if (-not $PularHistorico) { Add-Historico $falavel }

        # O PID vai para o disco antes da sintese: cancelar precisa interromper
        # tambem enquanto o audio ainda esta sendo gerado.
        [System.IO.File]::WriteAllText($PidPath, "$PID", $Utf8SemBom)

        $segmentos = @(Split-EmSegmentos -Texto $falavel)
        if ($segmentos.Count -eq 0) { return 'vazio' }

        $pasta = Join-Path $env:TEMP "clarisse_$([guid]::NewGuid().ToString('N'))"
        New-Item -ItemType Directory -Force $pasta | Out-Null
        $proc = $null
        try {
            [System.IO.File]::WriteAllLines((Join-Path $pasta 'segmentos.txt'), $segmentos, $Utf8SemBom)

            $argumentos = $inv.pre + @(
                (Join-Path $Root 'falar.py'),
                '--pasta',  $pasta,
                '--voz',    $cfg.voice,
                '--rate',   $rate,
                '--volume', $cfg.volume
            )
            $proc = Start-Process -FilePath $inv.exe -ArgumentList $argumentos -WindowStyle Hidden -PassThru

            # A voz pode ter sido desligada enquanto o audio era gerado.
            if ($RespeitaEnabled -and -not (Get-Config).enabled) { return 'mudo' }

            Set-Controle 'tocar'
            # Comeca em 'fim' e so piora: quem chamou usa isso para decidir se o
            # resumo ja pode sair da fila ou se continua esperando a vez.
            $resultado = 'fim'
            for ($i = 0; $i -lt $segmentos.Count; $i++) {
                # O primeiro pedaco e o unico que espera de verdade; os
                # seguintes ja estao prontos quando chega a vez deles.
                $estado = Wait-SegmentoPronto $pasta $i 120
                if ($estado -ne 'pronto') {
                    if ($estado -eq 'erro') {
                        $msg = try { [System.IO.File]::ReadAllText((Join-Path $pasta 'erro.txt')) } catch { 'desconhecido' }
                        Write-Log "sintese falhou no segmento ${i}: $msg"
                    } elseif ($estado -eq 'timeout') {
                        Write-Log "segmento $i nao ficou pronto no prazo"
                    }
                    $resultado = if ($estado -eq 'cancelado') { 'cancelado' } else { 'erro' }
                    break
                }
                $tocou = Invoke-TocaArquivo (Get-CaminhoSegmento $pasta $i)
                if ($tocou -ne 'fim') { $resultado = $tocou; break }
            }
            Set-Controle 'tocar'
            return $resultado
        } finally {
            # parar.txt antes de matar: se o processo escapar, ele mesmo desiste
            # no proximo segmento em vez de seguir baixando audio perdido.
            try { [System.IO.File]::WriteAllText((Join-Path $pasta 'parar.txt'), '') } catch { }
            if ($proc -and -not $proc.HasExited) {
                Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
            }
            Remove-Item $PidPath -Force -ErrorAction SilentlyContinue
            Remove-Item $pasta -Recurse -Force -ErrorAction SilentlyContinue
        }
    } finally {
        if ($obteve) { $mutex.ReleaseMutex() }
        $mutex.Dispose()
    }
}

# Dispara a fala num processo separado para nao travar o Claude Code.
# O sufixo .nohist no nome do arquivo diz ao processo filho para nao historiar
# de novo um texto que ja foi guardado no historico.
# Dispara um modo do clarisse.ps1 em outro processo. O escutador de atalhos usa
# isso para nao duplicar a logica de leitura: ela vive num lugar so, e o laco de
# mensagens do escutador volta na hora em vez de esperar a fala.
function Start-Modo([string]$modo, [string]$projeto = '') {
    # Nao usar $args aqui: e variavel automatica do PowerShell.
    $argumentos = @('-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-ExecutionPolicy', 'Bypass', '-File', "`"$(Join-Path $Root 'clarisse.ps1')`"", '-Mode', $modo)
    if ($projeto) { $argumentos += @('-Projeto', "`"$projeto`"") }
    Start-Process -FilePath 'powershell.exe' -ArgumentList $argumentos -WindowStyle Hidden | Out-Null
}

# Sobe o servidor residente do Ouvinte, se ele ainda nao estiver de pe.
#
# Quem decide se ja ha um e o proprio servidor, pela trava de PID: sao ~10
# sessoes rodando o SessionStart, e dez modelos carregados seriam ~6 GB de RAM
# disputando o mesmo microfone. Aqui a gente so tenta; o segundo sai calado.
function Start-Ouvinte($cfg) {
    $inv = Get-PythonInvocacao $cfg
    if (-not $inv) {
        Write-Log 'ouvinte nao subiu: nenhum Python encontrado'
        return $false
    }
    $argumentos = $inv.pre + @('-m', 'clarisse.ouvinte.servidor')
    Start-Process -FilePath $inv.exe -ArgumentList $argumentos `
        -WorkingDirectory (Split-Path $Root -Parent) -WindowStyle Hidden | Out-Null
    return $true
}

# O sufixo .fila no nome do arquivo diz ao processo filho que esta fala consome
# um item da fila: se ela chegar ao fim, o resumo sai; se for cortada, volta.
function Start-FalaAssincrona([string]$texto, [switch]$PularHistorico, [switch]$ConsomeFila) {
    if ([string]::IsNullOrWhiteSpace($texto)) { return }
    if (-not (Test-Path $PendDir)) { New-Item -ItemType Directory -Force $PendDir | Out-Null }
    $sufixo = ''
    if ($PularHistorico) { $sufixo += '.nohist' }
    if ($ConsomeFila)    { $sufixo += '.fila' }
    $arq = Join-Path $PendDir ("$([guid]::NewGuid().ToString('N'))$sufixo.txt")
    [System.IO.File]::WriteAllText($arq, $texto, $Utf8SemBom)
    Start-Process -FilePath 'powershell.exe' `
        -ArgumentList '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-ExecutionPolicy', 'Bypass', '-File', "`"$(Join-Path $Root 'clarisse.ps1')`"", '-Mode', 'speak', '-File', "`"$arq`"" `
        -WindowStyle Hidden | Out-Null
}

# --- Ouvinte: o texto ditado chega na janela em foco ------------------------

# Descobre de qual projeto e a janela que vai receber o texto.
#
# O servidor do Ouvinte e um por maquina e nao sabe onde o usuario esta. A unica
# pista disponivel e o titulo da janela em foco: o Windows Terminal mostra o
# titulo da aba ativa, e ele costuma vir cortado - a aba do financeiro-areceber
# aparece so como "areceber". Dai o casamento por pedaco, igual ao que o
# Read-Pendente -Projeto ja faz.
#
# Titulo curto demais nao casa: duas letras casariam com quase todo projeto, e
# marcar o turno do projeto errado faria a Clarisse falar na sessao errada.
function Resolve-ProjetoDoTitulo([string]$titulo, $projetos) {
    if ([string]::IsNullOrWhiteSpace($titulo)) { return '' }
    if (-not $projetos)                        { return '' }

    $alvo = $titulo.Trim().ToLowerInvariant()
    if ($alvo.Length -lt 3) { return '' }

    $achados = @()
    foreach ($p in $projetos) {
        if ([string]::IsNullOrWhiteSpace($p)) { continue }
        $nome = $p.Trim().ToLowerInvariant()
        if ($alvo.Contains($nome) -or $nome.Contains($alvo)) { $achados += $p }
    }
    if (-not $achados) { return '' }

    # O nome mais longo e o mais especifico: entre "api" e "omni-api", quem casa
    # com os dois quis dizer o segundo.
    return ($achados | Sort-Object { $_.Length } -Descending | Select-Object -First 1)
}

function Get-TituloDaJanelaEmFoco {
    # O tipo e compilado aqui dentro, e nao no topo do arquivo: este nucleo e
    # carregado por todo hook, e compilar C# em cada Stop custaria caro por nada.
    if (-not ('ClarisseJanela' -as [type])) {
        Add-Type -Language CSharp -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using System.Text;

public static class ClarisseJanela {
    [DllImport("user32.dll")]
    public static extern IntPtr GetForegroundWindow();

    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder texto, int tamanho);

    public static string TituloEmFoco() {
        IntPtr janela = GetForegroundWindow();
        if (janela == IntPtr.Zero) { return ""; }
        StringBuilder texto = new StringBuilder(512);
        GetWindowText(janela, texto, texto.Capacity);
        return texto.ToString();
    }
}
'@
    }
    try { return [ClarisseJanela]::TituloEmFoco() } catch { return '' }
}

# Digita o texto na janela em foco, caractere por caractere, pelo SendInput.
#
# NAO vai pela area de transferencia. Medido em 26/08/2026: nesta maquina a area
# ficou indisponivel de forma persistente - leitura e escrita estouravam com
# "operacao de Area de Transferencia nao foi bem-sucedida" - e antes disso, em
# uso normal, falhava calada em 2 de 25 idas, deixando a area VAZIA. Ela e
# recurso disputado da maquina inteira, e o ditado nao pode depender de ganhar
# essa disputa. De quebra, some o risco de perder o que o usuario tinha copiado.
#
# O KEYEVENTF_UNICODE manda o codigo do caractere, e nao a tecla: e por isso que
# acento sai certo aqui e nao sai pelo SendKeys, que foi o motivo de o desenho
# original ter escolhido colar.
function Send-TextoUnicode([string]$texto) {
    if (-not ('ClarisseTeclado' -as [type])) {
        Add-Type -Language CSharp -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public static class ClarisseTeclado {
    const uint INPUT_KEYBOARD    = 1;
    const uint KEYEVENTF_KEYUP   = 0x0002;
    const uint KEYEVENTF_UNICODE = 0x0004;

    [StructLayout(LayoutKind.Sequential)]
    struct KEYBDINPUT {
        public ushort wVk;
        public ushort wScan;
        public uint   dwFlags;
        public uint   time;
        public IntPtr dwExtraInfo;
    }

    // O MOUSEINPUT nao e usado para nada aqui, e mesmo assim precisa existir: o
    // INPUT do Windows e uma uniao, e quem manda no tamanho dela e o MAIOR
    // membro. Com 32 bytes, o mouse e maior que o teclado, que tem 24.
    //
    // Declarando so o teclado, o Marshal.SizeOf devolvia 32 em 64 bits. O
    // Windows exige 40, recusava com ERROR_INVALID_PARAMETER, devolvia zero
    // eventos aceitos e NAO lancava excecao. Medido em 01/09/2026: o ditado
    // nunca digitou um caractere desde que foi escrito.
    [StructLayout(LayoutKind.Sequential)]
    struct MOUSEINPUT {
        public int    dx;
        public int    dy;
        public uint   mouseData;
        public uint   dwFlags;
        public uint   time;
        public IntPtr dwExtraInfo;
    }

    // O deslocamento 8 vale para 64 bits, que e onde os hooks rodam; em 32 bits
    // seria 4, e o Digitar recusa antes de mandar lixo para o teclado.
    [StructLayout(LayoutKind.Explicit)]
    struct INPUT {
        [FieldOffset(0)] public uint       type;
        [FieldOffset(8)] public KEYBDINPUT ki;
        [FieldOffset(8)] public MOUSEINPUT mi;
    }

    // Exposto para o teste: e o unico numero que separa "digitou" de "o Windows
    // recusou em silencio", e nenhum teste de dublê alcanca ele.
    public static int TamanhoInput() { return Marshal.SizeOf(typeof(INPUT)); }

    public static int UltimoErro = 0;

    [DllImport("user32.dll", SetLastError = true)]
    static extern uint SendInput(uint nInputs, INPUT[] pInputs, int cbSize);

    public static int Digitar(string texto) {
        if (IntPtr.Size != 8) {
            throw new NotSupportedException("O ditado precisa de PowerShell de 64 bits.");
        }
        if (string.IsNullOrEmpty(texto)) { return 0; }

        INPUT[] eventos = new INPUT[texto.Length * 2];
        for (int i = 0; i < texto.Length; i++) {
            eventos[i * 2].type       = INPUT_KEYBOARD;
            eventos[i * 2].ki.wScan   = texto[i];
            eventos[i * 2].ki.dwFlags = KEYEVENTF_UNICODE;

            eventos[i * 2 + 1].type       = INPUT_KEYBOARD;
            eventos[i * 2 + 1].ki.wScan   = texto[i];
            eventos[i * 2 + 1].ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP;
        }

        int aceitos = (int)SendInput((uint)eventos.Length, eventos, Marshal.SizeOf(typeof(INPUT)));
        UltimoErro = aceitos == eventos.Length ? 0 : Marshal.GetLastWin32Error();
        return aceitos;
    }
}
'@
    }
    return [ClarisseTeclado]::Digitar($texto)
}

# Ultima parada antes do texto virar tecla de verdade.
#
# A quebra de linha e barrada aqui de novo, mesmo o saneamento do Ouvinte ja
# tendo tirado: no prompt do Claude Code ela ENVIA a mensagem, e enviar e a unica
# coisa que este desenho nao pode fazer por engano. Ela vira espaco e o caso fica
# no log, porque quebra de linha chegando aqui significa que algo a montante
# quebrou.
function Send-TextoNaJanela {
    param(
        [string]$texto,
        [scriptblock]$Enviar = { param($t) Send-TextoUnicode $t }
    )
    if ([string]::IsNullOrWhiteSpace($texto)) { return $false }

    $limpo = $texto
    if ($limpo -match "[`r`n]") {
        Write-Log 'ditado chegou com quebra de linha - trocada por espaco antes de digitar'
        $limpo = ($limpo -replace "[`r`n]+", ' ').Trim()
    }

    # O SendInput devolve QUANTOS eventos entraram na fila, e nao um sim ou nao.
    # Ignorar esse numero foi o que escondeu, por uma semana inteira, um ditado
    # que nunca digitou nada: o diario registrava sucesso e a tela ficava vazia.
    $esperados = $limpo.Length * 2
    $aceitos = & $Enviar $limpo

    if ($aceitos -ne $esperados) {
        $motivo = ''
        if ('ClarisseTeclado' -as [type]) { $motivo = " (erro do Windows: $([ClarisseTeclado]::UltimoErro))" }
        Write-Log "ditado nao foi digitado: o Windows aceitou $aceitos de $esperados eventos$motivo"
        return $false
    }

    return $true
}

# --- Turno: quando a Clarisse pode falar sozinha ---------------------------
#
# Sao duas etapas. Ditar deixa um marcador SEM projeto, porque o servidor do
# Ouvinte e um por maquina e nao sabe em qual sessao o texto caiu. O prompt
# enviado logo depois da nome ao turno: o hook UserPromptSubmit sabe o cwd dele.
#
# O UserPromptSubmit nao abre turno sozinho, e isso e deliberado: ele dispara em
# todo prompt, inclusive digitado, e a Clarisse voltaria a falar nas dez sessoes
# abertas - exatamente o que foi corrigido em 21/08, depois de ela interromper
# uma reuniao. Ele so batiza um turno que o ditado ja abriu.

$DitadoValidadeS = 60    # entre soltar a tecla e apertar Enter
$TurnoValidadeS  = 900   # entre enviar o prompt e o Claude terminar

# O instante em segundos desde 1970. Nao passar por texto aqui e obrigatorio:
# a versao anterior convertia TotalSeconds em string e chamava [double]::Parse,
# e em maquina pt-BR o ponto decimal e lido como separador de milhar - o numero
# saia mil vezes maior, o [int] estourava e o hook morria inteiro, em silencio.
function Get-Agora { return [int][DateTimeOffset]::UtcNow.ToUnixTimeSeconds() }

function Get-CaminhoTurno([string]$projeto) {
    if ([string]::IsNullOrWhiteSpace($projeto)) { return '' }
    $limpo = $projeto
    foreach ($c in [System.IO.Path]::GetInvalidFileNameChars()) { $limpo = $limpo.Replace($c, '-') }
    return (Join-Path $TurnoDir "$limpo.txt")
}

function Read-Instante([string]$caminho) {
    # Instante ilegivel e tratado como marcador estragado: some, e nao vale.
    if (-not (Test-Path $caminho)) { return $null }
    try {
        $bruto = [System.IO.File]::ReadAllText($caminho).Trim()
        return [int]$bruto
    } catch {
        Remove-Item $caminho -Force -ErrorAction SilentlyContinue
        return $null
    }
}

# O ditado acabou de entregar texto na janela. Ainda nao se sabe de quem e.
function Set-DitadoRecente([int]$Agora = -1) {
    if ($Agora -lt 0) { $Agora = Get-Agora }
    if (-not (Test-Path $Root)) { New-Item -ItemType Directory -Force $Root | Out-Null }
    [System.IO.File]::WriteAllText($DitadoPath, "$Agora", $Utf8SemBom)
}

# O prompt foi enviado neste projeto. Se veio de um ditado recente, o turno abre.
function Resolve-TurnoDoProjeto([string]$Projeto, [int]$Agora = -1) {
    if ($Agora -lt 0) { $Agora = Get-Agora }

    $alvo = Get-CaminhoTurno $Projeto
    if (-not $alvo) { return $false }

    $ditado = Read-Instante $DitadoPath
    if ($null -eq $ditado) { return $false }

    # O ditado e gasto de qualquer jeito: velho ou aproveitado, ele nao pode
    # sobrar para abrir a boca de uma segunda sessao.
    Remove-Item $DitadoPath -Force -ErrorAction SilentlyContinue

    $idade = $Agora - $ditado
    if ($idade -lt 0 -or $idade -gt $DitadoValidadeS) { return $false }

    if (-not (Test-Path $TurnoDir)) { New-Item -ItemType Directory -Force $TurnoDir | Out-Null }
    [System.IO.File]::WriteAllText($alvo, "$Agora", $Utf8SemBom)
    return $true
}

# O Claude terminou neste projeto. Pode falar na hora?
function Read-Turno([string]$Projeto, [int]$Agora = -1) {
    if ($Agora -lt 0) { $Agora = Get-Agora }

    $alvo = Get-CaminhoTurno $Projeto
    if (-not $alvo) { return $false }

    $marcado = Read-Instante $alvo
    if ($null -eq $marcado) { return $false }

    Remove-Item $alvo -Force -ErrorAction SilentlyContinue

    $idade = $Agora - $marcado
    return ($idade -ge 0 -and $idade -le $TurnoValidadeS)
}

# --- Ouvinte: a conversa com o servidor residente --------------------------
#
# O servidor e um processo Python que fica de pe com o modelo carregado. A tecla
# so escreve o comando; quem espera a resposta e um processo a parte, para o
# escutador de atalhos nunca ficar preso esperando a transcricao.

function Set-ComandoOuvinte([string]$comando) {
    if (-not (Test-Path $OuvinteDir)) { New-Item -ItemType Directory -Force $OuvinteDir | Out-Null }
    [System.IO.File]::WriteAllText((Join-Path $OuvinteDir 'comando.txt'), $comando, $Utf8SemBom)
}

# Espera o servidor levantar o sinal e devolve o texto transcrito.
#
# O sinal e obrigatorio, e nao a presenca do texto.txt: arquivo ainda em escrita
# e lido pela metade. O projeto ja pagou por isso uma vez com o mp3, e aqui o
# preco seria frase pela metade digitada na janela do usuario.
#
# O prazo e largo de proposito. Medido em 25/08, a mesma frase levou de 6 a 116
# segundos nesta maquina conforme o que mais estivesse rodando.
function Wait-DitadoPronto([int]$TimeoutS = 120) {
    $sinal = Join-Path $OuvinteDir 'pronto.flag'
    $texto = Join-Path $OuvinteDir 'texto.txt'
    $limite = [datetime]::Now.AddSeconds($TimeoutS)

    while ([datetime]::Now -lt $limite) {
        if (Test-Path $sinal) {
            $conteudo = ''
            try { $conteudo = [System.IO.File]::ReadAllText($texto, [System.Text.Encoding]::UTF8) } catch { }
            Remove-Item $sinal -Force -ErrorAction SilentlyContinue
            Remove-Item $texto -Force -ErrorAction SilentlyContinue
            return $conteudo
        }
        Start-Sleep -Milliseconds 120
    }

    Write-Log "ouvinte nao respondeu em $TimeoutS segundos"
    return ''
}

# --- Diario do ditado: dado para medir, nao log para ler --------------------
#
# Guarda o que o motor entendeu e o que voce acabou enviando, para que a taxa de
# correcao possa ser calculada depois. Nasce desligado: e texto seu, em disco, e
# ligar isso e decisao consciente.
#
# Ele nunca e lido por nenhum caminho de fala. O diario nao vira audio, e
# portanto nao sai da maquina.
#
# Por que arquivo proprio e nao o clarisse.log: o log e linha livre lida por
# gente, o diario e dado lido por script. Misturar os dois obrigaria o analisador
# a fazer parsing de log, que quebra, e faria o log crescer com texto que ninguem
# le.

$DiarioPath = Join-Path $OuvinteDir 'diario.jsonl'
$DiarioTeto = 300

function Test-DiarioLigado {
    $c = Get-Config
    return [bool]($c.ouvinte -and $c.ouvinte.diario)
}

function Add-LinhaDiario {
    param(
        [string]$Arquivo,
        [hashtable]$Dados,
        [bool]$Ligado,
        [int]$Teto = 300
    )
    if (-not $Ligado) { return }

    $pasta = Split-Path $Arquivo -Parent
    if ($pasta -and -not (Test-Path $pasta)) {
        New-Item -ItemType Directory -Force $pasta | Out-Null
    }

    # -Compress porque cada registro tem que caber numa linha: o analisador le
    # linha a linha, e JSON indentado partiria um registro em dezenas delas.
    $linha = ($Dados | ConvertTo-Json -Compress -Depth 4) -replace "[`r`n]+", ' '

    try {
        [System.IO.File]::AppendAllText($Arquivo, $linha + "`n", $Utf8SemBom)
    } catch {
        # Fronteira: o diario e instrumentacao. Ele nunca pode derrubar o ditado.
        Write-Log "diario nao pode ser escrito: $_"
        return
    }

    # -Encoding utf8 nao e opcional aqui: sem ele o PowerShell 5.1 le o arquivo
    # como ANSI, e a poda reescreveria todo acento ja gravado como lixo.
    $linhas = @(Get-Content $Arquivo -Encoding utf8 -ErrorAction SilentlyContinue)
    if ($linhas.Count -gt $Teto) {
        $mantem = $linhas[($linhas.Count - $Teto)..($linhas.Count - 1)]
        [System.IO.File]::WriteAllLines($Arquivo, $mantem, $Utf8SemBom)
    }
}

# O id que liga as duas metades do par.
#
# Ele viaja separado do marcador de turno de proposito, porque os dois medem
# coisas diferentes: o turno vale 60 s e decide se a Clarisse pode falar sozinha;
# o par vale 15 min e so registra o que foi ditado contra o que foi enviado.
# Voce pode revisar devagar sem ganhar fala automatica, e a medida continua.

$DiarioIdPath       = Join-Path $OuvinteDir 'ditado-id.txt'
$DiarioParValidadeS = 900

function New-IdDitado {
    return '{0}-{1}' -f [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds(), $PID
}

function Read-MedidaDitado([string]$Pasta) {
    $vazio = [pscustomobject]@{ segundos_audio = 0; segundos_transcricao = 0 }
    $caminho = Join-Path $Pasta 'medida.json'
    if (-not (Test-Path $caminho)) { return $vazio }
    try {
        $d = (Get-Content $caminho -Raw -Encoding utf8) | ConvertFrom-Json
        return [pscustomobject]@{
            segundos_audio       = [double]$d.segundos_audio
            segundos_transcricao = [double]$d.segundos_transcricao
        }
    } catch { return $vazio }
}

function Set-IdDitadoRecente([string]$Id, [int]$Agora = -1) {
    if ($Agora -lt 0) { $Agora = Get-Agora }
    if (-not (Test-Path $OuvinteDir)) { New-Item -ItemType Directory -Force $OuvinteDir | Out-Null }
    [System.IO.File]::WriteAllText($DiarioIdPath, "$Agora`t$Id", $Utf8SemBom)
}

function Read-IdDitadoRecente([int]$Agora = -1) {
    if ($Agora -lt 0) { $Agora = Get-Agora }
    if (-not (Test-Path $DiarioIdPath)) { return $null }

    $bruto = ''
    try { $bruto = [System.IO.File]::ReadAllText($DiarioIdPath).Trim() } catch { }

    # Gasto de qualquer jeito, valido ou nao: um id que sobra fecharia o par com
    # o proximo prompt digitado, e o diario registraria um ditado que nao houve.
    Remove-Item $DiarioIdPath -Force -ErrorAction SilentlyContinue

    $partes = $bruto -split "`t", 2
    if ($partes.Count -lt 2) { return $null }

    $quando = 0
    if (-not [int]::TryParse($partes[0], [ref]$quando)) { return $null }

    $idade = $Agora - $quando
    if ($idade -lt 0 -or $idade -gt $DiarioParValidadeS) { return $null }

    return [pscustomobject]@{ id = $partes[1]; segundos_ate_enviar = $idade }
}
