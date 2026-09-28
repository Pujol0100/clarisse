"""O laço da Clarisse: fala → modelo → segurança → ferramenta → modelo → resposta."""
import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from clarisse.auditoria import Auditoria
from clarisse.eventos import Estado, Eventos
from clarisse.ferramentas.registro import Registro
from clarisse.ferramentas.sistema import data_por_extenso
from clarisse.llm import ErroDoModelo
from clarisse.seguranca import Decisao, avaliar, confirma, nega, pede_para_parar

log = logging.getLogger(__name__)

_TAMANHO_DO_HISTORICO = 12


def prompt_do_sistema(projetos: list[str], agora: datetime) -> str:
    return f"""Você é a Clarisse, assistente de voz que roda no computador do usuário.
Hoje é {data_por_extenso(agora)}.
Responda sempre em português do Brasil, em no máximo duas frases curtas, porque a resposta será falada.
Quando o pedido exigir uma ação ou uma informação do mundo real, chame a ferramenta adequada. Nunca invente o resultado de uma ferramenta e nunca diga que fez algo sem ter chamado a ferramenta.
Para conversa, contas simples ou conhecimento geral, responda direto, sem ferramenta.
Tarefas complexas de programação, análise, leitura de sites ou agenda vão para o Claude.
Não peça confirmação nem detalhes: chame a ferramenta direto com o que o usuário disse. O sistema confirma sozinho as ações arriscadas.
Projetos cadastrados: {", ".join(projetos) or "nenhum"}. A transcrição de voz pode errar o nome; escolha o projeto cadastrado mais parecido."""


@dataclass
class Resposta:
    texto: str
    parar: bool = False
    aguardando_confirmacao: bool = False


class Agente:
    def __init__(
        self,
        modelo,
        registro: Registro,
        eventos: Eventos,
        auditoria: Auditoria,
        projetos: list[str],
        agora: Callable[[], datetime] = datetime.now,
        max_rodadas: int = 4,
        timeout_da_ferramenta: float = 180,
    ):
        self._modelo = modelo
        self._registro = registro
        self._eventos = eventos
        self._auditoria = auditoria
        self._projetos = projetos
        self._agora = agora
        self._max_rodadas = max_rodadas
        self._timeout = timeout_da_ferramenta
        self._historico: list[dict] = []
        self._pendente: tuple[Decisao, list[dict]] | None = None
        self._trava = asyncio.Lock()

    async def responder(self, fala: str) -> Resposta:
        async with self._trava:
            fala = fala.strip()
            if pede_para_parar(fala):
                self._pendente = None
                return Resposta("Parei.", parar=True)

            if self._pendente:
                decisao, mensagens = self._pendente
                self._pendente = None
                if confirma(fala):
                    mensagens.append(await self._executar(decisao))
                    return await self._laco(mensagens, fala)
                if nega(fala):
                    return self._concluir(fala, "Tudo bem, cancelei.")

            mensagens = [
                {"role": "system", "content": prompt_do_sistema(self._projetos, self._agora())},
                *self._historico,
                {"role": "user", "content": fala},
            ]
            return await self._laco(mensagens, fala)

    async def _laco(self, mensagens: list[dict], fala: str) -> Resposta:
        for _ in range(self._max_rodadas):
            await self._eventos.estado(Estado.PENSANDO)
            try:
                resposta = await self._modelo.conversar(mensagens, self._registro.esquemas())
            except ErroDoModelo as erro:
                log.warning("modelo local falhou: %s", erro)
                return self._concluir(fala, f"Não consegui falar com o modelo local: {erro}.")
            if not resposta.chamadas:
                return self._concluir(fala, resposta.texto or "Pronto.")

            mensagens.append(resposta.mensagem)
            for chamada in resposta.chamadas:
                decisao = avaliar(self._registro, chamada.nome, chamada.argumentos)
                if decisao.acao == "recusar":
                    mensagens.append(_mensagem_de_ferramenta(chamada.nome, f"Erro: {decisao.motivo}."))
                elif decisao.acao == "confirmar":
                    self._pendente = (decisao, mensagens)
                    frase = decisao.ferramenta.frase_de_confirmacao(decisao.args)
                    return self._concluir(fala, frase, aguardando=True)
                else:
                    mensagens.append(await self._executar(decisao))
        return self._concluir(fala, "Não consegui concluir esse pedido. Tente dizer de outro jeito.")

    async def _executar(self, decisao: Decisao) -> dict:
        nome = decisao.ferramenta.nome
        await self._eventos.estado(Estado.EXECUTANDO)
        await self._eventos.publicar({"tipo": "ferramenta", "ferramenta": nome, "situacao": "iniciada"})
        inicio = time.monotonic()
        try:
            resultado = await asyncio.wait_for(decisao.ferramenta.executar(decisao.args), self._timeout)
            situacao = "concluida"
        except Exception as erro:
            log.exception("ferramenta %s falhou", nome)
            resultado = f"Erro ao executar {nome}: {erro}"
            situacao = "erro"
        self._auditoria.registrar(
            ferramenta=nome,
            argumentos=decisao.args.model_dump(),
            risco=decisao.ferramenta.risco_de(decisao.args).value,
            situacao="ok" if situacao == "concluida" else "erro",
            duracao_ms=round((time.monotonic() - inicio) * 1000),
        )
        await self._eventos.publicar({"tipo": "ferramenta", "ferramenta": nome, "situacao": situacao})
        return _mensagem_de_ferramenta(nome, resultado)

    def _concluir(self, fala: str, texto: str, aguardando: bool = False) -> Resposta:
        self._historico += [{"role": "user", "content": fala}, {"role": "assistant", "content": texto}]
        self._historico = self._historico[-_TAMANHO_DO_HISTORICO:]
        return Resposta(texto, aguardando_confirmacao=aguardando)


def _mensagem_de_ferramenta(nome: str, conteudo: str) -> dict:
    return {"role": "tool", "tool_name": nome, "content": conteudo}
