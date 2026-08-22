# Plano B: o Ouvinte

**Objetivo:** uma tecla que grava a fala, transcreve localmente e digita o texto na
janela em foco, e a fala de resposta ligada ao turno que essa tecla abriu.

**Arquitetura:** bloco, não fluxo — decidido por medição em 22/08/2026. Aperta a
tecla, fala, aperta de novo; ao soltar, o áudio inteiro vai ao
`faster-whisper small` com a dica dos nomes de projeto, e o texto é digitado onde
o cursor estiver. A espera de ~3 s é o piso deste motor nesta máquina e não é
contornável por corte.

**Ferramentas:** PowerShell 5.1 para as teclas e a digitação (o escutador
residente já existe), Python para gravar (`sounddevice`) e transcrever
(`faster-whisper`, `int8`, 8 threads).

---

## O que mudou desde o desenho de 21/08

Três coisas, todas medidas.

### 1. A transcrição em fluxo morreu

`docs/medicoes/2026-08-22-fluxo/` mediu a "primeira tarefa do Plano B" e ela
reprovou: cortar a fala em pedaços **dobra** a espera (3,21 s → 6,48 s) e triplica
o erro (9,2% → 29,2%). O custo do whisper é por chamada, não por segundo de áudio:
transcrever 0,5 s custa 6,17 s e transcrever 5,0 s custa 6,45 s.

**Consequência:** o Ouvinte transcreve em bloco, e a espera de ~3 s é aceita.
Ela é tolerável porque o texto é **digitado para revisão**, não enviado — o usuário
já está lendo a tela nesse momento.

### 2. O ditado nativo do Claude Code existe, e não resolve

`/voice`, tecla `Espaço`, disponível na versão instalada. A documentação oficial diz
que **o áudio vai para os servidores da Anthropic** e que o ditado escreve **só no
prompt do Claude Code**. Ele não cobre nenhuma das três razões do Ouvinte:

| Razão do Ouvinte | O nativo cobre? |
|---|---|
| Não mandar a voz para fora | Não |
| Digitar em qualquer janela (ClickUp, e-mail) | Não |
| Nomes de projeto corretos pela dica de vocabulário | Não |

### 3. O Handy foi avaliado e preterido — mas fica como contingência

[cjpais/Handy](https://github.com/cjpais/Handy), 30.098 estrelas, MIT, Rust, offline,
atalho global, cola em qualquer campo, `winget install cjpais.Handy`. É 90% deste
plano empacotado, e por isso foi considerado a sério.

Preterido por três razões:

1. **Não ganha latência.** Com Whisper é o mesmo motor e o mesmo custo por chamada
   que medimos. A alternativa dele, Parakeet TDT, **foi treinada em português
   europeu** — risco direto sobre a precisão que é o ponto do projeto.
2. **A dica não está garantida.** O "dictionary" dele existe, mas não confirmei se
   é `initial_prompt` ou substituição depois do fato. A dica vale 43 pontos de erro
   de palavra; não é item para arriscar.
3. **O vínculo com a fila é código nosso de qualquer jeito.** Nenhum app de
   terceiro registra "ditei para o projeto X", que é a fundação da tecla de leitura.

**Contingência:** se a Tarefa 5 (digitar na janela em foco) der problema com
acentuação ou com o Windows Terminal, instalar o Handy e usá-lo apenas como
gravador/digitador é o caminho de fuga — as Tarefas 1 a 4 continuam valendo.

---

## Estrutura de arquivos

| Arquivo | Responsabilidade |
|---|---|
| `clarisse/ouvinte/dica.py` | Monta o `initial_prompt` a partir dos projetos que existem na máquina |
| `clarisse/ouvinte/cortador.py` | Diz se houve fala na gravação e apara o silêncio das pontas (já existe, com testes) |
| `clarisse/ouvinte/ditado.py` | Fronteira: grava do microfone, chama o motor, devolve texto |
| `clarisse/ouvinte/turno.py` | Marcador: registra que o ditado abriu turno para um projeto |
| `clarisse/nucleo.ps1` | Ganha as funções de marcador de turno e de digitação |
| `clarisse/atalhos.ps1` | Ganha a tecla de ditado |
| `instalar.ps1` | Cria o ambiente Python do Ouvinte e registra a tecla nova |

---

## Tarefa 1: a dica sai dos projetos reais

Hoje a dica é uma constante escrita à mão com sete nomes, dentro de um script de
medição. Em produção ela tem de vir dos projetos que existem na máquina, senão ela
envelhece no dia em que um projeto novo aparece — e o erro volta de 9,2% para 52,3%
naquele nome.

**Arquivos:**
- Criar: `clarisse/ouvinte/dica.py`
- Testar: `tests/fluxo/test_dica.py`
- Ler: `clarisse/leitora/sessoes.py:55` (`listar_sessoes` já devolve o projeto de cada sessão)

- [ ] **Passo 1: escrever o teste que falha**

```python
def test_a_dica_traz_os_nomes_dos_projetos():
    dica = montar_dica(["omni-api", "compliance-app"])

    assert "omni-api" in dica
    assert "compliance-app" in dica
    assert dica.startswith("Projetos:")
```

- [ ] **Passo 2: rodar e ver falhar**

Roda: `python -m pytest tests/fluxo/test_dica.py -v`
Espera: `ModuleNotFoundError: No module named 'clarisse.ouvinte.dica'`

- [ ] **Passo 3: implementar o mínimo**

- [ ] **Passo 4: rodar e ver passar**

- [ ] **Passo 5: commitar**

Regras que os testes fixam:
- a dica termina com `Clarisse.`, porque o nome aparece em toda frase de comando;
- projeto repetido entra uma vez;
- lista vazia devolve só `Clarisse.`, nunca `Projetos: .`;
- a dica tem teto de nomes, porque `initial_prompt` compete com o áudio pela
  janela de contexto do modelo — com muitos projetos, os mais recentes ganham.

## Tarefa 2: transcrever um WAV com a dica

**Arquivos:**
- Criar: `clarisse/ouvinte/ditado.py`
- Testar: manualmente, contra as oito gravações de 21/08

Esta é fronteira de sistema: ela fala com o motor e com o disco. A lógica pura
(dica, saneamento) já está testada nas Tarefas 1 e 3; aqui só se verifica que a
chamada funciona, com os parâmetros que a medição fixou:

```python
modelo.transcribe(onda, language="pt", beam_size=1, vad_filter=False,
                  condition_on_previous_text=False, initial_prompt=dica)
```

**Nunca** passar texto recém-transcrito no `initial_prompt`: medido em 22/08, isso
levou o erro a 52,3% com repetição em laço (`clarisse clarisse clarisse`).

## Tarefa 3: sanear o texto antes de digitar

O whisper devolve com espaço na frente e às vezes com pontuação inventada no fim.
Digitar isso no terminal cria comando torto.

**Arquivos:**
- Modificar: `clarisse/ouvinte/ditado.py`
- Testar: `tests/fluxo/test_ditado.py`

Regras: apara espaços das pontas; colapsa espaço duplo; devolve string vazia se o
motor não ouviu nada — e string vazia **nunca** é digitada.

## Tarefa 4: o marcador de turno

**Arquivos:**
- Criar: `clarisse/ouvinte/turno.py`
- Testar: `tests/fluxo/test_turno.py`

O ditado escreve `~/.claude/clarisse/turno/<projeto>.txt` com o instante. O hook
`Stop` consulta: se existe marcador para aquele projeto, o resumo **fala na hora**;
se não existe, bipa e espera ser pedido. O marcador é consumido na leitura.

**Por que não usar o hook `UserPromptSubmit` para abrir o turno sozinho:** ele
dispara em todo prompt, inclusive digitado. Isso faria a Clarisse falar sozinha a
cada resposta em qualquer uma das dez sessões — exatamente o que foi corrigido em
21/08 depois de ela interromper uma reunião. O turno falado só abre com a tecla.

Regras que os testes fixam:
- marcador vencido (mais de 15 minutos) não abre turno: o usuário saiu;
- marcador de um projeto não abre turno de outro;
- consumir o marcador é idempotente.

## Tarefa 5: digitar na janela em foco

**Arquivos:**
- Modificar: `clarisse/nucleo.ps1`
- Testar: `tests/ditado.Tests.ps1`

Colar via área de transferência (`Set-Clipboard` + `Ctrl+V`) em vez de simular as
teclas letra por letra: acento em português por `SendKeys` é fonte conhecida de
caractere perdido. O conteúdo anterior da área de transferência é restaurado
depois.

**Ponto de parada:** este é o passo com maior chance de falhar de um jeito que a
medição não prevê (Windows Terminal, foco, layout de teclado). Se falhar, é aqui
que a contingência do Handy entra.

## Tarefa 6: a tecla e o instalador

**Arquivos:**
- Modificar: `clarisse/atalhos.ps1`, `clarisse/config.json`, `instalar.ps1`
- Testar: `tests/instalador.Tests.ps1`

A tecla é configurável, como as outras quatro. O instalador precisa criar um
ambiente Python com `sounddevice` e `faster-whisper` — hoje o projeto só depende de
`edge_tts`, e essas duas somam cerca de 1 GB com o modelo. **Isso muda o custo de
instalação do projeto**, e o instalador tem de dizer isso antes de baixar.

---

## Verificação

Duas suítes, e as duas têm de ficar verdes:

```
Invoke-Pester -Path .\tests
python -m pytest
```

Antes desta sessão: 133 e 37. Cada tarefa acrescenta e nenhuma derruba.

## O que este plano deliberadamente não faz

- **Palavra de ativação.** Fora do projeto desde 21/08, com medição.
- **Transcrição em fluxo.** Fora do projeto desde 22/08, com medição.
- **Enviar o texto direto.** O texto é digitado para revisão. A transcrição erra
  9,2% das palavras; agir na pasta errada é o modo de falha que o desenho mais teme.
- **Motor transducer (Parakeet, Nemotron).** É a saída se ~3 s virar inaceitável,
  mas é troca de arquitetura e tem risco de pt-BR. Fica registrado, não planejado.
