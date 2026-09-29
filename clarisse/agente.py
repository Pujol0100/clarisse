"""O laço da Clarisse: fala → modelo → segurança → ferramenta → modelo → resposta."""
import asyncio
import logging
import re
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from clarisse.auditoria import Auditoria
from clarisse.eventos import Estado, Eventos
from clarisse.figuras import Retorno
from clarisse.ferramentas.registro import Registro
from clarisse.ferramentas.sistema import data_por_extenso
from clarisse.llm import ErroDoModelo
from clarisse.seguranca import Decisao, avaliar, confirma, nega, pede_para_parar

log = logging.getLogger(__name__)

_CONVERSAS_LEMBRADAS = 4
_LIMITE_DO_RESULTADO_LEMBRADO = 300
_ANUNCIO = re.compile(r"\b(vou|irei|vamos)\b", re.IGNORECASE)
_CITA_O_CLAUDE = re.compile(r"\bclaude\b", re.IGNORECASE)
_CUTUCADA = {
    "role": "user",
    "content": "Você disse que ia fazer isso, mas não chamou nenhuma ferramenta. "
    "Chame a ferramenta agora, ou diga em uma frase por que não pode.",
}


def prompt_do_sistema(projetos: list[str], agora: datetime, cidade: str | None = None) -> str:
    texto = f"""Você é a Clarisse, assistente de voz que roda no computador do usuário.
Hoje é {data_por_extenso(agora)}.
Responda sempre em português do Brasil, em no máximo duas frases curtas, porque a resposta será falada.
Quando o pedido exigir uma ação ou uma informação do mundo real, chame a ferramenta adequada. Nunca invente o resultado de uma ferramenta e nunca diga que fez algo sem ter chamado a ferramenta.
Para conversa, contas simples ou conhecimento geral, responda direto, sem ferramenta.
Tarefas complexas de programação, análise, leitura de sites ou agenda vão para o Claude.
Qualquer pergunta sobre a agenda, inclusive se um compromisso que você acabou de criar está lá, chama consultar_agenda. Nunca confirme o que está na agenda de memória.
Quando o usuário mencionar o Claude, chame pedir_ao_claude (ou abrir_claude_na_tela, se ele quiser ver o Claude trabalhando) na mesma hora. Nunca responda que vai pedir ao Claude sem chamar a ferramenta.
Não peça confirmação nem detalhes: chame a ferramenta direto com o que o usuário disse. O sistema confirma sozinho as ações arriscadas.
Se nenhuma ferramenta faz exatamente o que o usuário pediu, diga que não consegue fazer isso e o que consegue fazer no lugar. Nunca faça outra coisa parecida dizendo que fez o pedido.
Projetos cadastrados: {", ".join(projetos) or "nenhum"}. A transcrição de voz pode errar o nome; escolha o projeto cadastrado mais parecido."""
    if cidade:
        texto += f"\nO usuário mora em {cidade}. Em perguntas de tempo, clima, frio, calor ou chuva sem cidade, chame previsao_do_tempo com cidade {cidade}."
    return texto


@dataclass
class Resposta:
    texto: str
    parar: bool = False
    aguardando_confirmacao: bool = False
    figura: str | None = None


class Agente:
    def __init__(
        self,
        modelo,
        registro: Registro,
        eventos: Eventos,
        auditoria: Auditoria,
        projetos: list[str],
        agora: Callable[[], datetime] = datetime.now,
        cidade: str | None = None,
        max_rodadas: int = 4,
        timeout_da_ferramenta: float = 180,
    ):
        self._modelo = modelo
        self._registro = registro
        self._eventos = eventos
        self._auditoria = auditoria
        self._projetos = projetos
        self._cidade = cidade
        self._agora = agora
        self._max_rodadas = max_rodadas
        self._timeout = timeout_da_ferramenta
        self._conversas: list[list[dict]] = []
        self._pendente: tuple[Decisao, list[dict], int] | None = None
        self._trava = asyncio.Lock()
        self._figura: str | None = None

    async def responder(self, fala: str) -> Resposta:
        async with self._trava:
            fala = fala.strip()
            self._figura = None
            if pede_para_parar(fala):
                self._pendente = None
                return Resposta("Parei.", parar=True)

            if self._pendente:
                decisao, mensagens, inicio = self._pendente
                self._pendente = None
                if confirma(fala):
                    self._conversas.pop()
                    mensagens.append(await self._executar(decisao))
                    return await self._laco(mensagens, inicio)
                if nega(fala):
                    return self._concluir([{"role": "user", "content": fala}], 0, "Tudo bem, cancelei.")

            mensagens = [
                {"role": "system", "content": prompt_do_sistema(self._projetos, self._agora(), self._cidade)},
                *self._historico(),
                {"role": "user", "content": fala},
            ]
            return await self._laco(mensagens, len(mensagens) - 1)

    async def _laco(self, mensagens: list[dict], inicio: int) -> Resposta:
        for _ in range(self._max_rodadas):
            await self._eventos.estado(Estado.PENSANDO)
            try:
                resposta = await self._perguntar(mensagens)
            except ErroDoModelo as erro:
                log.warning("modelo local falhou: %s", erro)
                return self._concluir(mensagens, inicio, f"Não consegui falar com o modelo local: {erro}.")
            if not resposta.chamadas:
                fala = mensagens[inicio]["content"]
                agiu = any(m["role"] == "tool" for m in mensagens[inicio:])
                if not agiu and _CITA_O_CLAUDE.search(fala) and "pedir_ao_claude" in self._registro.nomes():
                    return await self._delegar_ao_claude(mensagens, inicio, fala)
                return self._concluir(mensagens, inicio, resposta.texto or _ultimo_resultado(mensagens) or "Pronto.")

            mensagens.append(resposta.mensagem)
            for chamada in resposta.chamadas:
                decisao = avaliar(self._registro, chamada.nome, chamada.argumentos)
                if decisao.acao == "recusar":
                    mensagens.append(_mensagem_de_ferramenta(chamada.nome, f"Erro: {decisao.motivo}."))
                elif decisao.acao == "confirmar":
                    self._pendente = (decisao, mensagens, inicio)
                    frase = decisao.ferramenta.frase_de_confirmacao(decisao.args)
                    espera = _mensagem_de_ferramenta(chamada.nome, "Aguardando a confirmação do usuário.")
                    return self._concluir([*mensagens[inicio:], espera], 0, frase, aguardando=True)
                else:
                    mensagens.append(await self._executar(decisao))
        return self._concluir(mensagens, inicio, "Não consegui concluir esse pedido. Tente dizer de outro jeito.")

    async def _perguntar(self, mensagens: list[dict]):
        """Quem anuncia uma ação sem chamar a ferramenta ganha uma segunda chance, fora do histórico."""
        esquemas = self._registro.esquemas()
        resposta = await self._modelo.conversar(mensagens, esquemas)
        if not resposta.chamadas and _ANUNCIO.search(resposta.texto):
            resposta = await self._modelo.conversar([*mensagens, resposta.mensagem, _CUTUCADA], esquemas)
        return resposta

    async def _delegar_ao_claude(self, mensagens: list[dict], inicio: int, fala: str) -> Resposta:
        """O usuário citou o Claude e o modelo não chamou nada: a frase dele vai inteira para o Claude."""
        argumentos = {"pedido": fala}
        decisao = avaliar(self._registro, "pedir_ao_claude", argumentos)
        if decisao.acao != "executar":
            return self._concluir(mensagens, inicio, f"Não consegui passar o pedido ao Claude: {decisao.motivo}.")
        chamada = {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "pedir_ao_claude", "arguments": argumentos}}]}
        resultado = await self._executar(decisao)
        mensagens += [chamada, resultado]
        return self._concluir(mensagens, inicio, resultado["content"])

    async def _executar(self, decisao: Decisao) -> dict:
        nome = decisao.ferramenta.nome
        await self._eventos.estado(Estado.EXECUTANDO)
        await self._eventos.publicar({"tipo": "ferramenta", "ferramenta": nome, "situacao": "iniciada"})
        inicio = time.monotonic()
        try:
            resultado = await asyncio.wait_for(decisao.ferramenta.executar(decisao.args), self._timeout)
            situacao = "concluida"
            if isinstance(resultado, Retorno):
                self._figura = resultado.figura or decisao.ferramenta.figura
                resultado = resultado.texto
            else:
                self._figura = decisao.ferramenta.figura or self._figura
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

    def _historico(self) -> list[dict]:
        return [mensagem for conversa in self._conversas for mensagem in conversa]

    def _concluir(self, mensagens: list[dict], inicio: int, texto: str, aguardando: bool = False) -> Resposta:
        conversa = [_encurtar(m) for m in mensagens[inicio:]] + [{"role": "assistant", "content": texto}]
        self._conversas = [*self._conversas, conversa][-_CONVERSAS_LEMBRADAS:]
        return Resposta(texto, aguardando_confirmacao=aguardando, figura=self._figura)


def _encurtar(mensagem: dict) -> dict:
    """O histórico guarda as chamadas de ferramenta: sem elas o modelo imita as respostas e para de agir."""
    conteudo = mensagem.get("content") or ""
    if mensagem["role"] == "tool" and len(conteudo) > _LIMITE_DO_RESULTADO_LEMBRADO:
        return {**mensagem, "content": conteudo[:_LIMITE_DO_RESULTADO_LEMBRADO] + "…"}
    return dict(mensagem)


def _ultimo_resultado(mensagens: list[dict]) -> str:
    return next((m["content"] for m in reversed(mensagens) if m["role"] == "tool"), "")


def _mensagem_de_ferramenta(nome: str, conteudo: str) -> dict:
    return {"role": "tool", "tool_name": nome, "content": conteudo}
