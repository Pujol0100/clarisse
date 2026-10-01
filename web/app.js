"use strict";

// Parada ou falando, o topo não mostra estado: falando, o que ela diz aparece na legenda.
const NOMES_DOS_ESTADOS = {
  idle: "",
  listening: "Ouvindo",
  thinking: "Pensando",
  executing: "Consultando",
  speaking: "Falando",
  error: "Algo falhou",
};

// Nós da constelação. Cada evento de ferramenta diz o grupo que acende.
const GRUPOS = [
  { grupo: "clima", rotulo: "Clima" },
  { grupo: "agenda", rotulo: "Agenda" },
  { grupo: "email", rotulo: "E-mail" },
  { grupo: "noticias", rotulo: "Notícias" },
  { grupo: "github", rotulo: "GitHub" },
  { grupo: "notas", rotulo: "Notas" },
  { grupo: "servidores", rotulo: "Servidores" },
  { grupo: "lembretes", rotulo: "Lembretes" },
  { grupo: "navegador", rotulo: "Navegador" },
  { grupo: "claude", rotulo: "Claude" },
  { grupo: "codigo", rotulo: "Código" },
  { grupo: "janelas", rotulo: "Janelas" },
  { grupo: "sistema", rotulo: "Sistema" },
];

const elementos = {
  corpo: document.body,
  estado: document.getElementById("estado"),
  voce: document.getElementById("voce"),
  legenda: document.getElementById("legenda"),
  hora: document.getElementById("hora"),
  conversa: document.getElementById("conversa"),
  conversaVazia: document.getElementById("conversa-vazia"),
  confirmacao: document.getElementById("confirmacao"),
  avisoSom: document.getElementById("aviso-som"),
  falar: document.getElementById("falar"),
  falarRotulo: document.getElementById("falar-rotulo"),
  escrever: document.getElementById("escrever"),
  fecharChat: document.getElementById("fechar-chat"),
  formulario: document.getElementById("formulario"),
  texto: document.getElementById("texto"),
};

/* ---------- estado ---------- */

let estadoAtual = "idle";

function mudarEstado(estado) {
  estadoAtual = estado;
  elementos.corpo.dataset.estado = estado;
  elementos.estado.textContent = NOMES_DOS_ESTADOS[estado] || "";
  Nucleo.estado(estado);
}

function mostrarLegenda(texto) {
  if (texto) elementos.legenda.textContent = texto;
  elementos.legenda.classList.toggle("visivel", Boolean(texto));
}

/* ---------- conversa: o que se disse aparece no topo e fica no chat ---------- */

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
  elementos.voce.textContent = texto;
  elementos.voce.classList.add("visivel");
}

function esconderVoce() {
  elementos.voce.classList.remove("visivel");
}

function mostrarClarisse(texto, aguardandoConfirmacao = false) {
  adicionarFala("clarisse", texto);
  elementos.confirmacao.hidden = !aguardandoConfirmacao;
}

/* ---------- escrita opcional ---------- */

function abrirChat(aberto) {
  elementos.corpo.classList.toggle("com-chat", aberto);
  elementos.escrever.setAttribute("aria-expanded", String(aberto));
  if (aberto) setTimeout(() => elementos.texto.focus(), 300);
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
  const analisador = estadoAtual === "listening" ? analisadorDoMicrofone : estadoAtual === "speaking" ? analisadorDaVoz : null;
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

/* ---------- fala em trechos, com legenda ----------
   O servidor manda cada trecho assim que fica pronto. Eles tocam em fila, com o próximo já
   carregado; o texto e o cartão da resposta só aparecem quando a voz começa. */

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
    mudarEstado("speaking");
  }
  const audio = new Audio(e.audio);
  audio.preload = "auto";
  audio.muted = !tenhoAVoz;
  falaAtual.trechos[e.parte] = { audio, legenda: e.legenda, paragrafo: e.paragrafo };
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
    if (parte === 0) soltarTexto(fala.id);
    // Lendo uma matéria, o próprio bloco mostra o texto: acende o parágrafo em vez da legenda.
    if (Cartoes.lendo()) {
      mostrarLegenda(null);
      if (trecho.paragrafo != null) Cartoes.marcarParagrafo(trecho.paragrafo);
    } else {
      mostrarLegenda(trecho.legenda);
    }
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

function encerrarCena() {
  mostrarLegenda(null);
  esconderVoce();
  Cartoes.encerrar();
}

function terminarFala(fala) {
  if (falaAtual !== fala) return;
  falaAtual = null;
  encerrarCena();
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
  encerrarCena();
  if (avisarServidor) {
    mudarEstado("idle");
    fetch("/api/fim-da-fala", { method: "POST" });
  }
}

/* ---------- microfone: aperta para gravar, aperta de novo para enviar ---------- */

let gravador = null;
let pedacos = [];
let fonteDoMicrofone = null;

function rotularMicrofone(gravando) {
  elementos.falar.setAttribute("aria-pressed", String(gravando));
  elementos.falarRotulo.textContent = gravando ? "Ouvindo · aperte de novo para enviar" : "Ctrl+Alt+C para falar";
}

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
    mostrarLegenda("Não tenho acesso ao microfone. Use o botão Escrever enquanto isso.");
    return;
  }
  fonteDoMicrofone = contextoDeAudio.createMediaStreamSource(fluxo);
  fonteDoMicrofone.connect(analisadorDoMicrofone);
  pedacos = [];
  gravador = new MediaRecorder(fluxo, { mimeType: "audio/webm;codecs=opus" });
  gravador.addEventListener("dataavailable", (e) => pedacos.push(e.data));
  gravador.addEventListener("stop", () => enviarGravacao(fluxo));
  gravador.start();
  rotularMicrofone(true);
  esconderVoce();
  mudarEstado("listening");
}

async function enviarGravacao(fluxo) {
  fluxo.getTracks().forEach((trilha) => trilha.stop());
  if (fonteDoMicrofone) fonteDoMicrofone.disconnect();
  fonteDoMicrofone = null;
  rotularMicrofone(false);
  mudarEstado("thinking");
  const audio = new Blob(pedacos, { type: "audio/webm" });
  await chamar("/api/voz", { method: "POST", headers: { "Content-Type": "audio/webm" }, body: audio });
}

/* ---------- uma voz só ----------
   Com várias abas abertas, todas mostram a conversa, mas só a que o servidor escolheu toca o som;
   as outras tocam mudas, para a legenda e o chat andarem juntos. A aba que a pessoa usa pede a voz. */

let tenhoAVoz = true;
let canalAberto = null;

function receberAVoz(sua) {
  tenhoAVoz = sua;
  if (falaAtual) falaAtual.trechos.forEach((t) => { if (t) t.audio.muted = !sua; });
}

function pedirAVoz() {
  if (!tenhoAVoz && canalAberto && canalAberto.readyState === WebSocket.OPEN) canalAberto.send("voz");
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
    mostrarLegenda("Não consegui falar com o servidor da Clarisse.");
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
  transcricao: (e) => {
    if (e.texto) return;
    adicionarFala("aviso", "Não entendi o que foi dito. Tente de novo.");
    mostrarLegenda("Não entendi o que foi dito. Tente de novo.");
    setTimeout(() => { if (!falaAtual) mostrarLegenda(null); }, 4000);
  },
  fala_do_usuario: (e) => mostrarVoce(e.texto),
  resposta: (e) => esperarFala(e.fala, () => {
    mostrarClarisse(e.texto, e.aguardando_confirmacao);
    if (e.cartao) Cartoes.mostrar(e.cartao);
  }),
  aviso: (e) => esperarFala(e.fala, () => {
    mostrarClarisse(e.falado || `Do ${e.titulo}: ${e.texto}`);
    if (e.cartao) Cartoes.mostrar(e.cartao);
  }),
  falar: receberTrecho,
  ferramenta: (e) => { if (e.grupo) Nucleo.acender(e.grupo, e.situacao === "iniciada"); },
  parar: () => pararDeFalar(),
  // O atalho de teclado chega a todas as abas; só a que tem a voz grava, senão o pedido iria duas vezes.
  escutar: () => { if (tenhoAVoz) alternarMicrofone(); },
  voz: (e) => receberAVoz(e.sua),
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
  canalAberto = canal;
  canal.addEventListener("open", () => {
    espera = 500;
    if (document.hasFocus()) canal.send("voz");
  });
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

window.addEventListener("focus", pedirAVoz);
document.addEventListener("pointerdown", pedirAVoz);
document.addEventListener("keydown", pedirAVoz);

elementos.falar.addEventListener("click", alternarMicrofone);
elementos.escrever.addEventListener("click", () => abrirChat(!elementos.corpo.classList.contains("com-chat")));
elementos.fecharChat.addEventListener("click", () => abrirChat(false));
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

function relogio() {
  elementos.hora.textContent = new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

/* ---------- início ---------- */

Cartoes.aoEscolher = (pedido, numero) => {
  liberarSom();
  pedirAVoz();
  enviarTexto(`${pedido} ${numero}`);
};
// Para a leitura na hora e mostra a lista de novo, como dizer "volta para a lista".
Cartoes.aoVoltar = () => {
  liberarSom();
  pedirAVoz();
  pararDeFalar();
  enviarTexto("volta para a lista");
};
Nucleo.nivel = nivelDoSom;
Nucleo.grupos(GRUPOS);
Nucleo.iniciar(document.getElementById("nucleo"));
relogio();
setInterval(relogio, 15000);
mudarEstado("idle");
conectar();
