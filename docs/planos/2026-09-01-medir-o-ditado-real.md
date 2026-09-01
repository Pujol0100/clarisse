# Medir o ditado no uso real — plano de implementação

> **Para quem for executar:** os passos usam caixa (`- [ ]`) para marcação. TDD:
> teste primeiro, vê falhar, implementa o mínimo, vê passar, commita.

**Objetivo:** produzir os números que decidem o desenho do Agente — quanto o
ditado erra quando é você falando de verdade, quanto tempo você leva revisando,
e quantas vezes você desiste.

**Arquitetura:** um diário local em JSONL, escrito em duas metades que se juntam
por um identificador: o modo `ditar` grava o que o motor entendeu, o hook
`UserPromptSubmit` grava o que você acabou enviando. Um script Python lê o
diário e produz as estatísticas.

**Stack:** PowerShell 5.1 (`nucleo.ps1`, `clarisse.ps1`), Python 3
(`servidor.py`, o analisador), Pester e pytest.

---

## O que descobri antes de planejar, e que muda o pedido

O pedido era medir **o uso real desta semana**. Isso é impossível, e é melhor
dizer agora do que descobrir no meio.

O `clarisse.log` tem **sete linhas de Ouvinte, todas de "servidor de pé"**.
Nenhuma frase ditada foi registrada em lugar nenhum: o `texto.txt` é apagado
pelo `Wait-DitadoPronto` no instante em que o texto é entregue, e o servidor
nunca anotou o que transcreveu. A semana de 26/08 a 01/09 passou sem deixar
rastro.

O prompt final que você enviou existe, sim — o Claude Code guarda em
`~/.claude/projects/<projeto>/<sessão>.jsonl`. Mas sem o texto **bruto** ao lado
dele não há como calcular erro nenhum: falta metade do par.

**Portanto o plano é instrumentar primeiro e coletar depois.** Não há atalho.

## O que esta medição mede, e o que ela não mede

Ela mede **taxa de correção**: quanto do texto ditado você mexeu antes de
apertar Enter. Isso **não é** taxa de erro do motor, e confundir os dois seria o
mesmo erro de leitura que a medição de 26/08 cometeu e teve que corrigir.

| A diferença | Efeito no número |
|---|---|
| Você aceita uma palavra errada e envia assim mesmo | Erro real existe, correção não aparece — o número **subestima** |
| Você reescreve porque mudou de ideia, não porque errou | Correção sem erro — o número **superestima** |
| Você acrescenta uma frase digitada no fim | Não é correção nenhuma, mas mexe no texto |

O terceiro caso é o mais comum e o mais fácil de separar: o analisador conta
separadamente **palavra trocada**, **palavra removida** e **palavra
acrescentada**. Acréscimo no fim não entra na taxa de correção.

Os dois primeiros não têm como ser separados sem você narrar o que fez, e não
vou pedir isso. Fica declarado: **a taxa de correção é um indicador, não uma
verdade.** O número de laboratório continua sendo o de 26/08 — 10,6% de erro por
palavra nas oito gravações — e os dois são lidos juntos.

## Arquitetura: o diário do ditado

```
tecla (2a batida)
      |
   servidor.py  --> texto.txt + medida.json --> pronto.flag
      |                                              |
      |                              modo 'ditar' le os dois
      |                                              |
      |                    grava linha "ditado" no diario.jsonl
      |                    e deixa o id em ditado-id.txt
      |
   voce revisa na janela e aperta Enter
      |
   hook UserPromptSubmit --> modo 'prompt'
      |                          consome ditado-id.txt
      |                          grava linha "enviado" no diario.jsonl
```

Duas linhas por ditado, unidas pelo `id`. **Ditado que nunca virou "enviado" é
ditado abandonado** — e essa é justamente a métrica mais reveladora, então ele
precisa mesmo aparecer sozinho.

O `id` é `<milissegundos>-<PID>`. O projeto já apanhou de identificador por
milissegundo na fila de resumos, onde 34% dos pares colidiam; aqui não colide,
porque o servidor é um só por máquina e o microfone é um só — dois ditados nunca
acontecem no mesmo instante. O PID entra como cinto de segurança.

### Por que um arquivo novo, e não o `clarisse.log`

O log é linha de texto livre lida por humano. O diário é dado tabular lido por
script. Misturar os dois obrigaria o analisador a fazer parsing de log, que é
frágil, e faria o log crescer com texto que ninguém lê.

### Por que dois campos de tempo separados

`segundos_transcricao` é o que você espera depois de soltar a tecla — é
latência, e é o que decide se o laço conversacional do Agente fecha.
`segundos_ate_enviar` é quanto tempo você passou revisando o texto na tela — é
confiança, e é um sinal mais honesto do que qualquer opinião sobre o ditado.

## Privacidade

O diário guarda **tudo que você dita**, em texto puro, no disco. Isso é novo e
precisa de regra.

1. **Desligado por padrão.** `ouvinte.diario` nasce `false`. Você liga para a
   janela de coleta e desliga depois.
2. **Nunca sai da máquina.** O diário não é lido por nenhum caminho de fala —
   ele nunca vira áudio, e portanto nunca vai para os servidores da Microsoft.
   O analisador roda local.
3. **Teto de 300 linhas**, os mais antigos descartados. Não vira arquivo eterno.
4. **Apagar é um `Remove-Item`** no arquivo, e nada no sistema quebra por isso.

O delta de privacidade é menor do que parece: o texto **enviado** já está no
disco desde sempre, nas transcrições de sessão do Claude Code. O que o diário
acrescenta é o texto **bruto** e os tempos.

## Critério de decisão, escrito antes de ver o número

Esta é a tradição do projeto e ela já derrubou três planos. O que estes números
decidem é **o desenho do Agente**, não se ele existe.

| Medida | Faixa | O que decide |
|---|---|---|
| Taxa de correção mediana | ≤ 5% | Autorização falada vale até para ação que altera arquivo, com a Clarisse repetindo o entendido antes |
| | 5% a 20% | Voz autoriza só o que **não** altera nada. Alterar exige tecla |
| | > 20% | O Agente não recebe comando por voz. O ditado continua sendo entrada de texto revisada, e ponto |
| Ditados abandonados | > 15% | Reprova comando por voz em qualquer faixa de correção — desistir é o sinal mais forte que existe |
| Latência p95 (soltar a tecla até o texto) | > 8 s | O laço conversacional não fecha; o Agente precisa responder em pedaços, e isso é uma peça a mais no desenho |
| Tempo de revisão mediano | > 15 s | Você não confia no texto. Nenhuma autorização falada se sustenta em cima disso |

**Amostra mínima: 40 ditados enviados.** Não é "uma semana" — é a contagem que
importa, e uma semana pode dar 5 ou 300.

---

## Tarefa 1: o servidor mede o que só ele sabe

O servidor é o único que conhece a duração do áudio e quanto a transcrição
levou. Ele passa isso adiante pelo mesmo protocolo de sentinela que já existe.

**Arquivos:**
- Modificar: `clarisse/ouvinte/servidor.py`
- Testar: `tests/fluxo/test_servidor.py`

- [ ] **Passo 1: escrever o teste que falha**

Acrescentar ao fim de `tests/fluxo/test_servidor.py`:

```python
def test_medida_sai_junto_com_o_texto(tmp_path):
    relogio = iter([0.0, 1.0, 2.0, 5.5, 6.0, 6.0, 6.0, 6.0])
    servidor = Servidor(
        tmp_path,
        abrir_motor=lambda: 'motor',
        gravador=GravadorFalso(onda=[0.0] * 32000),
        transcrever=lambda motor, onda: 'ola mundo',
        relogio=lambda: next(relogio),
    )
    servidor.atender(GRAVAR)
    servidor.atender(PARAR)

    medida = json.loads((tmp_path / 'medida.json').read_text(encoding='utf-8'))
    assert medida['segundos_audio'] == pytest.approx(2.0)
    assert medida['segundos_transcricao'] >= 0.0


def test_medida_existe_antes_do_sinal(tmp_path):
    servidor = Servidor(
        tmp_path,
        abrir_motor=lambda: 'motor',
        gravador=GravadorFalso(onda=[0.0] * 16000),
        transcrever=lambda motor, onda: 'ola',
    )
    servidor.atender(GRAVAR)
    servidor.atender(PARAR)

    assert (tmp_path / 'pronto.flag').exists()
    assert (tmp_path / 'medida.json').exists()


def test_transcricao_vazia_nao_deixa_medida(tmp_path):
    servidor = Servidor(
        tmp_path,
        abrir_motor=lambda: 'motor',
        gravador=GravadorFalso(onda=[0.0] * 16000),
        transcrever=lambda motor, onda: '',
    )
    servidor.atender(GRAVAR)
    servidor.atender(PARAR)

    assert not (tmp_path / 'medida.json').exists()
```

Conferir que `import json` e `import pytest` já estão no topo do arquivo; se não
estiverem, acrescentar. Conferir também o nome do dublê do gravador usado nos
testes existentes — se ele não se chamar `GravadorFalso`, usar o nome que está
lá, nos três testes acima.

- [ ] **Passo 2: rodar e ver falhar**

```
python -m pytest tests/fluxo/test_servidor.py -k medida -v
```

Esperado: FAIL, com `FileNotFoundError` em `medida.json`.

- [ ] **Passo 3: implementar o mínimo**

Em `clarisse/ouvinte/servidor.py`, acrescentar junto das outras constantes do
topo:

```python
MEDIDA = 'medida.json'
TAXA_AUDIO = 16000  # a mesma do motor; audio em outra taxa nao chega aqui
```

Trocar o bloco que transcreve — hoje ele começa assim:

```python
        try:
            texto = self._transcrever(self._motor_pronto(), onda)
```

por:

```python
        comeco = self._relogio()
        try:
            texto = self._transcrever(self._motor_pronto(), onda)
```

Logo depois do `finally` que atualiza `self._ultimo_uso`, e antes do
`if not texto:`, acrescentar:

```python
        gasto = self._relogio() - comeco
```

E trocar o fim do método `_fechar` — hoje ele é:

```python
        escrever(self.pasta / TEXTO, texto)
        escrever(self.pasta / SINAL, '')
```

por:

```python
        import json

        escrever(self.pasta / TEXTO, texto)
        escrever(self.pasta / MEDIDA, json.dumps({
            'segundos_audio': round(len(onda) / TAXA_AUDIO, 2),
            'segundos_transcricao': round(gasto, 2),
        }))
        # A sentinela continua sendo a ultima coisa escrita, e agora ela cobre
        # dois arquivos em vez de um. A regra e a mesma que o mp3 ensinou.
        escrever(self.pasta / SINAL, '')
```

- [ ] **Passo 4: rodar e ver passar**

```
python -m pytest tests/fluxo/test_servidor.py -v
```

Esperado: PASS em todos, incluindo os 30 que já existiam.

- [ ] **Passo 5: limpar a medida velha na gravação seguinte**

O `_limpar_resposta` apaga `texto.txt` e `pronto.flag` no início de cada
gravação. O `medida.json` tem que sair junto, ou uma medida velha sobrevive a um
ditado que falhou e é lida como se fosse do ditado novo. Localizar o método e
acrescentar `MEDIDA` à lista de arquivos que ele remove, do mesmo jeito que
`TEXTO` e `SINAL` já estão.

Acrescentar o teste:

```python
def test_gravar_de_novo_apaga_a_medida_anterior(tmp_path):
    (tmp_path / 'medida.json').write_text('{"segundos_audio": 99}', encoding='utf-8')
    servidor = Servidor(
        tmp_path,
        abrir_motor=lambda: 'motor',
        gravador=GravadorFalso(onda=[0.0] * 16000),
        transcrever=lambda motor, onda: 'ola',
    )
    servidor.atender(GRAVAR)

    assert not (tmp_path / 'medida.json').exists()
```

Rodar `python -m pytest tests/fluxo/test_servidor.py -v` e ver passar.

- [ ] **Passo 6: commit**

```
git add clarisse/ouvinte/servidor.py tests/fluxo/test_servidor.py
git commit -m "Faz o servidor dizer quanto durou o audio e a transcricao"
```

---

## Tarefa 2: o diário, no núcleo

**Arquivos:**
- Modificar: `clarisse/nucleo.ps1`
- Criar: `tests/diario.Tests.ps1`

- [ ] **Passo 1: escrever o teste que falha**

Criar `tests/diario.Tests.ps1`. Copiar o cabeçalho de `tests/turno.Tests.ps1`
(as primeiras linhas, que carregam o `nucleo.ps1` e apontam o `$Root` para uma
pasta temporária) — o padrão já está estabelecido lá e não deve ser reinventado.

```powershell
Describe 'Add-LinhaDiario' {
    BeforeEach {
        $script:pasta = Join-Path ([System.IO.Path]::GetTempPath()) "diario-$([guid]::NewGuid())"
        New-Item -ItemType Directory -Force $script:pasta | Out-Null
        $script:arquivo = Join-Path $script:pasta 'diario.jsonl'
    }
    AfterEach {
        Remove-Item $script:pasta -Recurse -Force -ErrorAction SilentlyContinue
    }

    It 'nao escreve nada quando o diario esta desligado' {
        Add-LinhaDiario -Arquivo $script:arquivo -Dados @{ tipo = 'ditado' } -Ligado $false
        Test-Path $script:arquivo | Should -Be $false
    }

    It 'escreve uma linha de JSON por chamada' {
        Add-LinhaDiario -Arquivo $script:arquivo -Dados @{ tipo = 'ditado'; id = 'a' } -Ligado $true
        Add-LinhaDiario -Arquivo $script:arquivo -Dados @{ tipo = 'enviado'; id = 'a' } -Ligado $true
        (Get-Content $script:arquivo).Count | Should -Be 2
    }

    It 'grava o que foi pedido, de volta como objeto' {
        Add-LinhaDiario -Arquivo $script:arquivo -Dados @{ tipo = 'ditado'; bruto = 'ola mundo' } -Ligado $true
        $linha = (Get-Content $script:arquivo -Raw) | ConvertFrom-Json
        $linha.tipo | Should -Be 'ditado'
        $linha.bruto | Should -Be 'ola mundo'
    }

    It 'preserva acento no caminho de ida e volta' {
        Add-LinhaDiario -Arquivo $script:arquivo -Dados @{ bruto = 'conciliação e férias' } -Ligado $true
        $linha = (Get-Content $script:arquivo -Raw) | ConvertFrom-Json
        $linha.bruto | Should -Be 'conciliação e férias'
    }

    It 'nunca deixa a linha quebrar em duas' {
        Add-LinhaDiario -Arquivo $script:arquivo -Dados @{ bruto = "uma`nlinha`r`noutra" } -Ligado $true
        (Get-Content $script:arquivo).Count | Should -Be 1
    }

    It 'descarta os mais antigos quando passa do teto' {
        1..305 | ForEach-Object {
            Add-LinhaDiario -Arquivo $script:arquivo -Dados @{ n = $_ } -Ligado $true -Teto 300
        }
        $linhas = @(Get-Content $script:arquivo)
        $linhas.Count | Should -Be 300
        ($linhas[0] | ConvertFrom-Json).n | Should -Be 6
        ($linhas[-1] | ConvertFrom-Json).n | Should -Be 305
    }

    It 'cria a pasta quando ela ainda nao existe' {
        $fundo = Join-Path $script:pasta 'que\nao\existe\diario.jsonl'
        Add-LinhaDiario -Arquivo $fundo -Dados @{ tipo = 'ditado' } -Ligado $true
        Test-Path $fundo | Should -Be $true
    }
}
```

- [ ] **Passo 2: rodar e ver falhar**

```
Invoke-Pester -Path .\tests\diario.Tests.ps1
```

Esperado: FAIL com "The term 'Add-LinhaDiario' is not recognized".

- [ ] **Passo 3: implementar o mínimo**

Em `clarisse/nucleo.ps1`, logo depois do bloco de funções do Ouvinte (a seção
que começa em `# --- Ouvinte: a conversa com o servidor residente`),
acrescentar:

```powershell
# --- Diario do ditado: dado para medir, nao log para ler ------------------
#
# Guarda o que o motor entendeu e o que voce acabou enviando, para que a taxa de
# correcao possa ser calculada depois. Nasce desligado: e texto seu, em disco,
# e ligar isso e decisao consciente.
#
# Ele nunca e lido por nenhum caminho de fala. O diario nao vira audio, e
# portanto nao sai da maquina.

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

    # -Compress porque a linha tem que ser uma so: o analisador le linha a linha,
    # e JSON indentado quebraria cada registro em dezenas de linhas.
    $linha = ($Dados | ConvertTo-Json -Compress -Depth 4) -replace "[`r`n]+", ' '

    try {
        [System.IO.File]::AppendAllText($Arquivo, $linha + "`n", $Utf8SemBom)
    } catch {
        # Fronteira: o diario e instrumentacao. Ele nunca pode derrubar o ditado.
        Write-Log "diario nao pode ser escrito: $_"
        return
    }

    $linhas = @(Get-Content $Arquivo -ErrorAction SilentlyContinue)
    if ($linhas.Count -gt $Teto) {
        $mantem = $linhas[($linhas.Count - $Teto)..($linhas.Count - 1)]
        [System.IO.File]::WriteAllLines($Arquivo, $mantem, $Utf8SemBom)
    }
}
```

- [ ] **Passo 4: rodar e ver passar**

```
Invoke-Pester -Path .\tests\diario.Tests.ps1
```

Esperado: 7 passando, 0 falhando.

- [ ] **Passo 5: commit**

```
git add clarisse/nucleo.ps1 tests/diario.Tests.ps1
git commit -m "Poe o diario do ditado no nucleo, desligado por padrao"
```

---

## Tarefa 3: o ditar grava a primeira metade

**Arquivos:**
- Modificar: `clarisse/nucleo.ps1`, `clarisse/clarisse.ps1`
- Testar: `tests/diario.Tests.ps1`

- [ ] **Passo 1: escrever o teste que falha**

Acrescentar a `tests/diario.Tests.ps1`:

```powershell
Describe 'New-IdDitado' {
    It 'devolve dois pedacos separados por hifen' {
        New-IdDitado | Should -Match '^\d+-\d+$'
    }

    It 'nao repete em duas chamadas seguidas' {
        $a = New-IdDitado
        Start-Sleep -Milliseconds 2
        $b = New-IdDitado
        $a | Should -Not -Be $b
    }
}

Describe 'Read-MedidaDitado' {
    BeforeEach {
        $script:pasta = Join-Path ([System.IO.Path]::GetTempPath()) "medida-$([guid]::NewGuid())"
        New-Item -ItemType Directory -Force $script:pasta | Out-Null
    }
    AfterEach {
        Remove-Item $script:pasta -Recurse -Force -ErrorAction SilentlyContinue
    }

    It 'devolve zeros quando o arquivo nao existe' {
        $m = Read-MedidaDitado -Pasta $script:pasta
        $m.segundos_audio | Should -Be 0
        $m.segundos_transcricao | Should -Be 0
    }

    It 'devolve o que o servidor mediu' {
        Set-Content (Join-Path $script:pasta 'medida.json') '{"segundos_audio":4.2,"segundos_transcricao":3.1}' -Encoding utf8
        $m = Read-MedidaDitado -Pasta $script:pasta
        $m.segundos_audio | Should -Be 4.2
        $m.segundos_transcricao | Should -Be 3.1
    }

    It 'devolve zeros quando o arquivo esta estragado' {
        Set-Content (Join-Path $script:pasta 'medida.json') 'isto nao e json' -Encoding utf8
        $m = Read-MedidaDitado -Pasta $script:pasta
        $m.segundos_audio | Should -Be 0
    }
}

Describe 'Set-IdDitadoRecente e Read-IdDitadoRecente' {
    BeforeEach {
        Remove-Item (Join-Path $OuvinteDir 'ditado-id.txt') -Force -ErrorAction SilentlyContinue
    }

    It 'devolve vazio quando nenhum ditado aconteceu' {
        Read-IdDitadoRecente | Should -BeNullOrEmpty
    }

    It 'devolve o id que o ditado deixou' {
        Set-IdDitadoRecente -Id 'abc-1'
        (Read-IdDitadoRecente).id | Should -Be 'abc-1'
    }

    It 'serve uma vez so' {
        Set-IdDitadoRecente -Id 'abc-1'
        Read-IdDitadoRecente | Out-Null
        Read-IdDitadoRecente | Should -BeNullOrEmpty
    }

    It 'diz quantos segundos se passaram desde o ditado' {
        Set-IdDitadoRecente -Id 'abc-1' -Agora 1000
        (Read-IdDitadoRecente -Agora 1018).segundos_ate_enviar | Should -Be 18
    }

    It 'id de quinze minutos atras nao serve mais' {
        Set-IdDitadoRecente -Id 'abc-1' -Agora 1000
        Read-IdDitadoRecente -Agora (1000 + 901) | Should -BeNullOrEmpty
    }
}
```

- [ ] **Passo 2: rodar e ver falhar**

```
Invoke-Pester -Path .\tests\diario.Tests.ps1
```

Esperado: FAIL nas funções novas, PASS nos 7 da Tarefa 2.

- [ ] **Passo 3: implementar o mínimo**

Em `clarisse/nucleo.ps1`, no mesmo bloco do diário:

```powershell
$DiarioIdPath       = Join-Path $OuvinteDir 'ditado-id.txt'
$DiarioParValidadeS = 900   # mais largo que o turno: revisar devagar nao invalida a medida

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

# O id do ditado viaja separado do marcador de turno de proposito: o turno vale
# 60 s e o par da medicao vale 15 min. Voce pode demorar revisando sem que a
# Clarisse ganhe permissao de falar sozinha, e a medida continua valendo.
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
    Remove-Item $DiarioIdPath -Force -ErrorAction SilentlyContinue

    $partes = $bruto -split "`t", 2
    if ($partes.Count -lt 2) { return $null }

    $quando = 0
    if (-not [int]::TryParse($partes[0], [ref]$quando)) { return $null }

    $idade = $Agora - $quando
    if ($idade -lt 0 -or $idade -gt $DiarioParValidadeS) { return $null }

    return [pscustomobject]@{ id = $partes[1]; segundos_ate_enviar = $idade }
}
```

O `Wait-DitadoPronto` apaga `texto.txt` e `pronto.flag` ao entregar; o
`medida.json` **não** pode ser apagado ali, porque o modo `ditar` ainda vai
lê-lo. Ele já é limpo pelo servidor na gravação seguinte (Tarefa 1, passo 5).
Conferir que `Wait-DitadoPronto` não o remove.

- [ ] **Passo 4: rodar e ver passar**

```
Invoke-Pester -Path .\tests\diario.Tests.ps1
```

Esperado: 17 passando.

- [ ] **Passo 5: ligar no modo `ditar`**

Em `clarisse/clarisse.ps1`, no bloco `'ditar'`, trocar:

```powershell
        if (Send-TextoNaJanela $texto) {
            # O turno abre aqui, ainda sem dono: este processo nao sabe em qual
            # sessao o texto caiu. O prompt enviado a seguir e que da o nome.
            Set-DitadoRecente
        }
```

por:

```powershell
        if (Send-TextoNaJanela $texto) {
            $ditadoId = New-IdDitado
            $medida   = Read-MedidaDitado $OuvinteDir
            Add-LinhaDiario -Arquivo $DiarioPath -Ligado (Test-DiarioLigado) -Teto $DiarioTeto -Dados @{
                tipo                 = 'ditado'
                id                   = $ditadoId
                quando               = (Get-Date -Format 's')
                bruto                = $texto
                segundos_audio       = $medida.segundos_audio
                segundos_transcricao = $medida.segundos_transcricao
            }
            Set-IdDitadoRecente -Id $ditadoId

            # O turno abre aqui, ainda sem dono: este processo nao sabe em qual
            # sessao o texto caiu. O prompt enviado a seguir e que da o nome.
            Set-DitadoRecente
        }
```

- [ ] **Passo 6: rodar a suíte inteira**

```
Invoke-Pester -Path .\tests
```

Esperado: 175 + 17 = 192 passando, 0 falhando.

- [ ] **Passo 7: commit**

```
git add clarisse/nucleo.ps1 clarisse/clarisse.ps1 tests/diario.Tests.ps1
git commit -m "Faz o ditado registrar o que o motor entendeu e quanto demorou"
```

---

## Tarefa 4: o prompt fecha o par

**Arquivos:**
- Modificar: `clarisse/nucleo.ps1`, `clarisse/clarisse.ps1`
- Testar: `tests/diario.Tests.ps1`

- [ ] **Passo 1: escrever o teste que falha**

Acrescentar a `tests/diario.Tests.ps1`:

```powershell
Describe 'Get-PromptDoHook' {
    It 'tira o prompt do JSON que o Claude Code manda no stdin' {
        Get-PromptDoHook '{"cwd":"C:\\p\\omni","prompt":"roda os testes"}' | Should -Be 'roda os testes'
    }

    It 'devolve vazio quando o JSON nao tem prompt' {
        Get-PromptDoHook '{"cwd":"C:\\p\\omni"}' | Should -Be ''
    }

    It 'nao quebra com entrada que nao e JSON' {
        Get-PromptDoHook 'isto nao e json' | Should -Be ''
    }

    It 'nao quebra com entrada vazia' {
        Get-PromptDoHook '' | Should -Be ''
    }

    It 'preserva acento' {
        Get-PromptDoHook '{"prompt":"conciliação de férias"}' | Should -Be 'conciliação de férias'
    }
}
```

- [ ] **Passo 2: rodar e ver falhar**

```
Invoke-Pester -Path .\tests\diario.Tests.ps1
```

Esperado: FAIL com "The term 'Get-PromptDoHook' is not recognized".

- [ ] **Passo 3: implementar o mínimo**

Em `clarisse/nucleo.ps1`, logo abaixo de `Get-CwdDoHook`:

```powershell
function Get-PromptDoHook([string]$bruto) {
    if ([string]::IsNullOrWhiteSpace($bruto)) { return '' }
    try {
        $dados = $bruto | ConvertFrom-Json
        if ($dados.prompt) { return [string]$dados.prompt }
    } catch { }
    return ''
}
```

- [ ] **Passo 4: rodar e ver passar**

```
Invoke-Pester -Path .\tests\diario.Tests.ps1
```

Esperado: 22 passando.

- [ ] **Passo 5: ligar no modo `prompt`**

Em `clarisse/clarisse.ps1`, no bloco `'prompt'`, trocar o corpo por:

```powershell
        if (-not $cfg.enabled) { exit 0 }
        $stdin   = Read-StdinDoHook
        $projeto = Get-NomeProjeto (Get-CwdDoHook $stdin)
        if ($projeto) { Resolve-TurnoDoProjeto -Projeto $projeto | Out-Null }

        # A outra metade do par: o que voce acabou enviando, depois de revisar.
        # So fecha o par se este prompt veio mesmo de um ditado recente.
        $recente = Read-IdDitadoRecente
        if ($recente) {
            Add-LinhaDiario -Arquivo $DiarioPath -Ligado (Test-DiarioLigado) -Teto $DiarioTeto -Dados @{
                tipo                = 'enviado'
                id                  = $recente.id
                quando              = (Get-Date -Format 's')
                projeto             = $projeto
                enviado             = (Get-PromptDoHook $stdin)
                segundos_ate_enviar = $recente.segundos_ate_enviar
            }
        }
```

Reparar que o `Read-StdinDoHook` passa a ser chamado **uma vez** e o resultado
reutilizado: ele lê o stdin até o fim, e uma segunda chamada devolveria vazio.

- [ ] **Passo 6: rodar a suíte inteira**

```
Invoke-Pester -Path .\tests
```

Esperado: 197 passando, 0 falhando.

- [ ] **Passo 7: commit**

```
git add clarisse/nucleo.ps1 clarisse/clarisse.ps1 tests/diario.Tests.ps1
git commit -m "Fecha o par do diario com o texto que voce acabou enviando"
```

---

## Tarefa 5: o config, o status e o instalador

**Arquivos:**
- Modificar: `clarisse/config.json`, `clarisse/clarisse.ps1`, `instalar.ps1`
- Testar: `tests/instalador.Tests.ps1`

- [ ] **Passo 1: escrever o teste que falha**

Acrescentar a `tests/instalador.Tests.ps1`:

```powershell
Describe 'config do diario' {
    It 'o config de referencia traz o diario desligado' {
        $c = Get-Content (Join-Path $PSScriptRoot '..\clarisse\config.json') -Raw | ConvertFrom-Json
        $c.ouvinte.PSObject.Properties.Name | Should -Contain 'diario'
        $c.ouvinte.diario | Should -Be $false
    }

    It 'o instalador acrescenta o diario a um config que ainda nao tem' {
        $texto = Get-Content (Join-Path $PSScriptRoot '..\instalar.ps1') -Raw
        $texto | Should -Match "notcontains 'diario'"
    }
}
```

- [ ] **Passo 2: rodar e ver falhar**

```
Invoke-Pester -Path .\tests\instalador.Tests.ps1
```

Esperado: FAIL nos dois.

- [ ] **Passo 3: implementar o mínimo**

Em `clarisse/config.json`, o bloco `ouvinte` passa a ser:

```json
  "ouvinte": {
    "ativo": false,
    "ditar": "Ctrl+Alt+D",
    "modelo": "small",
    "diario": false
  }
```

Em `instalar.ps1`, logo depois do bloco que acrescenta `ouvinte` a um config
antigo (o `if ($atual.PSObject.Properties.Name -notcontains 'ouvinte')`),
acrescentar:

```powershell
    if ($atual.ouvinte -and ($atual.ouvinte.PSObject.Properties.Name -notcontains 'diario')) {
        # Desligado: e texto seu em disco, e ligar isso e decisao consciente.
        $atual.ouvinte | Add-Member -NotePropertyName diario -NotePropertyValue $false
        Passo 'config.json ganhou o diario do ditado, desligado'
    }
```

- [ ] **Passo 4: mostrar a contagem no status**

Em `clarisse/clarisse.ps1`, no bloco `'status'`, acrescentar antes do
`Write-Output` final:

```powershell
        $diario = if (Test-DiarioLigado) {
            $n = 0
            if (Test-Path $DiarioPath) { $n = @(Get-Content $DiarioPath).Count }
            " | diario do ditado: LIGADO ($n linhas)"
        } else { '' }
```

e emendar `$diario` no fim da string do `Write-Output`.

- [ ] **Passo 5: rodar a verificação inteira**

```
Invoke-Pester -Path .\tests
python -m pytest
```

Esperado: 199 e 117, 0 falhando.

- [ ] **Passo 6: commit**

```
git add clarisse/config.json clarisse/clarisse.ps1 instalar.ps1 tests/instalador.Tests.ps1
git commit -m "Poe o diario no config e mostra a contagem no status"
```

---

## Tarefa 6: o analisador

Não é código de produção: é script de medição, e mora onde as outras medições
moram. Ele roda uma vez, no fim da coleta.

**Arquivos:**
- Criar: `docs/medicoes/2026-09-01-ditado-real/analisar.py`
- Criar: `docs/medicoes/2026-09-01-ditado-real/README.md`

- [ ] **Passo 1: escrever o analisador**

Criar `docs/medicoes/2026-09-01-ditado-real/analisar.py`:

```python
"""Le o diario do ditado e produz os numeros que decidem o desenho do Agente.

Roda sobre `~/.claude/clarisse/ouvinte/diario.jsonl`, que so existe se
`ouvinte.diario` estiver ligado no config. Nada aqui manda dado para lugar
nenhum: le arquivo local, imprime na tela, grava o resultado ao lado.

A taxa de correcao NAO e taxa de erro do motor. Ela mede quanto voce mexeu no
texto antes de enviar, e isso sobe com mudanca de ideia e desce com erro que
voce aceitou. Ler junto com o numero de laboratorio de 26/08: 10,6%.
"""

from __future__ import annotations

import json
import statistics
import sys
import unicodedata
from collections import Counter
from pathlib import Path

DIARIO = Path.home() / '.claude' / 'clarisse' / 'ouvinte' / 'diario.jsonl'
SAIDA = Path(__file__).parent / 'resultado.json'


def normaliza(texto: str) -> str:
    """Tira acento, pontuacao e caixa: erro de acento nao e erro de palavra."""
    sem_acento = ''.join(
        c for c in unicodedata.normalize('NFD', texto.lower())
        if unicodedata.category(c) != 'Mn'
    )
    return ''.join(c if c.isalnum() or c.isspace() else ' ' for c in sem_acento)


def script_de_edicao(ref: list[str], hip: list[str]) -> tuple[int, int, int]:
    """Devolve (trocadas, removidas, acrescentadas) entre as duas listas.

    Separar os tres importa: acrescentar uma frase digitada no fim nao e
    correcao nenhuma, e somar tudo num numero so faria isso parecer erro.
    """
    n, m = len(ref), len(hip)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0] = i
    for j in range(m + 1):
        d[0][j] = j
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            d[i][j] = min(
                d[i - 1][j] + 1,
                d[i][j - 1] + 1,
                d[i - 1][j - 1] + (ref[i - 1] != hip[j - 1]),
            )

    trocadas = removidas = acrescentadas = 0
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0 and ref[i - 1] == hip[j - 1] and d[i][j] == d[i - 1][j - 1]:
            i, j = i - 1, j - 1
        elif i > 0 and j > 0 and d[i][j] == d[i - 1][j - 1] + 1:
            trocadas += 1
            i, j = i - 1, j - 1
        elif i > 0 and d[i][j] == d[i - 1][j] + 1:
            removidas += 1
            i -= 1
        else:
            acrescentadas += 1
            j -= 1
    return trocadas, removidas, acrescentadas


def palavras_trocadas(ref: list[str], hip: list[str]) -> list[tuple[str, str]]:
    """As duplas (o que o motor ouviu, o que voce pos no lugar)."""
    pares = []
    i = j = 0
    while i < len(ref) and j < len(hip):
        if ref[i] == hip[j]:
            i, j = i + 1, j + 1
        else:
            pares.append((ref[i], hip[j]))
            i, j = i + 1, j + 1
    return pares


def principal() -> None:
    if not DIARIO.exists():
        print(f'diario nao existe em {DIARIO}')
        print('ligue "diario": true no bloco "ouvinte" do config.json e dite algumas vezes')
        sys.exit(1)

    ditados: dict[str, dict] = {}
    enviados: dict[str, dict] = {}
    for linha in DIARIO.read_text(encoding='utf-8').splitlines():
        if not linha.strip():
            continue
        try:
            reg = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if reg.get('tipo') == 'ditado':
            ditados[reg['id']] = reg
        elif reg.get('tipo') == 'enviado':
            enviados[reg['id']] = reg

    pares = [(ditados[i], enviados[i]) for i in ditados if i in enviados]
    abandonados = [d for i, d in ditados.items() if i not in enviados]

    print(f'ditados registrados: {len(ditados)}')
    print(f'pares completos:     {len(pares)}')
    print(f'abandonados:         {len(abandonados)}')
    if not pares:
        print('nada para medir ainda')
        sys.exit(1)

    correcoes, latencias, revisoes, trocas = [], [], [], Counter()
    for ditado, enviado in pares:
        ref = normaliza(ditado.get('bruto', '')).split()
        hip = normaliza(enviado.get('enviado', '')).split()
        if not ref:
            continue
        trocadas, removidas, _acrescentadas = script_de_edicao(ref, hip)
        # Acrescimo nao entra: digitar mais depois nao e o motor ter errado.
        correcoes.append((trocadas + removidas) / len(ref))
        latencias.append(float(ditado.get('segundos_transcricao', 0)))
        revisoes.append(float(enviado.get('segundos_ate_enviar', 0)))
        for ouvida, posta in palavras_trocadas(ref, hip):
            trocas[f'{ouvida} -> {posta}'] += 1

    def p(valores: list[float], quantil: float) -> float:
        ordenado = sorted(valores)
        k = min(int(quantil * len(ordenado)), len(ordenado) - 1)
        return ordenado[k]

    resultado = {
        'amostra': len(pares),
        'abandonados': len(abandonados),
        'taxa_abandono': round(len(abandonados) / len(ditados), 3),
        'correcao_mediana': round(statistics.median(correcoes), 3),
        'correcao_media': round(statistics.fmean(correcoes), 3),
        'correcao_p95': round(p(correcoes, 0.95), 3),
        'latencia_mediana_s': round(statistics.median(latencias), 2),
        'latencia_p95_s': round(p(latencias, 0.95), 2),
        'revisao_mediana_s': round(statistics.median(revisoes), 1),
        'trocas_frequentes': trocas.most_common(10),
    }

    print()
    print(f"correcao mediana   {resultado['correcao_mediana']:.1%}")
    print(f"correcao p95       {resultado['correcao_p95']:.1%}")
    print(f"abandono           {resultado['taxa_abandono']:.1%}")
    print(f"latencia mediana   {resultado['latencia_mediana_s']:.2f} s")
    print(f"latencia p95       {resultado['latencia_p95_s']:.2f} s")
    print(f"revisao mediana    {resultado['revisao_mediana_s']:.1f} s")
    print()
    print('palavras mais trocadas:')
    for troca, quantas in resultado['trocas_frequentes']:
        print(f'  {quantas:3d}x  {troca}')

    if len(pares) < 40:
        print()
        print(f'AVISO: {len(pares)} pares. O criterio pede 40. Continue coletando.')

    SAIDA.write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\nresultado em {SAIDA}')


if __name__ == '__main__':
    principal()
```

- [ ] **Passo 2: rodar contra um diário de brinquedo**

Antes de coletar de verdade, provar que o analisador funciona. Criar três linhas
à mão num arquivo temporário, apontar `DIARIO` para ele e rodar:

```
python docs/medicoes/2026-09-01-ditado-real/analisar.py
```

Esperado: a contagem bate com as linhas criadas, e um par em que `bruto` e
`enviado` são idênticos dá correção 0,0%.

- [ ] **Passo 3: escrever o README da medição**

Criar `docs/medicoes/2026-09-01-ditado-real/README.md` com: a data, a máquina, o
critério de decisão copiado deste plano **antes** de qualquer número, e a seção
de resultado deixada vazia para ser preenchida depois da coleta.

- [ ] **Passo 4: commit**

```
git add docs/medicoes/2026-09-01-ditado-real/
git commit -m "Escreve o analisador do diario e o criterio, antes de coletar"
```

---

## Tarefa 7: instalar e começar a coletar

Esta tarefa não tem teste: ela é o ponto em que o código sai do repositório e
entra na máquina.

- [ ] **Passo 1: rodar a verificação inteira**

```
Invoke-Pester -Path .\tests
python -m pytest
```

Esperado: 199 e 117, zero falhas. **Se falhar qualquer um, parar aqui.**

- [ ] **Passo 2: instalar**

```
powershell -ExecutionPolicy Bypass -File .\instalar.ps1
```

Este passo **sobrescreve** os arquivos em `~/.claude/clarisse`. O instalador faz
backup do `settings.json`, e o `config.json` é preservado e só ganha o campo
novo. Ponto de conferência antes de seguir.

- [ ] **Passo 3: ligar o diário**

Abrir `~/.claude/clarisse/config.json` e pôr `"diario": true` dentro do bloco
`ouvinte`. Depois, `/clarisse atalhos off` e `/clarisse atalhos on`.

- [ ] **Passo 4: conferir que o par fecha**

Ditar uma frase qualquer numa sessão, revisar, enviar. Depois abrir o
`diario.jsonl` na pasta do Ouvinte.

Esperado: **duas** linhas, uma `ditado` e uma `enviado`, com o mesmo `id`. Se só
aparecer a linha `ditado`, o hook `UserPromptSubmit` não rodou — abrir `/hooks`
uma vez e repetir.

- [ ] **Passo 5: coletar**

Usar normalmente até `/clarisse status` mostrar pelo menos 80 linhas (40 pares).

- [ ] **Passo 6: analisar e escrever o achado**

```
python docs/medicoes/2026-09-01-ditado-real/analisar.py
```

Preencher a seção de resultado do README com os números e com **o que eles
decidem**, segundo a tabela de critério — que já está escrita e não pode ser
ajustada depois de ver o número.

---

## Verificação

```
Invoke-Pester -Path .\tests
python -m pytest
```

Linha de base de hoje: **175 e 113**. Ao fim da Tarefa 5: **199 e 117**. Nenhuma
tarefa pode derrubar teste existente.

## O que este plano deliberadamente não faz

- **Não constrói o Agente.** Ele é o destino, e o número é que desenha ele.
- **Não pede que você grave nada nem repita frase.** A medição usa o trabalho
  que você já ia fazer.
- **Não liga o diário por padrão.** Texto seu em disco é decisão sua.
- **Não tenta reconstruir a semana passada.** Não há dado. Fingir que há seria
  inventar número, que é o oposto do que este projeto faz.
- **Não mexe na `dica.py`.** As palavras mais trocadas vão apontar melhorias no
  vocabulário, mas isso é consequência da medição, não parte dela.
