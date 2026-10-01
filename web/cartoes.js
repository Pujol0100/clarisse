"use strict";

/* Cartões da resposta: entram na frente do anel enquanto a Clarisse fala e, quando ela termina,
   descem para a fileira do rodapé, que guarda os últimos. Todo texto entra por textContent: o que
   vem de fora (notícia, e-mail, resposta do modelo) nunca vira HTML. */

const Cartoes = (() => {
  const NA_FILEIRA = 6;
  const palco = document.getElementById("palco-cartao");
  const fileira = document.getElementById("fileira");
  let atual = null;

  function el(tag, classe, texto) {
    const e = document.createElement(tag);
    if (classe) e.className = classe;
    if (texto != null) e.textContent = texto;
    return e;
  }

  const MONTADORES = {
    clima(cartao, dado) {
      const linha = el("div", "clima");
      linha.append(el("span", "clima-temp", dado.temp), el("span", "clima-cond", dado.cond));
      const dias = el("div", "dias");
      for (const [nome, minima, maxima, chuva] of dado.dias || []) {
        const dia = el("div", "dia");
        dia.append(el("div", "dia-nome", nome), el("div", "dia-num", `${minima} · ${maxima}`), el("div", "dia-chuva", `chuva ${chuva}`));
        dias.append(dia);
      }
      cartao.append(linha, dias);
    },
    lista(cartao, dado) {
      const ul = el("ul", "lista");
      for (const [marca, texto] of dado.itens || []) {
        const li = el("li");
        li.append(el("span", "marca-item", marca), el("span", null, texto));
        ul.append(li);
      }
      cartao.append(ul);
    },
    texto(cartao, dado) {
      cartao.append(el("p", "texto-do-cartao", dado.texto));
    },
    // Lista numerada para escolher (manchetes, e-mails): clicar num item é como dizer "lê a notícia 2".
    escolha(cartao, dado) {
      const ul = el("ul", "lista");
      for (const item of dado.itens || []) {
        const li = el("li", "clicavel");
        li.dataset.numero = item.numero;
        li.tabIndex = 0;
        li.setAttribute("role", "button");
        const texto = el("span", "escolha-texto", item.titulo);
        if (item.detalhe) texto.append(el("span", "escolha-detalhe", item.detalhe));
        li.append(el("span", "marca-item", String(item.numero).padStart(2, "0")), texto);
        ul.append(li);
      }
      const escolher = (e) => {
        const li = e.target.closest("li[data-numero]");
        if (!li || (e.type === "keydown" && e.key !== "Enter")) return;
        li.classList.add("escolhida");
        aoEscolher(dado.pedido, Number(li.dataset.numero));
      };
      ul.addEventListener("click", escolher);
      ul.addEventListener("keydown", escolher);
      cartao.append(ul, el("p", "cartao-dica", "Diga o número ou clique para eu ler."));
    },
    leitura(cartao, dado) {
      const voltar = el("button", "leitura-voltar", "← Voltar à lista");
      voltar.type = "button";
      voltar.addEventListener("click", () => aoVoltar());
      cartao.append(voltar);
      if (dado.imagem) {
        const foto = el("img", "leitura-foto");
        foto.alt = "";
        foto.referrerPolicy = "no-referrer";
        foto.src = dado.imagem;
        foto.addEventListener("error", () => foto.remove());
        cartao.append(foto);
      }
      cartao.append(el("h2", "leitura-titulo", dado.titulo), el("p", "leitura-sub", dado.subtitulo || ""));
      const corpo = el("div", "leitura-corpo");
      for (const paragrafo of dado.paragrafos || []) corpo.append(el("p", null, paragrafo));
      cartao.append(corpo);
    },
  };

  function resumoDe(dado) {
    if (dado.resumo) return dado.resumo;
    if (dado.tipo === "clima") return `${dado.temp} · ${dado.cond}`;
    if (dado.tipo === "lista") return dado.canto || ((dado.itens || []).length === 1 ? "1 item" : `${(dado.itens || []).length} itens`);
    if (dado.tipo === "escolha") return dado.canto || `${(dado.itens || []).length} itens`;
    if (dado.tipo === "leitura") return dado.titulo;
    return dado.texto || "";
  }

  let aoEscolher = () => {};
  let aoVoltar = () => {};

  /** Na leitura de uma matéria: acende o parágrafo que está sendo lido e apaga os anteriores. */
  function marcarParagrafo(indice) {
    if (!atual || atual.dado.tipo !== "leitura") return;
    const paragrafos = atual.cartao.querySelectorAll(".leitura-corpo p");
    paragrafos.forEach((p, i) => {
      p.classList.toggle("lendo", i === indice);
      p.classList.toggle("lido", i < indice);
    });
    if (paragrafos[indice]) paragrafos[indice].scrollIntoView({ block: "nearest", behavior: "smooth" });
  }

  /** Fim da fala: o cartão desce para a fileira, menos o de escolha, que espera a pessoa escolher
      até o próximo cartão chegar. */
  function encerrar() {
    if (atual && atual.dado.tipo !== "escolha") guardar();
  }

  function lendo() {
    return Boolean(atual && atual.dado.tipo === "leitura");
  }

  /** Mostra o cartão na frente do anel; o anterior, se houver, desce para a fileira. */
  function mostrar(dado) {
    if (atual) guardar();
    const montar = MONTADORES[dado.tipo] || MONTADORES.texto;
    const cartao = el("article", `cartao cartao-${dado.tipo}`);
    for (let i = 0; i < 4; i++) cartao.append(el("i"));
    const titulo = el("div", "cartao-titulo");
    // Na leitura, o título já vem grande no corpo; o cabeçalho diz só o que é e de onde vem.
    const cabecalho = dado.tipo === "leitura" ? dado.rotulo || "" : dado.titulo || "";
    titulo.append(el("span", null, cabecalho), el("span", null, dado.canto || dado.fonte || ""));
    cartao.append(titulo);
    montar(cartao, dado);
    palco.append(cartao);
    requestAnimationFrame(() => requestAnimationFrame(() => cartao.classList.add("entrou")));
    atual = { cartao, dado };
  }

  /** O cartão da vez desce para a fileira. */
  function guardar() {
    if (!atual) return;
    const { cartao, dado } = atual;
    atual = null;
    cartao.classList.add("saindo");
    setTimeout(() => cartao.remove(), 650);
    const mini = el("div", "mini");
    mini.append(el("div", "mini-titulo", dado.titulo || ""), el("div", "mini-texto", resumoDe(dado)));
    // O mais novo entra à esquerda: se faltar espaço, some o mais antigo, à direita.
    fileira.prepend(mini);
    while (fileira.children.length > NA_FILEIRA) fileira.lastElementChild.remove();
  }

  return {
    mostrar,
    encerrar,
    marcarParagrafo,
    lendo,
    set aoEscolher(fn) { aoEscolher = fn; },
    set aoVoltar(fn) { aoVoltar = fn; },
  };
})();
