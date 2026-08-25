# O ouvinte residente, e o ruído que impediu o resto

Data: 25/08/2026
Máquina: Intel i7-1355U (2 núcleos rápidos, 8 econômicos, 12 lógicos, 1,7 GHz),
Windows 11, Python 3.14.4, `faster-whisper` 1.2.1, `ctranslate2` 4.8.1.
Estado: condição normal de trabalho — cerca de 10 sessões do Claude Code abertas,
OneDrive ativo, CPU em 68% no início da medição.

## O que esta medição decidiu

**O servidor residente está aprovado.** O critério foi escrito antes de medir: se
carregar o modelo custasse menos de 0,5 s, o residente não se justificaria.

| Medida | Valor |
|---|---|
| Interpretador Python sozinho | 0,13 s |
| `import faster_whisper` | 1,51 s |
| Carregar o modelo, 1ª vez | 6,78 s |
| Carregar o modelo, 2ª vez, no mesmo processo | 3,98 s |
| **Custo fixo pago a cada tecla, no desenho por processo** | **8,42 s** |

8,42 s contra um critério de 0,5 s. Não há leitura desses números que salve o
desenho de iniciar o Python a cada frase.

Script: `medir_carga.py`. Resultado: `resultado.json`.

## O que esta medição NÃO decidiu, e é o achado maior

**O número de threads.** E a tentativa de decidir produziu duas conclusões
opostas, o que é mais útil que qualquer uma das duas.

### Primeira tentativa: sequencial (`medir_threads.py`)

Configurações medidas em ordem, 3 repetições cada:

| threads | mediana | as três medidas |
|---|---|---|
| 2 | 14,69 s | 14,69 / 16,22 / 12,85 |
| 4 | 26,26 s | 26,26 / 33,00 / 15,55 |
| 6 | 63,43 s | 63,43 / 23,32 / 82,01 |
| 8 | 60,01 s | 65,44 / 60,01 / 37,42 |
| 12 | 91,93 s | 91,93 / 116,25 / 23,11 |

Leitura ingênua: menos threads é melhor, 6,3× de diferença. **Está errada.** A
variação dentro de `threads=12` (23 s a 116 s) é quase tão grande quanto a
variação entre a melhor e a pior configuração.

### Segunda tentativa: intercalada (`medir_intercalado.py`)

As duas configurações alternando a cada rodada, com os dois modelos já
carregados, para que a lentidão da máquina afete ambas igualmente:

| rodada | threads=2 | threads=8 |
|---|---|---|
| 1 | 46,49 s | 18,24 s |
| 2 | 34,44 s | 12,67 s |
| 3 | 27,90 s | 20,70 s |
| 4 | 16,78 s | 8,67 s |
| 5 | 7,82 s | 11,43 s |

| | mediana | menor | maior | espalhamento |
|---|---|---|---|---|
| threads=2 | 27,90 s | 7,82 s | 46,49 s | 5,9× |
| threads=8 | 12,67 s | 8,67 s | 20,70 s | 2,4× |

**A ordem inverteu.** Na medição sequencial `threads=2` foi a melhor; na
intercalada foi a pior, por 2×. Efeito das threads: 0,5×. Ruído da máquina: 5,9×.

**O ruído engole o sinal. Esta medição não decide o número de threads, e nenhuma
medição decidirá enquanto a máquina estiver neste estado.**

### O que aparece nos números quando se olha a coluna certa

`threads=2` caiu monotonicamente ao longo das rodadas: 46,49 → 34,44 → 27,90 →
16,78 → 7,82. É o mesmo aquecimento registrado em 22/08, quando a mesma frase
custou 6,65 s a frio e 4,01 s depois de 32 passadas.

**Falha conhecida deste script:** dentro de cada rodada a ordem não alternou —
`threads=2` sempre mediu primeiro e por isso pagou o custo frio de cada rodada.
Uma repetição futura precisa inverter a ordem em rodadas alternadas.

## A consequência que importa para o projeto

Os 3,21 s registrados em 22/08 **não se reproduzem nesta máquina em condição de
trabalho.** A pior medida de hoje foi 116 s para a mesma frase de ~5 s.

Isso não é um problema do motor, do número de threads ou da arquitetura. É a
capacidade sobrando da máquina, e ela varia 6× ao longo de meia hora com o que o
usuário normalmente mantém aberto.

**Para o Ouvinte, isso vale mais que qualquer ajuste:** a latência do ditado não é
uma propriedade do desenho, é uma propriedade do que mais está rodando. Um
orçamento de 3 s é o melhor caso, não o caso típico.

Duas saídas, nenhuma medida ainda:

1. **Prioridade de processo.** Numa máquina disputada, prioridade é a alavanca que
   funciona. O servidor residente pode subir em `AboveNormal`. Barato de testar.
2. **Trocar de família de motor**, já registrado em 22/08: transducer servido por
   `sherpa-onnx` tem custo proporcional ao áudio. Risco conhecido de pt-BR europeu
   no Parakeet.

## Como repetir isto de forma limpa

Uma medição limpa exige a máquina quieta, e isso é decisão do usuário, não do
script. Fechar as outras sessões do Claude Code, pausar a sincronização do
OneDrive, e só então rodar. Sem isso, repetir só produz outro número inútil.

## Ambiente

O venv fica em `venv/` e está fora do repositório pelo `.gitignore`, junto com as
outras medições. Recriar:

```
python -m venv venv
venv\Scripts\python.exe -m pip install faster-whisper sounddevice
```

Os modelos vêm do cache do Hugging Face, já baixados nesta máquina (680 MB).

## Regra que esta medição confirma

Duas ordens de medida deram respostas opostas sobre threads. **Configuração medida
em sequência não se compara quando a máquina deriva.** Intercalar não foi zelo
excessivo: foi o que impediu o projeto de fixar `threads=2` no config com base num
artefato.
