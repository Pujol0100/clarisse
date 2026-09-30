"use strict";

/* Rosto holográfico da Clarisse: rosto de frente desenhado com trilhas de circuito douradas, olhos
   acesos, boca que acompanha a voz e cabeça que segue o mouse. Do alto da cabeça e do pescoço saem
   trilhas até a borda da tela, com pulsos de luz correndo por elas.
   A base é o modelo canônico de rosto do Google MediaPipe (468 pontos, Apache 2.0). */

const Rosto = (() => {
  // O modelo é um rosto médio; estes ajustes dão traços femininos: queixo e mandíbula finos,
  // lábios cheios, olhos maiores e sobrancelhas arqueadas.
  function feminino(malha) {
    const olhos = [[-3.18, 2.62], [3.18, 2.62]];
    malha.v = malha.v.map(([x, y, z]) => {
      const baixo = Math.min(1, Math.max(0, (-2 - y) / 7));
      x *= 1 - 0.12 * baixo;
      if (Math.abs(x) < 2.7 && y > -5.6 && y < -3.2) { y = -4.3 + (y + 4.3) * 1.28; z += 0.18; }
      for (const [ox, oy] of olhos) {
        const d = Math.hypot(x - ox, y - oy);
        if (d < 2.2) { const f = 1 + 0.12 * (1 - d / 2.2); x = ox + (x - ox) * f; y = oy + (y - oy) * f; }
      }
      if (y > 3.6 && y < 5.2 && Math.abs(x) > 1 && Math.abs(x) < 6.2) y += 0.3 * Math.sin(((Math.abs(x) - 1) / 5.2) * Math.PI);
      return [x, y, z];
    });
    return malha;
  }

  const MALHA = feminino(MALHA_DO_ROSTO);
  const MOVIMENTO_REDUZIDO = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  // Dourado da marca em todos os estados; o vermelho só no erro, que é status.
  const CORES = {
    idle: [201, 168, 76], listening: [229, 200, 117], thinking: [236, 222, 176],
    executing: [229, 200, 117], speaking: [229, 200, 117], error: [229, 72, 77],
  };

  // Contornos do modelo MediaPipe (índices dos pontos).
  const CONTORNOS = [
    [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109, 10],
    [33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246, 33],
    [263, 249, 390, 373, 374, 380, 381, 382, 362, 398, 384, 385, 386, 387, 388, 466, 263],
    [61, 146, 91, 181, 84, 17, 314, 405, 321, 375, 291, 409, 270, 269, 267, 0, 37, 39, 40, 185, 61],
    [78, 95, 88, 178, 87, 14, 317, 402, 318, 324, 308, 415, 310, 311, 312, 13, 82, 81, 80, 191, 78],
    [46, 53, 52, 65, 55, 70, 63, 105, 66, 107],
    [276, 283, 282, 295, 285, 300, 293, 334, 296, 336],
    [168, 6, 197, 195, 5, 4, 1, 19, 94, 2],
    [48, 115, 220, 45, 4, 275, 440, 344, 278],
    [98, 97, 2, 326, 327],
  ];
  const PALPEBRAS = [
    { cima: [246, 161, 160, 159, 158, 157, 173], baixo: [7, 163, 144, 145, 153, 154, 155], centro: [-3.18, 2.62, 4.05] },
    { cima: [466, 388, 387, 386, 385, 384, 398], baixo: [249, 390, 373, 374, 380, 381, 382], centro: [3.18, 2.62, 4.05] },
  ];
  const BOCA_Y = -4.3;
  // Até onde as trilhas de fora vão, em unidades do rosto: além da borda de qualquer tela.
  const LIMITE_X = 40, LIMITE_Y = 26;

  function sorteio(semente) {
    return () => {
      semente |= 0; semente = (semente + 0x6d2b79f5) | 0;
      let t = Math.imul(semente ^ (semente >>> 15), 1 | semente);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const acaso = sorteio(20260930);

  const vizinhos = MALHA.v.map(() => new Set());
  for (const [a, b, c] of MALHA.f) {
    vizinhos[a].add(b).add(c); vizinhos[b].add(a).add(c); vizinhos[c].add(a).add(b);
  }

  // Trilhas sobre o rosto: caminhadas pela malha numa direção preferida, como trilhas de placa.
  const trilhas = [];
  const DIRECOES = [[0, -1], [0, 1], [1, 0], [-1, 0], [0.7, -0.7], [-0.7, -0.7]];
  for (let n = 0; n < 150; n++) {
    let atual = Math.floor(acaso() * MALHA.v.length);
    const [dx, dy] = DIRECOES[Math.floor(acaso() * DIRECOES.length)];
    const caminho = [atual];
    const tamanho = 4 + Math.floor(acaso() * 8);
    while (caminho.length < tamanho) {
      let melhor = null, nota = 0.35;
      for (const k of vizinhos[atual]) {
        if (caminho.includes(k)) continue;
        const [x0, y0] = MALHA.v[atual], [x1, y1] = MALHA.v[k];
        const d = Math.hypot(x1 - x0, y1 - y0) || 1;
        const n2 = ((x1 - x0) * dx + (y1 - y0) * dy) / d;
        if (n2 > nota) { nota = n2; melhor = k; }
      }
      if (melhor === null) break;
      caminho.push(melhor); atual = melhor;
    }
    if (caminho.length > 2) trilhas.push(caminho);
  }

  // Trilhas de fora: saem do rosto e vão até a borda da tela, cada uma com pulsos de luz.
  const oval = CONTORNOS[0].slice(0, -1).map((k) => MALHA.v[k]);
  const livres = [];
  function trilhaLivre(inicio, passo) {
    const pontos = [inicio];
    let [x, y, z] = inicio;
    const lado = Math.sign(x) || (acaso() < 0.5 ? -1 : 1);
    while (Math.abs(x) < LIMITE_X && Math.abs(y) < LIMITE_Y && pontos.length < 40) {
      const [ax, ay] = passo(x, y, lado);
      x += ax; y += ay; z -= 0.2;
      pontos.push([x, y, z]);
    }
    livres.push({ pontos, velocidade: 0.18 + acaso() * 0.3, atraso: acaso() * 6000 });
  }
  const raizes = [...oval.filter(([, y]) => y > 1.5), ...MALHA.v.filter(([, y]) => y > 5.6)];
  for (let i = 0; i < 80; i++) {
    const p = raizes[Math.floor(acaso() * raizes.length)];
    trilhaLivre([p[0], p[1], p[2] - 0.5], (x, y, lado) => {
      const abre = 0.4 + Math.abs(x) / 6 + Math.max(0, y - 10) / 5;
      return [acaso() < 0.4 ? 0 : lado * (0.4 + acaso() * 1.4) * abre, acaso() < 0.25 && y > 12 ? 0 : 0.9 + acaso() * 1.8];
    });
  }
  const queixo = oval.filter(([, y]) => y < -5);
  for (let i = 0; i < 56; i++) {
    const p = queixo[Math.floor(acaso() * queixo.length)];
    trilhaLivre([p[0] * 0.85, p[1], p[2] - 0.8], (x, y, lado) => {
      const ombro = y < -14 ? 2.6 + acaso() * 2 : 0.4;
      return [acaso() < 0.4 ? 0 : lado * (0.4 + acaso() * 1.2) * ombro, y < -16 && acaso() < 0.5 ? -0.3 : -(0.9 + acaso() * 2.2)];
    });
  }

  // Quanto cada ponto desce quando a boca abre: o queixo cai inteiro, menos perto das orelhas.
  const pesoDoQueixo = MALHA.v.map(([x, y]) => Math.min(1, Math.max(0, (BOCA_Y + 0.15 - y) / 0.5)) * Math.max(0, 1 - (x / 8) ** 2));

  let tela, pincel;
  let estado = "idle";
  let abertura = 0;
  let piscada = 0;
  let cor = CORES.idle.slice();
  let alvo = [0, 0];
  let olhar = [0, 0];
  let noCanto = false;
  let lugar = { x: 0.5, y: 0.47, tamanho: 1 };
  let contornoNaTela = null;

  function ajustarTamanho() {
    const escala = window.devicePixelRatio || 1;
    tela.width = Math.round(tela.clientWidth * escala);
    tela.height = Math.round(tela.clientHeight * escala);
  }

  function pontosDoQuadro() {
    const v = MALHA.v.map(([x, y, z], i) => [x, y - pesoDoQueixo[i] * abertura * 1.6, z]);
    for (const olho of PALPEBRAS) {
      olho.cima.forEach((k, j) => {
        const baixo = MALHA.v[olho.baixo[j]];
        v[k] = [v[k][0], v[k][1] + (baixo[1] - v[k][1]) * piscada, v[k][2]];
      });
    }
    return v;
  }

  function projetor(tempo) {
    const balanco = MOVIMENTO_REDUZIDO ? 0 : Math.sin(tempo / 2600) * 0.03;
    const giro = olhar[0] * 0.45 + balanco;
    const inclinacao = olhar[1] * 0.28;
    const [cg, sg, ci, si] = [Math.cos(giro), Math.sin(giro), Math.cos(inclinacao), Math.sin(inclinacao)];
    const w = tela.width, h = tela.height;
    const escala = (Math.min(w, h * 1.1) / 36) * lugar.tamanho;
    const cx = w * lugar.x, cy = h * lugar.y;
    return ([x, y, z]) => {
      const x1 = x * cg + z * sg;
      const z1 = -x * sg + z * cg;
      const y2 = y * ci - z1 * si;
      const z2 = y * si + z1 * ci;
      const p = 40 / (40 - Math.min(z2, 30));
      return [cx + x1 * escala * p, cy - (y2 + 1) * escala * p, z2];
    };
  }

  // Trilha de placa: diagonal primeiro, depois reta, entre cada par de pontos.
  function comCotovelos(pontos) {
    const saida = [pontos[0]];
    for (let i = 1; i < pontos.length; i++) {
      const [x0, y0] = pontos[i - 1], [x1, y1] = pontos[i];
      const dx = x1 - x0, dy = y1 - y0;
      const d = Math.min(Math.abs(dx), Math.abs(dy));
      saida.push([x0 + Math.sign(dx) * d, y0 + Math.sign(dy) * d], [x1, y1]);
    }
    return saida;
  }

  function brilho(p, raio, alfa, rgb = cor) {
    const g = pincel.createRadialGradient(p[0], p[1], 0, p[0], p[1], raio);
    g.addColorStop(0, `rgba(255,255,255,${alfa})`);
    g.addColorStop(0.25, `rgba(${rgb.join(",")},${alfa * 0.85})`);
    g.addColorStop(1, `rgba(${rgb.join(",")},0)`);
    pincel.fillStyle = g;
    pincel.beginPath(); pincel.arc(p[0], p[1], raio, 0, Math.PI * 2); pincel.fill();
  }

  function ponto(p, r, alfa) {
    pincel.fillStyle = `rgba(${cor.map((c) => Math.min(255, c + 45)).join(",")},${alfa})`;
    pincel.beginPath(); pincel.arc(p[0], p[1], r, 0, Math.PI * 2); pincel.fill();
  }

  function camada(listas, largura, alfa) {
    pincel.lineWidth = largura;
    pincel.strokeStyle = `rgba(${cor.join(",")},${alfa})`;
    pincel.beginPath();
    for (const pontos of listas) {
      pincel.moveTo(pontos[0][0], pontos[0][1]);
      for (let i = 1; i < pontos.length; i++) pincel.lineTo(pontos[i][0], pontos[i][1]);
    }
    pincel.stroke();
  }

  // Pulso de luz correndo pela trilha, do rosto para fora.
  function pulso(pontos, distancia, comprimento, largura) {
    let percorrido = 0;
    const rastro = [];
    for (let i = 1; i < pontos.length; i++) {
      const [x0, y0] = pontos[i - 1], [x1, y1] = pontos[i];
      const trecho = Math.hypot(x1 - x0, y1 - y0);
      const inicio = Math.max(percorrido, distancia - comprimento), fim = Math.min(percorrido + trecho, distancia);
      if (fim > inicio && trecho > 0) {
        const a = (inicio - percorrido) / trecho, b = (fim - percorrido) / trecho;
        rastro.push([[x0 + (x1 - x0) * a, y0 + (y1 - y0) * a], [x0 + (x1 - x0) * b, y0 + (y1 - y0) * b]]);
      }
      percorrido += trecho;
      if (percorrido > distancia) break;
    }
    if (!rastro.length) return;
    pincel.lineWidth = largura;
    pincel.strokeStyle = "rgba(255,244,214,0.85)";
    pincel.beginPath();
    for (const [a, b] of rastro) { pincel.moveTo(a[0], a[1]); pincel.lineTo(b[0], b[1]); }
    pincel.stroke();
    brilho(rastro[rastro.length - 1][1], largura * 6, 0.9, [229, 200, 117]);
  }

  function quadro(tempo) {
    olhar = olhar.map((o, i) => o + (alvo[i] - o) * 0.06);
    const meta = CORES[estado] || CORES.idle;
    cor = cor.map((c, i) => Math.round(c + (meta[i] - c) * 0.06));
    const destino = noCanto ? { x: 0.1, y: 0.16, tamanho: 0.3 } : { x: 0.5, y: 0.47, tamanho: 1 };
    const suave = MOVIMENTO_REDUZIDO ? 1 : 0.07;
    lugar = { x: lugar.x + (destino.x - lugar.x) * suave, y: lugar.y + (destino.y - lugar.y) * suave, tamanho: lugar.tamanho + (destino.tamanho - lugar.tamanho) * suave };

    const w = tela.width, h = tela.height;
    pincel.clearRect(0, 0, w, h);
    pincel.globalCompositeOperation = "lighter";
    pincel.lineJoin = "round";

    const projetar = projetor(tempo);
    const p = pontosDoQuadro().map(projetar);
    const fino = Math.max(0.7, (h / 900) * Math.max(0.6, lugar.tamanho));
    const doRosto = trilhas.map((t) => comCotovelos(t.map((k) => p[k])));
    const contornos = CONTORNOS.map((c) => comCotovelos(c.map((k) => p[k])));
    contornoNaTela = CONTORNOS[0].map((k) => p[k]);
    const deFora = livres.map((l) => comCotovelos(l.pontos.map(projetar)));

    // Duas passadas: uma larga e fraca (o brilho) e uma fina e forte (a trilha).
    for (const [largura, alfa] of [[fino * 4, 0.06], [fino, 0.5]]) {
      camada(deFora, largura, alfa * 0.7);
      camada(doRosto, largura, alfa);
      camada(contornos, largura * 1.2, Math.min(1, alfa * 1.6));
    }

    for (const lista of doRosto) { ponto(lista[lista.length - 1], fino * 1.8, 0.9); ponto(lista[0], fino * 1.3, 0.6); }
    deFora.forEach((lista) => lista.forEach((q, i) => { if (i % 4 === 0) ponto(q, fino * 1.5, 0.7); }));
    contornos.forEach((c) => c.forEach((q, i) => { if (i % 4 === 0) ponto(q, fino * 1.3, 0.75); }));

    // Corrente: um pulso de luz por trilha de fora, saindo do rosto em direção à borda.
    if (!MOVIMENTO_REDUZIDO) {
      livres.forEach((l, i) => {
        const trajeto = deFora[i];
        let total = 0;
        for (let k = 1; k < trajeto.length; k++) total += Math.hypot(trajeto[k][0] - trajeto[k - 1][0], trajeto[k][1] - trajeto[k - 1][1]);
        const ciclo = total * 1.8;
        const distancia = ((tempo + l.atraso) * l.velocidade * (h / 900)) % ciclo;
        if (distancia < total + 60) pulso(trajeto, distancia, 60 * (h / 900), fino * 1.6);
      });
    }

    // Olhos acesos, que acompanham o mouse um pouco além da cabeça e somem ao piscar.
    for (const olho of PALPEBRAS) {
      const centro = projetar([olho.centro[0] + olhar[0] * 0.5, olho.centro[1] - olhar[1] * 0.35, olho.centro[2]]);
      const aceso = (1 - piscada) * (estado === "listening" ? 1 : 0.9);
      const raio = h * lugar.tamanho;
      brilho(centro, raio * 0.07, 0.3 * aceso);
      brilho(centro, raio * 0.018, aceso);
    }

    pincel.globalCompositeOperation = "source-over";
    requestAnimationFrame(quadro);
  }

  function piscar() {
    const inicio = performance.now();
    const passo = () => {
      const t = (performance.now() - inicio) / 160;
      piscada = t < 1 ? Math.sin(t * Math.PI) : 0;
      if (t < 1) requestAnimationFrame(passo);
    };
    requestAnimationFrame(passo);
    setTimeout(piscar, 2500 + Math.random() * 3500);
  }

  function seguir(evento) {
    const caixa = tela.getBoundingClientRect();
    const cx = caixa.left + caixa.width * lugar.x, cy = caixa.top + caixa.height * lugar.y;
    alvo = [
      Math.max(-1, Math.min(1, (evento.clientX - cx) / (window.innerWidth / 2))),
      Math.max(-1, Math.min(1, (evento.clientY - cy) / (window.innerHeight / 2))),
    ];
  }

  return {
    iniciar(elemento) {
      tela = elemento;
      pincel = tela.getContext("2d");
      window.addEventListener("resize", ajustarTamanho);
      window.addEventListener("pointermove", seguir);
      document.documentElement.addEventListener("pointerleave", () => { alvo = [0, 0]; });
      ajustarTamanho();
      requestAnimationFrame(quadro);
      if (!MOVIMENTO_REDUZIDO) setTimeout(piscar, 1800);
    },
    estado(novo) { estado = novo; },
    abertura(v) { abertura = Math.max(0, Math.min(1, v)); },
    canto(sim) { noCanto = sim; },
    // Centro do rosto em pixels da página: de onde os drones saem para formar as figuras.
    centro() {
      const caixa = tela.getBoundingClientRect(), f = caixa.width / tela.width;
      if (!contornoNaTela) return { x: caixa.left + caixa.width / 2, y: caixa.top + caixa.height / 2 };
      const xs = contornoNaTela.map((q) => q[0]), ys = contornoNaTela.map((q) => q[1]);
      return { x: caixa.left + ((Math.min(...xs) + Math.max(...xs)) / 2) * f, y: caixa.top + ((Math.min(...ys) + Math.max(...ys)) / 2) * f };
    },
  };
})();


const legenda = document.getElementById("legenda");
let volume = 0;
let fimDaFala = 0;
let silabas = [];
Enxame.iniciar(document.getElementById("enxame"));
Rosto.iniciar(document.getElementById("malha"));
Enxame.origem = () => Rosto.centro();
Enxame.nivel = () => volume;

function simularVoz(agora) {
  if (agora < fimDaFala) {
    const t = agora / 1000;
    const onda = Math.abs(Math.sin(t * 9.3)) * 0.6 + Math.abs(Math.sin(t * 3.1 + 1)) * 0.4;
    const pausa = Math.sin(t * 1.7) > 0.85 ? 0.1 : 1;
    volume += (onda * pausa - volume) * 0.35;
  } else {
    volume += (0 - volume) * 0.3;
  }
  Rosto.abertura(volume);
  requestAnimationFrame(simularVoz);
}
requestAnimationFrame(simularVoz);

function marcar(estado) {
  document.querySelectorAll("[data-estado]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.estado === estado)));
}

function mudarEstado(estado, texto) {
  Rosto.estado(estado); Enxame.estado(estado); marcar(estado);
  legenda.textContent = texto;
}

let temporizador;
function falar(segundos, figura) {
  clearTimeout(temporizador);
  mudarEstado("speaking", figura
    ? "Apresentando: os drones saem do rosto e formam a figura no meio; o rosto vai para o canto e continua falando."
    : "Conversando: a boca acompanha a voz.");
  Rosto.canto(Boolean(figura));
  Enxame.mostrar(figura || null);
  fimDaFala = performance.now() + segundos * 1000;
  temporizador = setTimeout(() => {
    Enxame.mostrar(null);
    Rosto.canto(false);
    mudarEstado("idle", "Terminou de falar: o rosto volta ao centro.");
  }, segundos * 1000 + 300);
}

document.querySelectorAll("[data-estado]").forEach((b) => b.addEventListener("click", () => {
  clearTimeout(temporizador); fimDaFala = 0;
  Enxame.mostrar(null); Rosto.canto(false);
  const textos = { idle: "Parada: o rosto no centro, com a corrente passando pelas trilhas.", listening: "Ouvindo: olhos mais abertos, cor verde-água.", thinking: "Pensando: olhar para o alto, cor lilás, drones piscando." };
  mudarEstado(b.dataset.estado, textos[b.dataset.estado]);
}));
document.getElementById("falar").addEventListener("click", () => falar(5));
document.querySelectorAll("[data-figura]").forEach((b) => b.addEventListener("click", () => falar(7, b.dataset.figura)));
if (location.hash.length > 1) falar(60, location.hash.slice(1));
