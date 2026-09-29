"use strict";

/* Enxame de "drones" de luz: esfera quando parada, onda quando fala, figuras quando a resposta pede. */

const Enxame = (() => {
  const MOVIMENTO_REDUZIDO = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const QUANTIDADE = MOVIMENTO_REDUZIDO ? 400 : 900;

  const CORES_DOS_ESTADOS = {
    idle: "#7fa7d9", listening: "#3fd6c6", thinking: "#a58cff",
    executing: "#ffb547", speaking: "#ffe29a", error: "#ff7a6b",
  };
  const CORES_DAS_FIGURAS = {
    sol: "#ffb547", nuvem: "#9fb8d6", chuva: "#6fb6ff", trovoada: "#c7b8ff",
    calendario: "#3fd6c6", relogio: "#a58cff", jornal: "#e8eef6", codigo: "#7fe0a8", mensagem: "#ffe29a",
  };
  const GIRO_DOS_ESTADOS = { idle: 0.25, listening: 0.4, thinking: 0.9, executing: 1.3, speaking: 0.4, error: 0.15 };

  /* ---------- figuras desenhadas numa tela invisível ---------- */

  const LADO = 360;
  const rascunho = document.createElement("canvas");
  rascunho.width = rascunho.height = LADO;
  const r = rascunho.getContext("2d", { willReadFrequently: true });

  function amostrar(desenhar, quantidade) {
    r.clearRect(0, 0, LADO, LADO);
    r.save();
    r.translate(LADO / 2, LADO / 2);
    r.scale(LADO / 2, LADO / 2);
    r.fillStyle = r.strokeStyle = "#fff";
    r.lineCap = "round";
    r.lineJoin = "round";
    desenhar(r);
    r.restore();
    const { data } = r.getImageData(0, 0, LADO, LADO);
    const cheios = [];
    for (let y = 0; y < LADO; y += 2) {
      for (let x = 0; x < LADO; x += 2) {
        if (data[(y * LADO + x) * 4 + 3] > 128) cheios.push([x / (LADO / 2) - 1, y / (LADO / 2) - 1]);
      }
    }
    return Array.from({ length: quantidade }, () => {
      const [x, y] = cheios[(Math.random() * cheios.length) | 0];
      return [x + (Math.random() - 0.5) * 0.012, y + (Math.random() - 0.5) * 0.012];
    });
  }

  function linha(c, pontos, largura) {
    c.lineWidth = largura;
    c.beginPath();
    pontos.forEach(([x, y], i) => (i ? c.lineTo(x, y) : c.moveTo(x, y)));
    c.stroke();
  }

  function nuvem(c, deslocamento = 0) {
    c.beginPath();
    for (const [x, y, raio] of [[-0.42, -0.12, 0.26], [-0.12, -0.3, 0.34], [0.24, -0.2, 0.3], [0.5, -0.06, 0.2]]) {
      c.moveTo(x + raio, y + deslocamento);
      c.arc(x, y + deslocamento, raio, 0, Math.PI * 2);
    }
    c.rect(-0.62, -0.1 + deslocamento, 1.28, 0.2);
    c.fill();
  }

  const DESENHOS = {
    sol(c) {
      c.beginPath(); c.arc(0, 0, 0.36, 0, Math.PI * 2); c.fill();
      for (let i = 0; i < 12; i++) {
        const a = (i / 12) * Math.PI * 2;
        linha(c, [[Math.cos(a) * 0.52, Math.sin(a) * 0.52], [Math.cos(a) * 0.82, Math.sin(a) * 0.82]], 0.07);
      }
    },
    nuvem(c) { nuvem(c, 0.12); },
    chuva(c) { nuvem(c); },
    trovoada(c) { nuvem(c); },
    calendario(c) {
      c.lineWidth = 0.05;
      c.beginPath(); c.roundRect(-0.7, -0.6, 1.4, 1.25, 0.12); c.stroke();
      c.beginPath(); c.roundRect(-0.7, -0.6, 1.4, 0.3, [0.12, 0.12, 0, 0]); c.fill();
      for (const x of [-0.38, 0.38]) linha(c, [[x, -0.78], [x, -0.52]], 0.06);
      for (let l = 0; l < 3; l++) {
        for (let k = 0; k < 5; k++) { c.beginPath(); c.roundRect(-0.56 + k * 0.24, -0.12 + l * 0.22, 0.14, 0.12, 0.03); c.fill(); }
      }
    },
    relogio(c) {
      c.lineWidth = 0.05;
      c.beginPath(); c.arc(0, 0, 0.78, 0, Math.PI * 2); c.stroke();
      for (let i = 0; i < 12; i++) {
        const a = (i / 12) * Math.PI * 2;
        const dentro = i % 3 === 0 ? 0.56 : 0.64;
        linha(c, [[Math.cos(a) * dentro, Math.sin(a) * dentro], [Math.cos(a) * 0.7, Math.sin(a) * 0.7]], 0.05);
      }
    },
    jornal(c) {
      c.lineWidth = 0.05;
      c.beginPath(); c.roundRect(-0.62, -0.72, 1.24, 1.44, 0.06); c.stroke();
      c.beginPath(); c.roundRect(-0.48, -0.58, 0.96, 0.2, 0.03); c.fill();
      c.beginPath(); c.roundRect(-0.48, -0.28, 0.42, 0.36, 0.03); c.fill();
      for (let i = 0; i < 4; i++) linha(c, [[0.04, -0.24 + i * 0.1], [0.48, -0.24 + i * 0.1]], 0.04);
      for (let i = 0; i < 4; i++) linha(c, [[-0.48, 0.2 + i * 0.12], [0.48, 0.2 + i * 0.12]], 0.04);
    },
    codigo(c) {
      linha(c, [[-0.38, -0.36], [-0.74, 0], [-0.38, 0.36]], 0.1);
      linha(c, [[0.38, -0.36], [0.74, 0], [0.38, 0.36]], 0.1);
      linha(c, [[0.14, -0.5], [-0.14, 0.5]], 0.1);
    },
    mensagem(c) {
      c.lineWidth = 0.06;
      c.beginPath(); c.roundRect(-0.72, -0.52, 1.44, 0.86, 0.2); c.stroke();
      linha(c, [[-0.34, 0.34], [-0.5, 0.64], [-0.1, 0.34]], 0.06);
      for (const x of [-0.3, 0, 0.3]) { c.beginPath(); c.arc(x, -0.09, 0.08, 0, Math.PI * 2); c.fill(); }
    },
  };

  const RAIO_DE_TROVOADA = [[0.08, 0.14], [-0.1, 0.46], [0.06, 0.46], [-0.08, 0.8]];

  /* ---------- figuras que se mexem: calculadas a cada quadro ---------- */

  const esferaBase = Array.from({ length: QUANTIDADE }, (_, i) => {
    const y = 1 - (i / (QUANTIDADE - 1)) * 2;
    const raio = Math.sqrt(1 - y * y);
    const t = Math.PI * (3 - Math.sqrt(5)) * i;
    return [Math.cos(t) * raio, y, Math.sin(t) * raio];
  });

  let nivel = () => 0;
  let estado = "idle";
  let figuraForcada = null;
  let figura = "esfera";
  let giro = 0;
  let corAtual = [127, 167, 217];
  let corAlvo = corAtual;
  let especiais = [];

  function alvoDaEsfera(i, som) {
    const [x, y, z] = esferaBase[i];
    const xr = x * Math.cos(giro) - z * Math.sin(giro);
    const zr = x * Math.sin(giro) + z * Math.cos(giro);
    const p = 1 / (1.9 - zr * 0.6);
    const raio = 0.62 * (1 + som * 0.25) * 1.4;
    return [xr * raio * p, (y * Math.cos(0.35) - zr * Math.sin(0.35)) * raio * p, zr];
  }

  function alvoDaOnda(i, tempo, som) {
    const x = (i / QUANTIDADE) * 2.4 - 1.2;
    const envelope = Math.cos((x / 1.2) * (Math.PI / 2));
    const faixa = ((i * 7919) % 100) / 100 - 0.5;
    const altura = 0.06 + som * 0.5;
    return [x, Math.sin(x * 6 + tempo / 160) * altura * envelope + faixa * 0.05, 0];
  }

  /* ---------- enxame ---------- */

  const drones = Array.from({ length: QUANTIDADE }, () => ({
    x: (Math.random() - 0.5) * 3, y: (Math.random() - 0.5) * 3, vx: 0, vy: 0,
    alvo: [0, 0], partida: 0, fase: Math.random() * Math.PI * 2, papel: null, queda: Math.random(), k: 0,
  }));

  function hexParaRgb(hex) {
    const n = parseInt(hex.slice(1), 16);
    return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
  }

  function formar(nova) {
    if (nova === figura) return;
    figura = nova;
    const agora = performance.now();
    drones.forEach((d) => { d.papel = null; d.partida = agora + Math.random() * (MOVIMENTO_REDUZIDO ? 0 : 450); });
    especiais = [];
    if (!DESENHOS[nova]) return;

    const fracaoEspecial = { chuva: 0.32, trovoada: 0.16, relogio: 0.28 }[nova] || 0;
    const quantosFixos = Math.round(QUANTIDADE * (1 - fracaoEspecial));
    especiais = drones.slice(quantosFixos);
    const papel = { chuva: "gota", trovoada: "raio", relogio: "ponteiro" }[nova];
    especiais.forEach((d, k) => { d.papel = papel; d.k = k; d.queda = Math.random(); });

    const pontos = amostrar(DESENHOS[nova], quantosFixos).sort((a, b) => Math.atan2(a[1], a[0]) - Math.atan2(b[1], b[0]));
    drones.slice(0, quantosFixos)
      .map((d) => ({ d, a: Math.atan2(d.y, d.x) }))
      .sort((p, q) => p.a - q.a)
      .forEach(({ d }, k) => { d.alvo = pontos[k]; });
  }

  function alvoEspecial(d, tempo) {
    if (d.papel === "gota") {
      d.queda = (d.queda + 0.012) % 1;
      const coluna = ((d.k * 2654435761) % 1000) / 1000;
      return [-0.5 + coluna, 0.18 + d.queda * 0.75];
    }
    if (d.papel === "raio") {
      const t = (d.k / especiais.length) * (RAIO_DE_TROVOADA.length - 1);
      const i = Math.min(Math.floor(t), RAIO_DE_TROVOADA.length - 2);
      const [a, b] = [RAIO_DE_TROVOADA[i], RAIO_DE_TROVOADA[i + 1]];
      const f = t - i;
      return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
    }
    const agora = new Date();
    const minuto = agora.getMinutes() + agora.getSeconds() / 60;
    const hora = (agora.getHours() % 12) + minuto / 60;
    const doMinuto = d.k % 3 !== 0;
    const angulo = (doMinuto ? minuto / 60 : hora / 12) * Math.PI * 2 - Math.PI / 2;
    const t = ((d.k * 7) % especiais.length) / especiais.length;
    return [Math.cos(angulo) * (doMinuto ? 0.62 : 0.4) * t, Math.sin(angulo) * (doMinuto ? 0.62 : 0.4) * t];
  }

  /* ---------- desenho ---------- */

  const brilhos = new Map();

  function brilho(cor) {
    const chave = cor.join(",");
    if (!brilhos.has(chave)) {
      const b = document.createElement("canvas");
      b.width = b.height = 32;
      const c = b.getContext("2d");
      const g = c.createRadialGradient(16, 16, 0, 16, 16, 16);
      g.addColorStop(0, "rgba(255,255,255,1)");
      g.addColorStop(0.18, `rgba(${chave},0.95)`);
      g.addColorStop(0.5, `rgba(${chave},0.22)`);
      g.addColorStop(1, `rgba(${chave},0)`);
      c.fillStyle = g;
      c.fillRect(0, 0, 32, 32);
      brilhos.set(chave, b);
      if (brilhos.size > 64) brilhos.delete(brilhos.keys().next().value);
    }
    return brilhos.get(chave);
  }

  let tela, pincel;

  function ajustarTamanho() {
    const escala = window.devicePixelRatio || 1;
    tela.width = Math.round(tela.clientWidth * escala);
    tela.height = Math.round(tela.clientHeight * escala);
  }

  function quadro(tempo) {
    const som = estado === "listening" || estado === "speaking" ? nivel() : 0;
    formar(figuraForcada || (estado === "speaking" ? "onda" : "esfera"));
    corAlvo = hexParaRgb(figuraForcada ? CORES_DAS_FIGURAS[figuraForcada] || "#e8eef6" : CORES_DOS_ESTADOS[estado] || "#7fa7d9");
    corAtual = corAtual.map((c, i) => c + (corAlvo[i] - c) * 0.05);
    const cor = corAtual.map(Math.round);
    const sprite = brilho(cor);
    giro += MOVIMENTO_REDUZIDO ? 0.0015 : 0.004 * (GIRO_DOS_ESTADOS[estado] ?? 0.3) * 2;

    const w = tela.width, h = tela.height;
    const escala = Math.min(w, h) * 0.36;
    const cx = w / 2, cy = h * 0.46;
    pincel.globalCompositeOperation = "destination-out";
    pincel.fillStyle = `rgba(0,0,0,${MOVIMENTO_REDUZIDO ? 1 : 0.32})`;
    pincel.fillRect(0, 0, w, h);
    pincel.globalCompositeOperation = "lighter";

    const pisca = estado === "thinking" || estado === "executing";
    const clarao = figura === "trovoada" ? 0.35 + 0.65 * Math.max(0, Math.sin(tempo / 90)) ** 8 : 1;
    const tamanho = Math.max(6, escala * 0.034);
    drones.forEach((d, i) => {
      let ax, ay, profundidade = 0;
      if (figura === "esfera") [ax, ay, profundidade] = alvoDaEsfera(i, MOVIMENTO_REDUZIDO ? 0 : som);
      else if (figura === "onda") [ax, ay] = alvoDaOnda(i, tempo, som);
      else if (d.papel) [ax, ay] = alvoEspecial(d, tempo);
      else if (figura === "sol") {
        const g = tempo * 0.00018;
        [ax, ay] = [d.alvo[0] * Math.cos(g) - d.alvo[1] * Math.sin(g), d.alvo[0] * Math.sin(g) + d.alvo[1] * Math.cos(g)];
      } else [ax, ay] = d.alvo;

      const pairar = MOVIMENTO_REDUZIDO ? 0 : 0.006;
      const tx = ax + Math.sin(tempo / 700 + d.fase) * pairar;
      const ty = ay + Math.cos(tempo / 900 + d.fase * 1.3) * pairar;
      if (tempo >= d.partida) {
        const rapido = d.papel === "gota";
        d.vx = (d.vx + (tx - d.x) * (rapido ? 0.3 : 0.022)) * (rapido ? 0.5 : 0.86);
        d.vy = (d.vy + (ty - d.y) * (rapido ? 0.3 : 0.022)) * (rapido ? 0.5 : 0.86);
        d.x += d.vx;
        d.y += d.vy;
      }
      const px = cx + d.x * escala, py = cy + d.y * escala;
      if (d.papel === "gota") {
        pincel.strokeStyle = `rgba(${cor.join(",")},0.55)`;
        pincel.lineWidth = Math.max(1, escala * 0.006);
        pincel.beginPath(); pincel.moveTo(px, py - escala * 0.05); pincel.lineTo(px, py); pincel.stroke();
        return;
      }
      const perto = figura === "esfera" ? 0.45 + (profundidade + 1) * 0.35 : 1;
      const brilhoDoPonto = pisca && figura === "esfera" ? 0.5 + 0.5 * Math.sin(tempo / 120 + d.fase) : 1;
      pincel.globalAlpha = (figura === "esfera" ? 0.35 + (profundidade + 1) * 0.3 : 0.9) * brilhoDoPonto * (d.papel === "raio" ? clarao : 1);
      const s = tamanho * perto;
      pincel.drawImage(sprite, px - s / 2, py - s / 2, s, s);
    });
    pincel.globalAlpha = 1;
    requestAnimationFrame(quadro);
  }

  return {
    iniciar(elemento) {
      tela = elemento;
      pincel = tela.getContext("2d");
      window.addEventListener("resize", ajustarTamanho);
      ajustarTamanho();
      requestAnimationFrame(quadro);
    },
    estado(novo) { estado = novo; },
    mostrar(nova) { figuraForcada = DESENHOS[nova] ? nova : null; },
    set nivel(funcao) { nivel = funcao; },
    get figura() { return figura; },
  };
})();
