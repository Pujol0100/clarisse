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
      cartao.append(el("p", "cartao-texto", dado.texto));
    },
  };

  function resumoDe(dado) {
    if (dado.resumo) return dado.resumo;
    if (dado.tipo === "clima") return `${dado.temp} · ${dado.cond}`;
    if (dado.tipo === "lista") return `${(dado.itens || []).length} itens`;
    return dado.texto || "";
  }

  /** Mostra o cartão na frente do anel; o anterior, se houver, desce para a fileira. */
  function mostrar(dado) {
    if (atual) guardar();
    const montar = MONTADORES[dado.tipo] || MONTADORES.texto;
    const cartao = el("article", `cartao cartao-${dado.tipo}`);
    for (let i = 0; i < 4; i++) cartao.append(el("i"));
    const titulo = el("div", "cartao-titulo");
    titulo.append(el("span", null, dado.titulo || ""), el("span", null, dado.canto || ""));
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
    fileira.append(mini);
    while (fileira.children.length > NA_FILEIRA) fileira.firstElementChild.remove();
  }

  return { mostrar, guardar };
})();
