"use strict";

const NOMES_DOS_ESTADOS = {
  idle: "Pronta",
  listening: "Ouvindo",
  thinking: "Pensando",
  executing: "Fazendo",
  speaking: "Falando",
  error: "Algo falhou",
};
const ENERGIA_DOS_ESTADOS = { idle: 0.12, listening: 0.35, thinking: 0.7, executing: 1, speaking: 0.35, error: 0.2 };
const MOVIMENTO_REDUZIDO = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const elementos = {
  corpo: document.body,
  estado: document.getElementById("estado"),
  voce: document.getElementById("voce"),
  clarisse: document.getElementById("clarisse"),
  confirmacao: document.getElementById("confirmacao"),
  avisoSom: document.getElementById("aviso-som"),
  falar: document.getElementById("falar"),
  formulario: document.getElementById("formulario"),
  texto: document.getElementById("texto"),
};

/* ---------- estado ---------- */

let estadoAtual = "idle";

function mudarEstado(estado) {
  estadoAtual = estado;
  elementos.corpo.dataset.estado = estado;
  elementos.estado.textContent = NOMES_DOS_ESTADOS[estado] || estado;
}

function mostrarVoce(texto) {
  elementos.voce.textContent = texto;
  elementos.voce.hidden = !texto;
}

function mostrarClarisse(texto, aguardandoConfirmacao = false) {
  elementos.clarisse.textContent = texto;
  elementos.clarisse.hidden = !texto;
  elementos.confirmacao.hidden = !aguardandoConfirmacao;
}

/* ---------- som ---------- */

let contextoDeAudio = null;
let analisadorDoMicrofone = null;
let analisadorDaVoz = null;
let audioTocando = null;

function liberarSom() {
  if (!contextoDeAudio) {
    contextoDeAudio = new AudioContext();
    analisadorDoMicrofone = contextoDeAudio.createAnalyser();
    analisadorDoMicrofone.fftSize = 512;
    analisadorDaVoz = contextoDeAudio.createAnalyser();
    analisadorDaVoz.fftSize = 512;
    analisadorDaVoz.connect(contextoDeAudio.destination);
  }
  if (contextoDeAudio.state === "suspended") contextoDeAudio.resume();
  elementos.avisoSom.hidden = true;
}

document.addEventListener("pointerdown", liberarSom);

function nivelDoSom() {
  const analisador = estadoAtual === "listening" ? analisadorDoMicrofone : analisadorDaVoz;
  if (!analisador) return 0;
  const amostras = new Uint8Array(analisador.fftSize);
  analisador.getByteTimeDomainData(amostras);
  let soma = 0;
  for (const a of amostras) {
    const v = (a - 128) / 128;
    soma += v * v;
  }
  return Math.min(1, Math.sqrt(soma / amostras.length) * 4);
}

async function tocar(url) {
  pararDeFalar(false);
  const audio = new Audio(url);
  audioTocando = audio;
  if (contextoDeAudio) {
    contextoDeAudio.createMediaElementSource(audio).connect(analisadorDaVoz);
  }
  audio.addEventListener("ended", () => terminarFala(audio));
  mudarEstado("speaking");
  try {
    await audio.play();
  } catch {
    elementos.avisoSom.hidden = false;
    terminarFala(audio);
  }
}

function terminarFala(audio) {
  if (audioTocando !== audio) return;
  audioTocando = null;
  mudarEstado("idle");
  fetch("/api/fim-da-fala", { method: "POST" });
}

function pararDeFalar(avisarServidor = true) {
  if (!audioTocando) return;
  const audio = audioTocando;
  audioTocando = null;
  audio.pause();
  if (avisarServidor) {
    mudarEstado("idle");
    fetch("/api/fim-da-fala", { method: "POST" });
  }
}

/* ---------- microfone ---------- */

let gravador = null;
let pedacos = [];
let fonteDoMicrofone = null;

async function alternarMicrofone() {
  liberarSom();
  if (gravador && gravador.state === "recording") {
    gravador.stop();
    return;
  }
  pararDeFalar();
  let fluxo;
  try {
    fluxo = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
  } catch {
    mudarEstado("error");
    mostrarClarisse("Não tenho acesso ao microfone. Libere o microfone para esta página nas permissões do navegador.");
    return;
  }
  fonteDoMicrofone = contextoDeAudio.createMediaStreamSource(fluxo);
  fonteDoMicrofone.connect(analisadorDoMicrofone);
  pedacos = [];
  gravador = new MediaRecorder(fluxo, { mimeType: "audio/webm;codecs=opus" });
  gravador.addEventListener("dataavailable", (e) => pedacos.push(e.data));
  gravador.addEventListener("stop", () => enviarGravacao(fluxo));
  gravador.start();
  elementos.falar.setAttribute("aria-pressed", "true");
  elementos.falar.querySelector(".botao-falar-rotulo").textContent = "Enviar";
  mudarEstado("listening");
}

async function enviarGravacao(fluxo) {
  fluxo.getTracks().forEach((trilha) => trilha.stop());
  if (fonteDoMicrofone) fonteDoMicrofone.disconnect();
  fonteDoMicrofone = null;
  elementos.falar.setAttribute("aria-pressed", "false");
  elementos.falar.querySelector(".botao-falar-rotulo").textContent = "Falar";
  mudarEstado("thinking");
  const audio = new Blob(pedacos, { type: "audio/webm" });
  await chamar("/api/voz", { method: "POST", headers: { "Content-Type": "audio/webm" }, body: audio });
}

/* ---------- servidor ---------- */

async function chamar(caminho, opcoes) {
  try {
    const resposta = await fetch(caminho, opcoes);
    if (!resposta.ok) throw new Error(String(resposta.status));
    return await resposta.json();
  } catch {
    mudarEstado("error");
    mostrarClarisse("Não consegui falar com o servidor da Clarisse. Confira se ele está ligado e recarregue a página.");
    return null;
  }
}

function enviarTexto(texto) {
  mostrarVoce(texto);
  mudarEstado("thinking");
  return chamar("/api/mensagem", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ texto }),
  });
}

const tratadores = {
  estado: (e) => {
    const ocupadaAqui = audioTocando || (gravador && gravador.state === "recording");
    if (!(ocupadaAqui && e.estado === "idle")) mudarEstado(e.estado);
  },
  transcricao: (e) => mostrarVoce(e.texto || "(não entendi nada)"),
  fala_do_usuario: (e) => mostrarVoce(e.texto),
  resposta: (e) => mostrarClarisse(e.texto, e.aguardando_confirmacao),
  aviso: (e) => mostrarClarisse(`Do ${e.titulo}: ${e.texto}`),
  falar: (e) => tocar(e.audio),
  parar: () => pararDeFalar(),
  escutar: () => alternarMicrofone(),
  erro: (e) => mostrarClarisse(e.texto),
};

let espera = 500;

function conectar() {
  const canal = new WebSocket(`ws://${location.host}/ws`);
  canal.addEventListener("open", () => { espera = 500; });
  canal.addEventListener("message", (m) => {
    const evento = JSON.parse(m.data);
    const tratar = tratadores[evento.tipo];
    if (tratar) tratar(evento);
  });
  canal.addEventListener("close", async () => {
    try {
      const resposta = await fetch("/api/estado");
      if (resposta.status === 401) {
        location.reload();
        return;
      }
    } catch {
      /* servidor desligado: tenta de novo mais tarde */
    }
    setTimeout(conectar, espera);
    espera = Math.min(espera * 2, 8000);
  });
}

/* ---------- controles ---------- */

elementos.falar.addEventListener("click", alternarMicrofone);
elementos.formulario.addEventListener("submit", (e) => {
  e.preventDefault();
  const texto = elementos.texto.value.trim();
  if (!texto) return;
  elementos.texto.value = "";
  liberarSom();
  enviarTexto(texto);
});
document.getElementById("confirmar").addEventListener("click", () => enviarTexto("sim"));
document.getElementById("cancelar").addEventListener("click", () => enviarTexto("não"));
document.addEventListener("keydown", (e) => {
  if (e.code !== "Space" || e.repeat || e.target instanceof HTMLInputElement || e.target instanceof HTMLButtonElement) return;
  e.preventDefault();
  alternarMicrofone();
});

/* ---------- bola neural ---------- */

const tela = document.getElementById("bola");
const pincel = tela.getContext("2d");
const NOS = criarEsfera(MOVIMENTO_REDUZIDO ? 120 : 190);
const LIGACOES = ligarVizinhos(NOS, 0.36);
let giro = 0;
let energia = ENERGIA_DOS_ESTADOS.idle;
let corAtual = [127, 167, 217];

function criarEsfera(quantidade) {
  const pontos = [];
  const aureo = Math.PI * (3 - Math.sqrt(5));
  for (let i = 0; i < quantidade; i++) {
    const y = 1 - (i / (quantidade - 1)) * 2;
    const r = Math.sqrt(1 - y * y);
    const t = aureo * i;
    pontos.push({ x: Math.cos(t) * r, y, z: Math.sin(t) * r, fase: Math.random() * Math.PI * 2 });
  }
  return pontos;
}

function ligarVizinhos(pontos, distancia) {
  const pares = [];
  for (let i = 0; i < pontos.length; i++) {
    for (let j = i + 1; j < pontos.length; j++) {
      const a = pontos[i], b = pontos[j];
      if (Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z) < distancia) pares.push([i, j]);
    }
  }
  return pares;
}

function corDoEstado() {
  const hex = getComputedStyle(elementos.corpo).getPropertyValue("--cor-do-estado").trim();
  const n = parseInt(hex.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function ajustarTamanho() {
  const escala = window.devicePixelRatio || 1;
  const { width, height } = tela.getBoundingClientRect();
  tela.width = Math.round(width * escala);
  tela.height = Math.round(height * escala);
}

function desenhar(instante) {
  const som = estadoAtual === "listening" || estadoAtual === "speaking" ? nivelDoSom() : 0;
  const alvo = (ENERGIA_DOS_ESTADOS[estadoAtual] ?? 0.2) + (MOVIMENTO_REDUZIDO ? 0 : som * 0.8);
  energia += (alvo - energia) * 0.08;
  const destino = corDoEstado();
  corAtual = corAtual.map((c, i) => c + (destino[i] - c) * 0.06);
  const [vermelho, verde, azul] = corAtual.map(Math.round);

  giro += MOVIMENTO_REDUZIDO ? 0.0015 : 0.002 + energia * 0.012;
  const respiracao = MOVIMENTO_REDUZIDO ? 0 : Math.sin(instante / 1400) * 0.02;
  const w = tela.width, h = tela.height;
  const raio = Math.min(w, h) * 0.34 * (1 + respiracao + som * 0.18);
  const cx = w / 2, cy = h / 2;
  const cosG = Math.cos(giro), senG = Math.sin(giro);
  const inclinacao = 0.35, cosI = Math.cos(inclinacao), senI = Math.sin(inclinacao);

  const projetados = NOS.map((p) => {
    const x = p.x * cosG - p.z * senG;
    const z0 = p.x * senG + p.z * cosG;
    const y = p.y * cosI - z0 * senI;
    const z = p.y * senI + z0 * cosI;
    const perspectiva = 1 / (1.9 - z * 0.6);
    return { x: cx + x * raio * perspectiva * 1.4, y: cy + y * raio * perspectiva * 1.4, z, fase: p.fase };
  });

  pincel.clearRect(0, 0, w, h);
  const brilho = pincel.createRadialGradient(cx, cy, 0, cx, cy, raio * 1.6);
  brilho.addColorStop(0, `rgba(${vermelho},${verde},${azul},${0.10 + energia * 0.12})`);
  brilho.addColorStop(1, "rgba(0,0,0,0)");
  pincel.fillStyle = brilho;
  pincel.fillRect(0, 0, w, h);

  pincel.lineWidth = Math.max(1, w / 900);
  for (const [i, j] of LIGACOES) {
    const a = projetados[i], b = projetados[j];
    const profundidade = (a.z + b.z + 2) / 4;
    pincel.strokeStyle = `rgba(${vermelho},${verde},${azul},${0.05 + profundidade * 0.28})`;
    pincel.beginPath();
    pincel.moveTo(a.x, a.y);
    pincel.lineTo(b.x, b.y);
    pincel.stroke();
  }

  for (const p of projetados) {
    const profundidade = (p.z + 1) / 2;
    const pisca = estadoAtual === "thinking" || estadoAtual === "executing"
      ? 0.5 + 0.5 * Math.sin(instante / (160 - energia * 80) + p.fase)
      : 1;
    const tamanho = (1.2 + profundidade * 2.4) * (w / 700) * (0.8 + pisca * 0.4);
    pincel.fillStyle = `rgba(${vermelho},${verde},${azul},${0.25 + profundidade * 0.75 * pisca})`;
    pincel.beginPath();
    pincel.arc(p.x, p.y, tamanho, 0, Math.PI * 2);
    pincel.fill();
  }

  requestAnimationFrame(desenhar);
}

window.addEventListener("resize", ajustarTamanho);
ajustarTamanho();
requestAnimationFrame(desenhar);
mudarEstado("idle");
conectar();
