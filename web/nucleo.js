"use strict";

/* O núcleo da Clarisse: anel dourado com a bússola da Smart Compass no centro, filamentos de energia
   que se agitam com a voz, régua de HUD e, em volta, a constelação de ferramentas. Um nó acende
   enquanto a ferramenta dele trabalha. A bússola respira parada, gira enquanto a Clarisse pensa ou
   executa e, ao terminar, assenta apontando para cima de novo, com o balanço de um ponteiro.
   Quando o chat abre à direita, o núcleo desliza para o espaço que sobra. */

const Nucleo = (() => {
  const MOVIMENTO_REDUZIDO = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const DOURADO = [201, 168, 76];
  const OURO_CLARO = [229, 200, 117];
  const BRANCO = [255, 255, 255];
  const LARGURA_DO_CHAT = 400;
  const rgba = ([r, g, b], a) => `rgba(${r},${g},${b},${a})`;

  const ALVOS = {
    idle: { agitacao: 0.05, giro: 0.12, brilho: 0.55 },
    listening: { agitacao: 0.08, giro: 0.2, brilho: 0.85 },
    thinking: { agitacao: 0.035, giro: 0.9, brilho: 0.75 },
    executing: { agitacao: 0.04, giro: 1.2, brilho: 0.8 },
    speaking: { agitacao: 0.07, giro: 0.25, brilho: 1.0 },
    error: { agitacao: 0.02, giro: 0.05, brilho: 0.35 },
  };

  let c = null;
  let largura = 0, altura = 0, cx = 0, cy = 0, raio = 0;
  let estadoAtual = "idle";
  let agitacao = 0.05, brilho = 0.55, giro = 0, chat = 0;
  let nos = [];

  // O logo tem simetria de quarto de volta: assentar em qualquer múltiplo de 90° é apontar para cima.
  const QUARTO = Math.PI / 2;
  const GIRO_DA_BUSSOLA = 2.2;
  let rumo = 0, rumoVel = 0, pouso = 0;
  let logoDourado = null;
  const logo = new Image();
  logo.onload = () => {
    const o = document.createElement("canvas");
    o.width = logo.naturalWidth;
    o.height = logo.naturalHeight;
    const oc = o.getContext("2d");
    oc.drawImage(logo, 0, 0);
    oc.globalCompositeOperation = "source-in";
    oc.fillStyle = rgba(OURO_CLARO, 1);
    oc.fillRect(0, 0, o.width, o.height);
    logoDourado = o;
  };
  logo.src = "/static/logo-smart.png";

  const filamentos = Array.from({ length: 9 }, (_, i) => ({
    f1: 2 + (i % 3), f2: 4 + ((i * 2) % 5), f3: 7 + (i % 2),
    p1: Math.random() * 6.28, p2: Math.random() * 6.28, p3: Math.random() * 6.28,
    v1: 0.3 + Math.random() * 0.5, v2: -0.2 - Math.random() * 0.6, v3: 0.5 + Math.random() * 0.4,
    escala: 0.92 + i * 0.022,
  }));
  const poeira = Array.from({ length: 140 }, () => ({
    a: Math.random() * 6.28, r: 0.8 + Math.random() * 0.9, v: 0.02 + Math.random() * 0.08, s: Math.random() * 1.3 + 0.3,
  }));

  /* ---------- medidas ---------- */

  function medir() {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    largura = innerWidth;
    altura = innerHeight;
    c.canvas.width = largura * dpr;
    c.canvas.height = altura * dpr;
    c.setTransform(dpr, 0, 0, dpr, 0, 0);
    posicionar();
  }

  function posicionar() {
    const livre = largura - chat;
    cx = livre / 2;
    cy = altura * 0.46;
    raio = Math.min(livre * 0.5, altura * 0.9) * 0.27;
    // Metade dos nós à direita (de -50° a 50°), metade à esquerda (de 130° a 230°).
    const direita = Math.ceil(nos.length / 2);
    nos.forEach((no, i) => {
      const lado = i < direita ? 0 : 1;
      const quantos = lado === 0 ? direita : nos.length - direita;
      const k = lado === 0 ? i : i - direita;
      const passo = quantos > 1 ? 100 / (quantos - 1) : 0;
      const graus = lado === 0 ? -50 + k * passo : 230 - k * passo;
      const a = (graus * Math.PI) / 180;
      no.x = cx + Math.cos(a) * raio * 2.35;
      no.y = cy + Math.sin(a) * raio * 1.35;
    });
  }

  /* ---------- desenho ---------- */

  function desenharPoeira() {
    for (const p of poeira) {
      const a = p.a + giro * p.v * 3;
      c.fillStyle = rgba(DOURADO, 0.25 * brilho);
      c.fillRect(cx + Math.cos(a) * raio * p.r * 1.25, cy + Math.sin(a) * raio * p.r * 0.95, p.s, p.s);
    }
  }

  function desenharConstelacao(t, dt) {
    c.font = '500 12px "IBM Plex Mono", "DejaVu Sans Mono", ui-monospace, monospace';
    c.textBaseline = "middle";
    for (const no of nos) {
      no.brilho += ((no.ativo ? 1 : 0) - no.brilho) * Math.min(1, dt * 5);
      const dx = no.x - cx, dy = no.y - cy, d = Math.hypot(dx, dy) || 1;
      const bx = cx + (dx / d) * raio * 1.05, by = cy + (dy / d) * raio * 1.05;
      const mx = (no.x + bx) / 2 + dy * 0.12, my = (no.y + by) / 2 - dx * 0.12;

      c.strokeStyle = rgba(DOURADO, 0.14 + no.brilho * 0.6);
      c.lineWidth = 1 + no.brilho;
      c.beginPath();
      c.moveTo(no.x, no.y);
      c.quadraticCurveTo(mx, my, bx, by);
      c.stroke();

      if (no.brilho > 0.05) {
        // pulsos de luz correndo do nó até o núcleo
        for (let p = 0; p < 3; p++) {
          const u = (t * 0.9 + p / 3) % 1;
          const x = (1 - u) ** 2 * no.x + 2 * (1 - u) * u * mx + u * u * bx;
          const y = (1 - u) ** 2 * no.y + 2 * (1 - u) * u * my + u * u * by;
          c.fillStyle = rgba(OURO_CLARO, no.brilho);
          c.shadowColor = rgba(OURO_CLARO, 1);
          c.shadowBlur = 12;
          c.beginPath();
          c.arc(x, y, 2.4, 0, Math.PI * 2);
          c.fill();
          c.shadowBlur = 0;
        }
      }

      c.fillStyle = "#0a0a0a";
      c.strokeStyle = rgba(no.brilho > 0.1 ? OURO_CLARO : DOURADO, 0.5 + no.brilho * 0.5);
      c.lineWidth = 1.2;
      c.shadowColor = rgba(OURO_CLARO, no.brilho);
      c.shadowBlur = 18 * no.brilho;
      c.beginPath();
      c.arc(no.x, no.y, 6 + no.brilho * 2, 0, Math.PI * 2);
      c.fill();
      c.stroke();
      c.shadowBlur = 0;
      c.fillStyle = rgba(OURO_CLARO, 0.35 + no.brilho * 0.65);
      c.beginPath();
      c.arc(no.x, no.y, 2.2, 0, Math.PI * 2);
      c.fill();

      const esquerda = no.x < cx;
      c.textAlign = esquerda ? "right" : "left";
      c.fillStyle = no.brilho > 0.1 ? rgba(BRANCO, 0.6 + no.brilho * 0.4) : "rgba(163,163,170,0.8)";
      c.fillText(no.rotulo.toUpperCase(), no.x + (esquerda ? -16 : 16), no.y);
    }
  }

  function desenharBussola(t, nivel) {
    if (!logoDourado) return;
    const lado = raio * 1.12;
    const respiro = 0.88 + 0.12 * Math.sin(t * 1.3);
    c.save();
    c.translate(cx, cy);
    c.rotate(rumo);
    c.globalAlpha = Math.min(1, (0.45 + 0.55 * brilho) * respiro + nivel * 0.3);
    c.shadowColor = rgba(OURO_CLARO, 0.8);
    c.shadowBlur = 10 + 8 * respiro + nivel * 36;
    c.drawImage(logoDourado, -lado / 2, -lado / 2, lado, lado);
    c.restore();
  }

  function desenharAnel(nivel) {
    const g = c.createRadialGradient(cx, cy, raio * 0.2, cx, cy, raio * 0.75);
    g.addColorStop(0, rgba(DOURADO, 0.1 * brilho));
    g.addColorStop(1, "rgba(0,0,0,0)");
    c.fillStyle = g;
    c.beginPath();
    c.arc(cx, cy, raio * 0.75, 0, Math.PI * 2);
    c.fill();

    c.shadowColor = rgba(OURO_CLARO, 1);
    c.shadowBlur = 22 + nivel * 30;
    c.strokeStyle = rgba(OURO_CLARO, 0.9 * brilho);
    c.lineWidth = 2.6 + nivel * 2;
    c.beginPath();
    c.arc(cx, cy, raio * 0.66, 0, Math.PI * 2);
    c.stroke();
    c.shadowBlur = 0;

    c.strokeStyle = rgba(DOURADO, 0.45 * brilho);
    c.lineWidth = 1;
    for (let k = 0; k < 120; k++) {
      const a = (k / 120) * Math.PI * 2 - giro * 0.6;
      const r0 = raio * 0.72, r1 = raio * (k % 10 === 0 ? 0.77 : 0.745);
      c.beginPath();
      c.moveTo(cx + Math.cos(a) * r0, cy + Math.sin(a) * r0);
      c.lineTo(cx + Math.cos(a) * r1, cy + Math.sin(a) * r1);
      c.stroke();
    }
    c.setLineDash([raio * 0.18, raio * 0.08]);
    c.strokeStyle = rgba(DOURADO, 0.3 * brilho);
    c.beginPath();
    c.arc(cx, cy, raio * 1.24, giro * 0.8, giro * 0.8 + Math.PI * 1.3);
    c.stroke();
    c.beginPath();
    c.arc(cx, cy, raio * 1.32, -giro * 0.5, -giro * 0.5 + Math.PI * 0.8);
    c.stroke();
    c.setLineDash([]);
  }

  function desenharFilamentos(t, nivel) {
    c.globalCompositeOperation = "lighter";
    const amplitude = agitacao + nivel * 0.12;
    filamentos.forEach((f, i) => {
      c.beginPath();
      for (let k = 0; k <= 200; k++) {
        const th = (k / 200) * Math.PI * 2;
        const onda = Math.sin(f.f1 * th + t * f.v1 + f.p1) * 0.55
          + Math.sin(f.f2 * th + t * f.v2 + f.p2) * 0.3
          + Math.sin(f.f3 * th + t * f.v3 + f.p3) * 0.15 * (0.4 + nivel);
        const r = raio * f.escala * (1 + amplitude * onda);
        const x = cx + Math.cos(th + giro * 0.15) * r, y = cy + Math.sin(th + giro * 0.15) * r;
        if (k) c.lineTo(x, y);
        else c.moveTo(x, y);
      }
      c.strokeStyle = rgba(i % 4 === 0 ? BRANCO : DOURADO, (0.16 + 0.1 * (i % 3)) * brilho);
      c.lineWidth = 1.1;
      c.shadowColor = rgba(DOURADO, 0.9);
      c.shadowBlur = 10;
      c.stroke();
    });
    c.shadowBlur = 0;
    c.globalCompositeOperation = "source-over";
  }

  /* ---------- laço ---------- */

  let antes = performance.now();

  function moverBussola(dt) {
    if (MOVIMENTO_REDUZIDO) return;
    if (estadoAtual === "thinking" || estadoAtual === "executing") {
      rumoVel += (GIRO_DA_BUSSOLA - rumoVel) * Math.min(1, dt * 2);
      // Assenta no próximo quarto à frente, contando o embalo, para nunca voltar para trás.
      pouso = Math.ceil((rumo + rumoVel * 0.5) / QUARTO) * QUARTO;
    } else {
      // Mola pouco amortecida: passa um pouco do ponto e volta, como ponteiro de bússola.
      rumoVel += (-(rumo - pouso) * 18 - rumoVel * 4.5) * dt;
    }
    rumo += rumoVel * dt;
  }

  function quadro(agora) {
    const dt = Math.min(0.05, (agora - antes) / 1000);
    antes = agora;
    const t = MOVIMENTO_REDUZIDO ? agora / 4000 : agora / 1000;
    const alvo = ALVOS[estadoAtual] || ALVOS.idle;
    agitacao += (alvo.agitacao - agitacao) * dt * 3;
    brilho += (alvo.brilho - brilho) * dt * 3;
    giro += alvo.giro * dt * (MOVIMENTO_REDUZIDO ? 0.25 : 1);
    const nivel = MOVIMENTO_REDUZIDO ? 0 : api.nivel();
    moverBussola(dt);

    const chatAlvo = document.body.classList.contains("com-chat") ? Math.min(LARGURA_DO_CHAT, largura * 0.4) : 0;
    if (Math.abs(chatAlvo - chat) > 0.5) {
      chat += (chatAlvo - chat) * Math.min(1, dt * 7);
      posicionar();
    }

    c.clearRect(0, 0, largura, altura);
    desenharPoeira();
    desenharConstelacao(agora / 1000, dt);
    desenharBussola(t, nivel);
    desenharAnel(nivel);
    desenharFilamentos(t, nivel);
    requestAnimationFrame(quadro);
  }

  /* ---------- interface ---------- */

  const api = {
    nivel: () => 0,
    iniciar(canvas) {
      c = canvas.getContext("2d");
      addEventListener("resize", medir);
      medir();
      requestAnimationFrame(quadro);
    },
    estado(nome) {
      estadoAtual = nome;
    },
    /** Lista de {grupo, rotulo}: os nós da constelação, na ordem em que aparecem. */
    grupos(lista) {
      const antigos = new Map(nos.map((no) => [no.grupo, no]));
      nos = lista.map(({ grupo, rotulo }) => ({ ...(antigos.get(grupo) || { brilho: 0, ativo: false }), grupo, rotulo }));
      if (c) posicionar();
    },
    acender(grupo, ligado) {
      const no = nos.find((n) => n.grupo === grupo);
      if (no) no.ativo = ligado;
    },
  };
  return api;
})();
