# Visual novo, só Gemma e conectores — plano

> Para quem executa: siga as fases na ordem. Cada tarefa é TDD: escreva o teste, veja falhar,
> implemente o mínimo, veja passar, faça commit. Antes de rodar a suíte inteira, rode `free -g`
> (coluna "disponível" ≥ 8) e use só os testes do arquivo que mudou durante o trabalho.

**Objetivo:** trocar o rosto e os drones por um anel com constelação de ferramentas e cartões
(formato dos vídeos de 01/10/2026), deixar a Clarisse respondendo só com a Gemma, e ligar
conectores que rodam aqui ou só leem.

**Decisões do usuário em 01/10/2026:**
- Fica a `gemma4:e4b-it-qat` (o Qwen mediu 2,7× mais lento em 28/09).
- Sai o rosto (as pessoas tiveram medo) e saem os drones.
- Voz é o principal. Um botão "Escrever" abre o chat à direita e leva a Clarisse para a esquerda.
- Falar: aperta a tecla, grava; aperta de novo, para e envia (Ctrl+Alt+C fora da página, espaço na página).
- Notícia: escolher por número falado ou clique; o cartão vira bloco de leitura e ela lê a matéria inteira.
- Claude fora "por hora": sai tudo que delega ao Claude. Ficam "abre o Claude no projeto X" e
  "lê a última coisa que o Claude disse (no projeto X)".
- Conectores: agenda, e-mail, GitHub, Obsidian, Dokploy, lembretes. ClickUp não.

**Referência visual:** `docs/prototipos/2026-10-01-orbe-e-cartoes.html` (abrir no navegador;
`?cena=3` começa nas notícias). O CSS e o desenho do canvas saem de lá.

**Arquitetura:** o servidor continua mandando eventos pelo WebSocket. Muda o que vai neles:
cada ferramenta declara o `grupo` (nó da constelação) e pode devolver um `cartao` (dados
estruturados). A página desenha anel, constelação e cartões a partir desses eventos.

**Riscos que o usuário precisa saber:**
- Sem o Claude, perguntas de fato do mundo (empresa, preço, cotação) passam a receber "não sei".
  O Gemma inventa fatos quando tenta (medição de 28/09); a regra do prompt proíbe.
- Conteúdo de fora (e-mail, notícia, nota) entra no contexto da Gemma, que tem ferramentas que agem
  (digitar, atalho, git). Um e-mail pode trazer instrução maliciosa. Mitigação: o texto lido na
  íntegra vai direto para a voz (`na_integra`) e não volta ao modelo; o resumo do e-mail usa só
  remetente e assunto; ações continuam passando pela confirmação do sistema.
- A voz (edge-tts) é serviço da Microsoft: o que ela fala sai da máquina. Fica como está.

---

## Fase 1 — Tela nova (anel, constelação, cartões, escrita opcional)

**Arquivos:**
- Criar: `web/nucleo.js` (canvas: anel, globo, filamentos, régua, poeira, constelação)
- Criar: `web/cartoes.js` (montar cartão, levar à fileira, bloco de leitura)
- Reescrever: `web/index.html`, `web/estilo.css`, `web/app.js`
- Apagar: `web/rosto.js`, `web/malha-rosto.js`, `web/enxame.js`, `web/licencas/mediapipe-LICENSE.txt`
- Testes: `tests/test_pagina.py`

### Tarefa 1.1 — a página carrega o núcleo e os cartões, sem rosto nem drones

- [ ] Reescrever em `tests/test_pagina.py` os testes de rosto/malha/MediaPipe por:

```python
def test_pagina_carrega_nucleo_e_cartoes_antes_do_app_e_nada_do_rosto():
    scripts = _scripts_da_pagina()

    assert {"nucleo.js", "cartoes.js", "app.js"} <= set(scripts)
    assert scripts.index("nucleo.js") < scripts.index("app.js")
    assert scripts.index("cartoes.js") < scripts.index("app.js")
    assert not {"rosto.js", "malha-rosto.js", "enxame.js"} & set(scripts)
    assert not (WEB / "rosto.js").exists() and not (WEB / "enxame.js").exists()


def test_pagina_tem_o_canvas_do_nucleo_e_os_lugares_dos_cartoes():
    pagina = (WEB / "index.html").read_text(encoding="utf-8")

    for id_ in ("nucleo", "palco-cartao", "fileira", "legenda", "voce"):
        assert f'id="{id_}"' in pagina
```

- [ ] Rodar `uv run pytest tests/test_pagina.py -q` → falha (ainda há `rosto.js`).
- [ ] Criar `web/nucleo.js` a partir do protótipo como módulo `Nucleo` com a interface:
  `Nucleo.iniciar(canvas)`, `Nucleo.estado(nome)`, `Nucleo.nivel = () => 0..1`,
  `Nucleo.grupos(lista)`, `Nucleo.acender(grupo, ligado)`, `Nucleo.espaco(larguraDoChat)`.
- [ ] Criar `web/cartoes.js` com `Cartoes.mostrar(dado)`, `Cartoes.guardar()`,
  `Cartoes.ler(materia)`, `Cartoes.marcarParagrafo(i)`; tudo com `textContent`, nunca `innerHTML`.
- [ ] Atualizar `index.html` e `estilo.css`; apagar rosto, malha, enxame e a licença do MediaPipe.
- [ ] Ajustar `test_scripts_so_procuram_elementos_que_existem_na_pagina` e
  `test_mensagens_do_chat_sao_criadas_como_texto_e_nunca_como_html` para olhar também
  `cartoes.js` e `nucleo.js`.
- [ ] Teste passa. Commit: "Tela nova: anel e cartoes no lugar do rosto e dos drones".

### Tarefa 1.2 — escrita só quando a pessoa pede

- [ ] Teste:

```python
def test_escrever_e_opcional_e_o_chat_comeca_fechado():
    pagina = (WEB / "index.html").read_text(encoding="utf-8")

    assert re.search(r'<button[^>]+id="escrever"[^>]+aria-expanded="false"', pagina)
    assert re.search(r'<aside[^>]+id="chat"', pagina)
    assert 'class="com-chat"' not in pagina
    assert pagina.index('id="chat"') < pagina.index('id="formulario"')
```

- [ ] Implementar o botão, o painel e a classe `com-chat` no `body` (CSS do protótipo).
  Fechado, a página não tem campo de texto visível. Confirmar/cancelar continuam por voz
  ("sim"/"não") e aparecem como botões só dentro do chat aberto.
- [ ] Commit: "Escrever vira opcao: o chat abre a direita so quando pedido".

### Tarefa 1.3 — conferência no navegador real

- [ ] `free -g`; ligar a Clarisse (`scripts/ligar.sh`) na worktree.
- [ ] Pelo Playwright: estados (Ouvindo/Pensando/Falando), legenda, abrir e fechar o chat,
  mandar "que horas são" escrito. Ler tempos com `browser_evaluate` (a foto chega atrasada).
- [ ] Desligar com `scripts/desligar.sh`.

## Fase 2 — Cartões com dados do servidor

**Arquivos:** `clarisse/figuras.py` (Retorno), `clarisse/ferramentas/registro.py` (grupo),
`clarisse/agente.py`, `clarisse/web.py`, `clarisse/ferramentas/tempo.py`,
`clarisse/ferramentas/noticias.py`, todas as ferramentas (declarar `grupo`), `web/app.js`.
Testes: `tests/test_figuras.py`, `tests/test_agente.py`, `tests/test_web.py`,
`tests/test_tempo.py`, `tests/test_noticias.py`.

### Tarefa 2.1 — toda ferramenta declara o nó da constelação

Grupos: `agenda, clima, noticias, email, github, notas, servidores, lembretes, claude, codigo,
navegador, janelas, sistema`.

```python
GRUPOS = {"agenda", "clima", "noticias", "email", "github", "notas", "servidores",
          "lembretes", "claude", "codigo", "navegador", "janelas", "sistema"}


def test_cada_ferramenta_declara_um_grupo_da_constelacao(cadastros, executor, tmp_path):
    registro = _montar(cadastros, executor, tmp_path)

    sem_grupo = [n for n in registro.nomes() if registro.obter(n).grupo not in GRUPOS]
    assert sem_grupo == []
    assert registro.obter("previsao_do_tempo").grupo == "clima"
    assert registro.obter("git").grupo == "codigo"
```

- `Ferramenta` ganha `grupo: str = "sistema"`; o evento `ferramenta` (iniciada/concluída)
  passa a levar `"grupo"`; a página acende o nó.

### Tarefa 2.2 — a resposta leva o cartão

```python
async def test_resposta_traz_o_cartao_da_ferramenta(...):
    # ferramenta falsa devolve Retorno("26 graus", cartao={"tipo": "clima", "titulo": "Clima"})
    resposta = await agente.responder("como está o tempo")
    assert resposta.cartao == {"tipo": "clima", "titulo": "Clima"}


async def test_ferramenta_sem_cartao_gera_cartao_de_texto(...):
    resposta = await agente.responder("que horas são")
    assert resposta.cartao == {"tipo": "texto", "titulo": "Hora e data", "texto": resposta.texto}
```

- `Retorno` ganha `cartao: dict | None`; `Resposta` ganha `cartao`; `web.processar` manda
  `"cartao"` no evento `resposta`. Resposta sem ferramenta não tem cartão (só legenda).

### Tarefa 2.3 — clima e notícias com cartão próprio

- Clima: `{"tipo": "clima", "titulo": "Clima", "canto": cidade, "temp": "26°", "cond": ...,
  "dias": [[rótulo, mín, máx, chuva%] × 3]}`. Teste com resposta do Open-Meteo gravada.
- Notícias: `{"tipo": "noticias", "titulo": "Notícias", "canto": tema,
  "itens": [{"numero": 1, "titulo", "imagem", "link"}]}`. Teste com RSS do g1 gravado em
  `tests/dados/g1-tecnologia.xml` (cortar para 3 itens; manter a forma do original).

## Fase 3 — Leitura de notícia

### Tarefa 3.1 — limpar o texto da matéria do feed

```python
def test_materia_fica_so_com_paragrafos_de_frase():
    descricao = (
        '<img src="x.jpg" /><br />   Título de vídeo relacionado sem ponto\n'
        "A polícia informou nesta quinta-feira que prendeu o suspeito.\n"
        "Ele é suspeito de coordenar o grupo, informou a porta-voz.\n"
        "*Com informações da Reuters.\n"
        "Cybercrime; hacker; crimes digitais\n"
        "Kevin Horvart/Unplash"
    )
    assert paragrafos_da_materia(descricao) == [
        "A polícia informou nesta quinta-feira que prendeu o suspeito.",
        "Ele é suspeito de coordenar o grupo, informou a porta-voz.",
    ]
```

Regra: linha sem tag HTML, com pelo menos 6 palavras, terminando em `.`, `!`, `?` ou `"`;
descarta a linha que começa com `*`.

### Tarefa 3.2 — `ler_noticia(numero | assunto)`

- A última lista de notícias fica guardada na ferramenta (por tema). "Lê a segunda" → número 2;
  "lê a do WhatsApp" → título que contém a palavra. Sem lista guardada: busca a geral.
- Devolve `Retorno(texto, na_integra=True, cartao={"tipo": "leitura", "titulo", "subtitulo",
  "imagem", "fonte", "paragrafos": [...]})`.
- A voz já fala em trechos; cada trecho do evento `falar` passa a levar `"paragrafo": i` para a
  página acender o parágrafo da vez. Teste em `tests/test_web.py`: trechos de uma leitura levam
  o índice do parágrafo de onde saíram.
- Clique numa manchete manda `POST /api/mensagem {"texto": "lê a notícia 2"}`.

## Fase 4 — Só Gemma

### Tarefa 4.1 — chave `CLARISSE_USAR_CLAUDE` (padrão desligada)

```python
def test_sem_claude_nao_registra_quem_delega_ao_claude(...):
    registro = _montar(..., usar_claude=False)
    for nome in ("pedir_ao_claude", "fazer_em_etapas", "fazer_no_navegador",
                 "mandar_para_conversa_do_claude", "consultar_agenda", "criar_compromisso"):
        assert nome not in registro.nomes()
    assert "abrir_claude_na_tela" in registro.nomes()
    assert "ler_resposta_do_claude" in registro.nomes()
```

- Prompt sem Claude: tira as regras de delegação; acrescenta "Você não tem acesso à internet
  para pesquisar. Para fatos do mundo que nenhuma ferramenta traz, diga que não sabe."
  Os desvios `_ENCADEADO`, `_QUER_O_CLAUDE` e a garantia "cita Claude vai ao Claude" só valem
  com a chave ligada. Teste: com a chave desligada, "pesquisa o preço do dólar" responde sem
  chamar ferramenta inexistente.

### Tarefa 4.2 — "lê o que o Claude disse no projeto X"

```python
async def test_le_a_ultima_resposta_do_projeto_pelo_nome(tmp_path, cadastros):
    # conversas em tmp_path/<pasta-do-projeto>/a.jsonl (velha) e b.jsonl (nova)
    resultado = await ler(ArgsLeitura(projeto="omni api"))
    assert resultado.texto == "resposta da conversa nova"
```

- `ArgsLeitura` ganha `projeto`; acha o projeto pelo cadastro (aceita erro de transcrição),
  procura a conversa mais recente na pasta do projeto **e nas worktrees dele**
  (`*-worktrees-<nome>-*`).

## Fase 5 — Conectores

Cada conector é só leitura, tem grupo próprio e cartão. Um commit por conector.

### 5.1 Agenda e e-mail pelo Outlook (conta do GNOME)

- `clarisse/microsoft.py`: `token()` pede o token à conta `ms_graph` do GNOME Online Accounts
  por `gdbus` (`OAuth2Based.GetAccessToken`); `graph(caminho, parametros)` faz `GET` em
  `https://graph.microsoft.com/v1.0`. Nunca registra o token em log.
- `consultar_agenda(periodo)` → `GET /me/calendarView` (já expande recorrência). Cartão lista
  `[hora, título]`. Teste com resposta do Graph gravada e cliente HTTP falso.
- `emails_nao_lidos()` → `GET /me/mailFolders/inbox/messages?$filter=isRead eq false&$top=10&
  $select=from,subject,receivedDateTime`. Cartão lista remetente e assunto. O resumo falado usa
  só remetente e assunto.
- `ler_email(numero)` → `GET /me/messages/{id}?$select=body` (texto), `na_integra=True`.
- Criar compromisso fica para depois (decisão de 01/10/2026).

### 5.2 GitHub (`gh`, já logado)

- `prs_para_revisar()` → `gh search prs --review-requested=@me --state=open --json ...`
- `situacao_da_pr(repo, numero)` → `gh pr checks`. Testes com executor falso e saída gravada.

### 5.3 Obsidian (cofre "Pujol's memory")

- `buscar_nas_notas(termo)` → procura no texto dos `.md` do cofre (pasta em `config/notas.json`),
  devolve os 5 títulos com trecho. `ler_nota(titulo)` → `na_integra=True`.

### 5.4 Dokploy (só leitura, chave que já existe em `sites.py`)

- `situacao_do_sistema(nome)` → status da aplicação e último deploy.

### 5.5 Lembretes

- `lembrar(quando, texto)`; guardado em `dados/lembretes.json`; tarefa de fundo dispara pelo
  `avisador` (voz + cartão). `listar_lembretes()`, `cancelar_lembrete(numero)` (confirma).

## Conferência final

- `free -g`; suíte inteira uma vez: `uv run pytest -q`.
- Clarisse ligada, conferência pelo Playwright de cada fase.
- Atalho Ctrl+Alt+C: rodar `scripts/instalar-atalho.sh` (não está cadastrado nesta máquina em 01/10/2026).
- PR em cima da `assistente-local` (a PR #9 continua aberta).
