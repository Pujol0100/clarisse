# Plano B revisado: o Ouvinte residente

Data: 25/08/2026
Substitui as Tarefas 2 a 6 de `2026-08-22-plano-b-ouvinte.md`. A Tarefa 1 (a dica)
continua valendo e está feita.

## O que mudou, e por quê

O Plano B original descreve `ditado.py` como *"grava do microfone, chama o motor,
devolve texto"*, chamado pelo PowerShell a cada tecla. **Se o Python é iniciado a
cada frase, o carregamento do modelo entra no orçamento de cada frase** — em cima
dos ~3 s de transcrição que já são o piso medido.

Indício de que isso é caro nesta máquina, já registrado em 22/08: a mesma frase
custou **6,65 s a frio e 4,01 s depois de 32 passadas**. A causa foi lida como
aquecimento genérico, mas parte disso é estado que um processo residente
guardaria.

**Isto é hipótese, não medição.** A Tarefa 2 é medir. Se o carregamento custar
menos de meio segundo, este plano inteiro se desfaz e o desenho original está
certo — e isso precisa aparecer antes de qualquer código de servidor.

## A arquitetura proposta

Um processo residente carrega o modelo uma vez e espera pedido. É o mesmo padrão
que o `atalhos.ps1` já usa e que já provou funcionar nesta máquina.

```
1ª tecla --> atalhos.ps1 --> comando.txt: "gravar" --> servidor.py (residente)
                                                            | abre o microfone
                                                            | carrega o modelo
                                                            |   enquanto se fala
2ª tecla --> atalhos.ps1 --> comando.txt: "parar"  -------->| fecha e transcreve
                                                            |
                            le texto.txt  <-- pronto.flag ---+
                                  |
                            cola na janela em foco
```

### Por que dois comandos, e não um

O `RegisterHotKey` do Windows avisa quando a tecla **desce**, e nunca quando ela
sobe. Sem evento de subida não existe "segurar para falar", então a tecla alterna
— e o servidor precisa ser avisado duas vezes: uma para abrir o microfone, outra
para fechá-lo. Um comando único não teria como dizer que a fala acabou.

O desenho de 25/08 descrevia um comando só. Corrigido em 26/08, ao construir a
Tarefa 3.

**De brinde, a carga do modelo some da conta.** O `gravar` abre o microfone e
**depois** manda carregar o modelo: os ~6,8 s de carga acontecem enquanto o
usuário ainda está falando. Numa máquina que acabou de descarregar o modelo por
ócio, isso é a diferença entre esperar e não esperar.

### Por que arquivo, e não pipe ou porta local

O projeto já conversa entre processos por arquivo: o reprodutor lê o controle da
pausa a cada 120 ms, e a fala usa arquivo-sentinela. Os 120 ms de atraso não
significam nada ao lado de 3 s, e não há conceito novo para manter.

**O sentinela é obrigatório, pela mesma razão que já custou caro uma vez.** O
projeto aprendeu com o mp3: a existência do arquivo não serve como sinal, porque
um arquivo ainda em escrita é lido pela metade. `pronto.flag` é escrito **depois**
de `texto.txt` ser fechado.

### Um servidor por máquina, não um por sessão

São ~10 sessões do Claude Code abertas, e todas rodam o hook `SessionStart`. Dez
servidores seriam ~6 GB de RAM e dez processos disputando o microfone.

Trava por arquivo de PID em `~/.claude/clarisse/ouvinte/servidor.pid`, com
verificação de que o processo daquele PID existe de verdade — PID órfão de
processo morto não pode bloquear a subida do próximo.

### O custo de RAM, declarado

O `small` em `int8` residente ocupa por volta de 500 a 700 MB **permanentemente**.
Isso não é detalhe de rodapé numa máquina com dez sessões abertas.

Mitigação: tempo ocioso configurável. Passado o limite sem pedido, o servidor
descarrega o modelo e continua de pé; o próximo pedido paga o carregamento de
novo. Padrão proposto: 15 minutos.

---

## Tarefa 2: medir o que o residente economiza

**Antes de construir.** Sem este número o resto do plano é chute.

**Arquivos:** criar `docs/medicoes/2026-08-25-residente/medir_carga.py`

O que medir, na mesma execução (a regra de 22/08: execuções diferentes não se
comparam nesta máquina):

| Medida | Por quê |
|---|---|
| `import faster_whisper` mais `WhisperModel(...)` a frio | É o que o desenho por tecla paga toda vez |
| A mesma carga, segunda vez no mesmo processo | Separa disco de inicialização |
| Transcrever com o modelo já carregado, 5 vezes | O piso real de um servidor residente |
| Início do interpretador Python sozinho | Parte do custo por tecla que não é o modelo |

**Critério de decisão, escrito antes de ver o número:** se o carregamento custar
menos de 0,5 s, o servidor residente não se justifica e as Tarefas 3 em diante
voltam ao desenho original de processo por tecla.

Reaproveitar as oito gravações em `~/.claude/clarisse/medicoes/voz_real/`. **Não
pedir gravação nova ao usuário.**

## Tarefa 3: o servidor residente

**Arquivos:**
- Criar: `clarisse/ouvinte/servidor.py`
- Testar: `tests/fluxo/test_servidor.py`

A parte testável é o protocolo, não o áudio: o motor, o microfone e a
transcrição entram por injeção, e os testes usam dublês. Regras que os testes
fixam (30 testes, feito em 26/08/2026):

- `pronto.flag` só aparece depois de `texto.txt` estar fechado;
- comando desconhecido não derruba o servidor;
- PID de processo morto não impede a subida;
- PID de processo vivo impede;
- ocioso além do limite descarrega o modelo e o servidor continua respondendo;
- gravação em andamento impede a descarga por ócio;
- texto vazio não gera `pronto.flag` — string vazia nunca é digitada;
- `parar` sem `gravar` antes não faz nada, e um segundo `gravar` não reinicia a
  gravação em curso;
- gravação sem áudio não chega ao motor;
- transcrição que estoura não derruba o servidor, e a fala seguinte é atendida.

O teste de vida do PID usa `OpenProcess` por `ctypes`, e **não** `os.kill(pid, 0)`:
no Windows o CPython implementa `os.kill` chamando `TerminateProcess`, então o
teste de vida mataria o servidor que deveria apenas encontrar.

## Tarefa 4: transcrever com a dica

**Arquivos:** modificar `clarisse/ouvinte/servidor.py`

Fronteira de sistema: verificação manual contra as oito gravações de 21/08, com
os parâmetros que a medição fixou:

```python
modelo.transcribe(onda, language="pt", beam_size=1, vad_filter=False,
                  condition_on_previous_text=False, initial_prompt=dica)
```

**Nunca** passar texto recém-transcrito no `initial_prompt`: medido em 22/08,
levou o erro a 52,3% com repetição em laço. A dica serve para vocabulário fixo.

A dica vem do `dica.py` da Tarefa 1, montada dos projetos que existem na máquina.

## Tarefa 5: sanear o texto

**Arquivos:**
- Modificar: `clarisse/ouvinte/servidor.py`
- Testar: `tests/fluxo/test_saneamento.py`

Apara espaços das pontas; colapsa espaço duplo; devolve string vazia se o motor
não ouviu nada.

## Tarefa 6: o marcador de turno

**Arquivos:**
- Criar: `clarisse/ouvinte/turno.py`
- Testar: `tests/fluxo/test_turno.py`

O ditado escreve `~/.claude/clarisse/turno/<projeto>.txt`. O hook `Stop` consulta:
com marcador, o resumo **fala na hora**; sem marcador, bipa e espera.

**Por que não usar `UserPromptSubmit` para abrir o turno sozinho:** ele dispara em
todo prompt, inclusive digitado — a Clarisse falaria sozinha em cada uma das dez
sessões, exatamente o que foi corrigido em 21/08 depois de ela interromper uma
reunião. O turno falado só abre com a tecla.

Regras: marcador vencido (15 min) não abre turno; marcador de um projeto não abre
turno de outro; consumir é idempotente.

## Tarefa 7: digitar na janela em foco

**Arquivos:**
- Modificar: `clarisse/nucleo.ps1`
- Testar: `tests/ditado.Tests.ps1`

Colar por área de transferência (`Set-Clipboard` mais `Ctrl+V`), não simular tecla
a tecla: acento por `SendKeys` é fonte conhecida de caractere perdido. O conteúdo
anterior da área é restaurado depois.

**Ponto de parada.** É o passo com maior chance de falhar de um jeito que a
medição não prevê. Se falhar, é aqui que a contingência do Handy entra.

## Tarefa 8: a tecla e o instalador

**Arquivos:** `clarisse/atalhos.ps1`, `clarisse/config.json`, `instalar.ps1`

A tecla é configurável, como as outras quatro. O `SessionStart` sobe o servidor se
`ouvinte.ativo` e se a trava de PID permitir.

O instalador ganha `sounddevice` e `faster-whisper`. **O teste-guarda do
instalador reprova `.py` novo em `clarisse/` que não seja copiado** — `servidor.py`
e `turno.py` exigem mexer no `instalar.ps1`.

---

## Verificação

```
Invoke-Pester -Path .\tests
python -m pytest
```

Linha de base de hoje: 133 e 55. Cada tarefa acrescenta e nenhuma derruba.

## O que este plano deliberadamente não faz

- **Palavra de ativação.** Fora do projeto desde 21/08, com medição.
- **Transcrição em fluxo.** Fora do projeto desde 22/08, com medição.
- **Enviar o texto direto.** O texto é digitado para revisão. A transcrição erra
  9,2% das palavras; agir na pasta errada é o modo de falha que o desenho mais teme.
- **Servidor sem medir antes.** A Tarefa 2 pode reprovar este plano inteiro.
