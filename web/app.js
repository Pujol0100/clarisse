"use strict";

// Parada ou falando, embaixo do rosto não aparece o estado: falando, aparece a legenda.
const NOMES_DOS_ESTADOS = {
  idle: "",
  listening: "Ouvindo…",
  thinking: "Pensando…",
  executing: "Fazendo…",
  speaking: "",
  error: "Algo falhou",
};

const elementos = {
  corpo: document.body,
  estado: document.getElementById("estado"),
  conversa: document.getElementById("conversa"),
  conversaVazia: document.getElementById("conversa-vazia"),
  confirmacao: document.getElementById("confirmacao"),
  avisoSom: document.getElementById("aviso-som"),
  falar: document.getElementById("falar"),
  formulario: document.getElementById("formulario"),
  texto: document.getElementById("texto"),
};

/* ---------- estado ---------- */

let estadoAtual = "idle";
let legendaAtual = null;

function atualizarRotulo() {
  const texto = legendaAtual || NOMES_DOS_ESTADOS[estadoAtual] || "";
  elementos.estado.textContent = texto;
  elementos.estado.classList.toggle("legenda", Boolean(legendaAtual));
  elementos.estado.hidden = !texto;
}

function mudarEstado(estado) {
  estadoAtual = estado;
  elementos.corpo.dataset.estado = estado;
  atualizarRotulo();
  Enxame.estado(estado);
  Rosto.estado(estado);
}

function mostrarLegenda(texto) {
  legendaAtual = texto;
  atualizarRotulo();
}

/* ---------- conversa: histórico em balões, desde que a página abriu ---------- */

const LIMITE_DE_FALAS = 100;

function adicionarFala(quem, texto) {
  if (!texto) return;
  elementos.conversaVazia.hidden = true;
  const fala = document.createElement("p");
  fala.className = `fala fala-${quem}`;
  fala.textContent = texto;
  elementos.conversa.append(fala);
  const falas = elementos.conversa.querySelectorAll(".fala");
  for (let i = 0; i < falas.length - LIMITE_DE_FALAS; i++) falas[i].remove();
  elementos.conversa.scrollTop = elementos.conversa.scrollHeight;
}

function mostrarVoce(texto) {
  adicionarFala("voce", texto);
}

function mostrarClarisse(texto, aguardandoConfirmacao = false) {
  adicionarFala("clarisse", texto);
  elementos.confirmacao.hidden = !aguardandoConfirmacao;
}

/* ---------- som ---------- */

let contextoDeAudio = null;
let analisadorDoMicrofone = null;
let analisadorDaVoz = null;

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

/* Figura na tela: os drones saem do rosto e formam a figura no meio; o rosto vai para o canto. */
let figuraSemFala = null;

function mostrarFigura(figura) {
  clearTimeout(figuraSemFala);
  Enxame.mostrar(figura);
  Rosto.canto(Boolean(figura));
}

/* ---------- fala em trechos, com legenda ----------
   O servidor manda cada trecho assim que fica pronto. Eles tocam em fila, com o próximo já
   carregado; o texto da resposta só entra no chat quando a voz começa. */

let falaAtual = null;
const falasCanceladas = new Set();
const textosEsperandoAFala = new Map();

function esperarFala(fala, mostrar) {
  if (!fala || falasCanceladas.has(fala)) {
    mostrar();
    return;
  }
  textosEsperandoAFala.set(fala, mostrar);
  setTimeout(() => soltarTexto(fala), 20000);  // sem voz, o texto aparece mesmo assim
}

function soltarTexto(fala) {
  const mostrar = textosEsperandoAFala.get(fala);
  if (!mostrar) return;
  textosEsperandoAFala.delete(fala);
  mostrar();
}

function receberTrecho(e) {
  if (falasCanceladas.has(e.fala)) return;
  if (!falaAtual || falaAtual.id !== e.fala) {
    pararDeFalar(false);
    falaAtual = { id: e.fala, total: e.total, trechos: [], proximo: 0, tocando: null };
    mostrarFigura(e.figura);
    mudarEstado("speaking");
  }
  const audio = new Audio(e.audio);
  audio.preload = "auto";
  falaAtual.trechos[e.parte] = { audio, legenda: e.legenda };
  if (!falaAtual.tocando) tocarProximo();
}

async function tocarProximo() {
  const fala = falaAtual;
  const trecho = fala && fala.trechos[fala.proximo];
  if (!trecho) return;  // ainda não chegou: receberTrecho chama de novo
  fala.tocando = trecho.audio;
  if (contextoDeAudio) contextoDeAudio.createMediaElementSource(trecho.audio).connect(analisadorDaVoz);
  const parte = fala.proximo;
  trecho.audio.addEventListener("playing", () => {
    if (falaAtual !== fala) return;
    mostrarLegenda(trecho.legenda);
    if (parte === 0) soltarTexto(fala.id);
  }, { once: true });
  trecho.audio.addEventListener("ended", () => {
    if (falaAtual !== fala) return;
    fala.proximo += 1;
    fala.tocando = null;
    if (fala.proximo >= fala.total) terminarFala(fala);
    else tocarProximo();
  });
  try {
    await trecho.audio.play();
  } catch {
    elementos.avisoSom.hidden = false;
    soltarTexto(fala.id);
    terminarFala(fala);
  }
}

function terminarFala(fala) {
  if (falaAtual !== fala) return;
  falaAtual = null;
  mostrarLegenda(null);
  mostrarFigura(null);
  mudarEstado("idle");
  fetch("/api/fim-da-fala", { method: "POST" });
}

function pararDeFalar(avisarServidor = true) {
  if (!falaAtual) return;
  const fala = falaAtual;
  falaAtual = null;
  falasCanceladas.add(fala.id);
  soltarTexto(fala.id);
  if (fala.tocando) fala.tocando.pause();
  mostrarLegenda(null);
  mostrarFigura(null);
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
  mudarEstado("thinking");
  return chamar("/api/mensagem", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ texto }),
  });
}

const tratadores = {
  estado: (e) => {
    const ocupadaAqui = falaAtual || (gravador && gravador.state === "recording");
    if (!(ocupadaAqui && e.estado === "idle")) mudarEstado(e.estado);
  },
  // A frase entendida volta como fala_do_usuario; aqui só entra quando não se entendeu nada.
  transcricao: (e) => { if (!e.texto) adicionarFala("aviso", "Não entendi o que foi dito. Tente de novo."); },
  fala_do_usuario: (e) => mostrarVoce(e.texto),
  resposta: (e) => esperarFala(e.fala, () => mostrarClarisse(e.texto, e.aguardando_confirmacao)),
  aviso: (e) => esperarFala(e.fala, () => mostrarClarisse(`Do ${e.titulo}: ${e.texto}`)),
  falar: receberTrecho,
  figura: (e) => {
    // Figura mandada pelo Claude das etapas, sem fala junto: fica alguns segundos e sai.
    mostrarFigura(e.figura);
    figuraSemFala = setTimeout(() => { if (!falaAtual) mostrarFigura(null); }, 8000);
  },
  parar: () => pararDeFalar(),
  escutar: () => alternarMicrofone(),
  erro: (e) => {
    // Voz falhou no meio: o texto que esperava aparece, e a fala termina onde parou.
    if (e.fala) {
      soltarTexto(e.fala);
      if (falaAtual && falaAtual.id === e.fala) falaAtual.total = falaAtual.trechos.length;
    }
    mostrarClarisse(e.texto);
  },
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

/* ---------- rosto e enxame ---------- */

function moverABoca() {
  Rosto.abertura(estadoAtual === "speaking" ? nivelDoSom() : 0);
  requestAnimationFrame(moverABoca);
}

Rosto.iniciar(document.getElementById("rosto"));
Enxame.nivel = nivelDoSom;
Enxame.origem = () => Rosto.centro();
Enxame.iniciar(document.getElementById("enxame"));
requestAnimationFrame(moverABoca);
mudarEstado("idle");
conectar();
