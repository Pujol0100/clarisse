# Roteiro da Azure e a escolha da palavra de ativação

Data: 21/08/2026. Pré-requisito do Plano B (o Ouvinte).

Este documento resolve o item **"Pré-requisito que depende do usuário"** do design
`2026-08-20-clarisse-ao-vivo-design.md`, e corrige duas suposições que aquele
design fez sem verificar.

## O que a pesquisa derrubou do design original

O design assumiu: *"Palavra de ativação: modelo local da Azure, gerado no Speech
Studio"*. Isso não sobrevive à documentação.

| Suposição do design | O que a fonte oficial diz |
|---|---|
| A palavra "Clarisse" pode ser gerada no Speech Studio | Custom Keyword só aceita **inglês dos EUA e chinês mandarim**. Não existe português |
| O recurso pode ficar no Brasil | `brazilsouth` **não** suporta *Custom keyword advanced models* nem *Keyword verification* |
| Nenhum áudio sai antes dela ouvir o nome | Verdade **só** no modo offline puro do `KeywordRecognizer`. No modo combinado com verificação, o áudio vai para a nuvem depois da detecção local |

O custo, por outro lado, é melhor do que o design temia: gerar o modelo da palavra
e rodá-lo no dispositivo é **gratuito**, e a verificação na nuvem não cobra nada
além da transcrição. A transcrição tem **5 horas de áudio por mês** grátis na
camada F0, listada como "sempre gratuito". O preço por hora acima disso **não
está publicado** — a tabela oficial mostra `$-`.

## As quatro opções para a palavra de ativação, e por que sobrou uma

| Opção | Português | Custo | Esforço | Veredito |
|---|---|---|---|---|
| Azure Custom Keyword | Não. Só en-US e zh | Grátis | Mínimo: digitar a palavra no portal e testar no navegador | Viável, mas força a região fora do Brasil e aposta que a pronúncia inglesa de "Clarisse" pegue |
| Picovoice Porcupine | **Sim, nativo** | **Morto** | Mínimo | **Descartado.** A Picovoice encerrou a camada gratuita em 30/06/2026 e declarou: *"There is no non-commercial tier planned"* |
| openWakeWord | Oficialmente **não** | Grátis, Apache 2.0 | Alto: treinar no Colab, cerca de 1 h, mais calibrar limiar | Descartado como primeira escolha. O README diz *"Currently, openWakeWord only supports English"*. Português só por caminho não suportado, com TTS Piper |
| **Vosk local** | **Sim**, modelo pt de 31 MB | Grátis, Apache 2.0, sem conta | Médio: nenhum treino, mas reconhecimento contínuo na CPU | **Escolhido**, no modo de vocabulário livre |

### Por que Vosk

1. Português de verdade, sem fingir que a palavra é inglesa.
2. Sem conta, sem chave, sem cadastro, sem risco de a camada gratuita ser
   encerrada — é Apache 2.0 e o modelo fica no disco.
3. Sem etapa de treino. O openWakeWord jogaria uma hora de Colab e uma calibração
   de limiar para dentro do Plano B, que já é o plano mais longo.
4. **Libera a região `brazilsouth` para a transcrição.** Com a ativação local, a
   Azure só é chamada depois que o nome é ouvido, e nada obriga mais o recurso a
   viver fora do país. Menos latência e o áudio não sai do Brasil.
5. O modo de falha é benigno: se ela não ouvir o nome, você aperta `F6`. A tecla
   já é a outra forma de ativar, decidida no design.

### Corrigido pela medição de 21/08/2026

Esta seção dizia originalmente que o Vosk rodaria com a **gramática restrita** a
uma frase só, e que isso seria um problema mais fácil que reconhecimento aberto.
**A medição reprovou essa ideia.** Ver `docs/medicoes/2026-08-21-fala-local/`.

Travada em `["clarisse","[unk]"]`, o reconhecedor é obrigado a encaixar todo som
numa das duas opções, e o português está cheio de palavras que colidem com o nome:
*clareza, esclarecimento, esclareceu, classificar, esclarecimentos*. Resultado
medido: **6 falsos positivos em 12** frases de trabalho. Cortar por confiança não
resolve, porque as distribuições estão invertidas — os falsos vêm com confiança
1,00 e o acerto real do nome sozinho vem com 0,76.

O modo correto é o **vocabulário livre**: com o modelo inteiro disponível, "clareza"
é reconhecida como "clareza". Medido: **0 falsos positivos em 12**, latência
mediana de 1096 ms, pior caso 1597 ms. O custo é perder as falas mais curtas — o
nome dito sozinho falhou 2 vezes em 5 — e é por isso que a tecla `F6` deixa de ser
alternativa e passa a ser a rede de segurança.

Se a validação com voz real reprovar o Vosk, a queda é para o openWakeWord com voz
Piper em pt-BR, não para o Porcupine — que deixou de ser opção.

## A armadilha que custaria dinheiro

A documentação da Microsoft manda criar um **"Foundry resource for Speech"**, pelo
link `portal.azure.com/#create/Microsoft.CognitiveServicesAIFoundry`.

**Não siga esse link.** O Foundry **não suporta o SKU F0**: ele provisiona em S0,
que é cobrado desde a primeira requisição. A camada gratuita só é selecionável no
recurso **Speech clássico**, em
`portal.azure.com/#create/Microsoft.CognitiveServices.Speech`.

## Roteiro: criar a subscrição, o recurso e obter a chave

Tudo no navegador. Nenhum passo aqui roda no PowerShell.

### Bloco 1 — a subscrição (só se você ainda não tiver uma)

O Microsoft 365 Business Premium **não inclui** a Azure. São contas e cobranças
separadas.

1. Abra `https://azure.microsoft.com/pt-br/pricing/purchase-options/azure-account`
   e clique em **Começar gratuitamente**.
2. Entre com a conta corporativa que você já usa no Microsoft 365.
3. Preencha o cadastro. **Ele pede cartão de crédito.**

   > **Passo irreversível — pare e confira.** O cartão é exigido mesmo na camada
   > gratuita. A conta gratuita dá US$ 200 de crédito válidos por 30 dias, e os
   > serviços "sempre gratuitos" continuam depois disso. O recurso que vamos criar
   > no bloco 2 é F0, que não consome o crédito. Mas a partir daqui existe um
   > cartão associado a uma conta de nuvem: só siga se você aceita isso.

4. Quando terminar, você deve cair no portal em `portal.azure.com` e ver
   **Subscrições** com uma entrada chamada *Avaliação Gratuita* ou *Azure
   subscription 1*. Se não aparecer nenhuma subscrição, o cadastro não concluiu —
   pare aqui e me diga o que a tela mostrou.

### Bloco 2 — o recurso de fala na camada gratuita

5. Abra exatamente este endereço:
   `https://portal.azure.com/#create/Microsoft.CognitiveServices.Speech`

   A tela deve se chamar **Criar Fala** (ou *Create Speech*). Se a tela falar
   "Foundry" ou "AI Services", você está no formulário errado — volte e use o
   endereço acima.

6. Preencha:
   - **Subscrição**: a que apareceu no passo 4.
   - **Grupo de recursos**: clique em *Criar novo* e chame de `clarisse`.
   - **Região**: **Brazil South**.
   - **Nome**: `clarisse-fala`.
   - **Tipo de preço**: **Gratuito F0**.

7. Se **Gratuito F0** não aparecer na lista de tipo de preço, **pare**. Significa
   que já existe um F0 nessa subscrição e região, ou que a região não oferece F0.
   Me diga quais opções apareceram, em vez de escolher S0 — S0 cobra.

8. Clique em **Revisar + criar** e depois em **Criar**. Espere a mensagem
   **"Sua implantação foi concluída"**. Leva menos de um minuto.

9. Clique em **Ir para o recurso**. No menu da esquerda, procure **Chaves e
   Ponto de Extremidade** (*Keys and Endpoint*).

10. Anote em local seguro, fora deste repositório:
    - o valor de **CHAVE 1**;
    - o valor de **Localização/Região**, que deve ser `brazilsouth`.

    > **Não me mande a chave, e não a cole em nenhum arquivo do projeto.** O
    > `config.json` é versionado: uma chave ali vai para o GitHub. No próximo
    > passo ela entra numa variável de ambiente do Windows, e o código lê de lá.

### Bloco 3 — guardar a chave sem versionar

Este bloco roda no **seu PowerShell**, mas só depois que eu escrever o Plano B —
o nome exato da variável faz parte dele. Fica registrado aqui para você saber que
existe e não colar a chave em nenhum arquivo enquanto espera.

## Consequências para o Plano B

1. A parte "gerar o modelo da palavra no Speech Studio" **sai** do Plano B.
   Entra "medir o Vosk com gramática restrita" como primeira tarefa.
2. A região passa a ser `brazilsouth`, e o orçamento de tempo do design pode ser
   recalculado para melhor: a chamada não sai do país.
3. Entra uma dependência nova: o pacote `vosk` e o modelo `vosk-model-small-pt-0.3`
   de 31 MB. O modelo **não** vai para o repositório — o instalador baixa.
4. A afirmação do design de que "nenhum áudio sai antes dela ouvir o nome" volta a
   ser literalmente verdadeira, e agora por construção: a detecção é local e não
   fala com nuvem nenhuma.
