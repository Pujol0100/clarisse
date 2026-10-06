"""Agenda e e-mail do Outlook, só leitura, pelo login Microsoft da Clarisse (ver clarisse/microsoft.py).

A lista de e-mails é falada pelo sistema, sem passar pelo modelo: assunto de e-mail é escrito por
qualquer um e não pode virar instrução. O mesmo vale para o corpo, lido na íntegra."""
import re
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
from pydantic import Field

from clarisse.cartoes import Retorno, UltimaEscolha
from clarisse.config import normalizar
from clarisse.ferramentas.registro import Argumentos, Ferramenta, Risco
from clarisse.microsoft import FUSO, SemContaMicrosoft

_BRASILIA = ZoneInfo("America/Sao_Paulo")
_DIAS = ["seg", "ter", "qua", "qui", "sex", "sáb", "dom"]
_PERIODOS = {"hoje": (0, 1), "amanha": (1, 1), "depois-de-amanha": (2, 1), "semana": (0, 7)}
_NOMES = {"hoje": "Hoje", "amanha": "Amanhã", "depois-de-amanha": "Depois de amanhã", "semana": "Nos próximos 7 dias"}
_NA_LISTA = 10
# Onde começa o histórico citado de uma resposta: daí para baixo não se lê.
_HISTORICO = re.compile(r"^(De|From|Enviado|Sent):\s|^-{2,}\s*(Mensagem original|Original Message)|^Em .+ escreveu:$", re.IGNORECASE)
_LIMITE_DO_CORPO = 4000


def _periodo(texto: str | None) -> str:
    chave = normalizar(texto or "hoje")
    if "semana" in chave:
        return "semana"
    return chave if chave in _PERIODOS else "hoje"


def _hora(evento: dict) -> datetime:
    return datetime.fromisoformat(evento["start"]["dateTime"][:19])


def _paragrafos_do_email(corpo: str) -> list[str]:
    paragrafos, atual = [], []
    for linha in corpo.replace("\r\n", "\n").split("\n"):
        linha = linha.strip()
        if _HISTORICO.match(linha):
            break
        if linha:
            atual.append(linha)
        elif atual:
            paragrafos.append(" ".join(atual))
            atual = []
    if atual:
        paragrafos.append(" ".join(atual))
    cabem, total = [], 0
    for paragrafo in paragrafos:
        total += len(paragrafo)
        if total > _LIMITE_DO_CORPO:
            break
        cabem.append(paragrafo)
    return cabem


def _remetente(mensagem: dict) -> str:
    endereco = (mensagem.get("from") or {}).get("emailAddress") or {}
    return endereco.get("name") or endereco.get("address") or "remetente desconhecido"


class ArgsAgenda(Argumentos):
    periodo: str | None = Field("hoje", max_length=40, description="hoje, amanhã, depois de amanhã ou semana")


_ENDERECO = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _paragrafos_do_texto(texto: str) -> list[str]:
    blocos = re.split(r"\n\s*\n", texto.replace("\r\n", "\n").strip())
    return [" ".join(linha.strip() for linha in bloco.splitlines() if linha.strip()) for bloco in blocos if bloco.strip()]


class ArgsEscreverEmail(Argumentos):
    para: str = Field(min_length=2, max_length=120, description="Nome da pessoa ou endereço de e-mail, como o usuário disse")
    sobre: str = Field(min_length=2, max_length=1000, description="O que o e-mail deve dizer, com as palavras do usuário")


class ArgsLerEmail(Argumentos):
    numero: int = Field(ge=1, le=_NA_LISTA, description="Número do e-mail na última lista de não lidos")


def ferramentas_do_outlook(
    conta, agora: Callable[[], datetime] = datetime.now, escolhas: UltimaEscolha | None = None,
    redigir: Callable[[str, str, str | None], Awaitable[tuple[str, str]]] | None = None,
) -> list[Ferramenta]:
    """`redigir(sobre, para, assinatura)` escreve (assunto, texto) do e-mail; sem ele, não há escrita."""
    ultimos: list[dict] = []
    escolhas = escolhas or UltimaEscolha()
    rascunho: dict = {}

    async def destinatario(para: str) -> dict | str:
        """{'address', 'name'?} do destinatário, ou a pergunta a fazer ao usuário."""
        para = para.strip()
        if "@" in para:
            return {"address": para.lower()} if _ENDERECO.match(para) else f"O endereço {para} não parece um e-mail. Diga de novo."
        dados = await conta.get("/me/people", {"$search": f'"{para}"', "$top": "5", "$select": "displayName,scoredEmailAddresses"})
        pessoas = [
            {"address": p["scoredEmailAddresses"][0]["address"], "name": p.get("displayName") or ""}
            for p in dados.get("value", []) if p.get("scoredEmailAddresses")
        ]
        exatas = [p for p in pessoas if normalizar(p["name"]) == normalizar(para)]
        if len(exatas) == 1 or len(pessoas) == 1:
            return (exatas or pessoas)[0]
        if not pessoas:
            return f"Não achei {para} nos seus contatos. Diga o endereço do e-mail."
        nomes = ", ".join(f"{p['name']} ({p['address']})" for p in pessoas)
        return f"Achei mais de uma pessoa: {nomes}. Para qual delas?"

    async def consultar_agenda(args: ArgsAgenda) -> Retorno | str:
        periodo = _periodo(args.periodo)
        desloca, dias = _PERIODOS[periodo]
        inicio = datetime.combine(agora().date() + timedelta(days=desloca), datetime.min.time(), _BRASILIA)
        fim = inicio + timedelta(days=dias)
        try:
            dados = await conta.get(
                "/me/calendarView",
                {"startDateTime": inicio.isoformat(), "endDateTime": fim.isoformat(),
                 "$select": "subject,start,end,isAllDay,isCancelled", "$orderby": "start/dateTime", "$top": "50"},
                {"Prefer": FUSO},
            )
        except (SemContaMicrosoft, httpx.HTTPError) as erro:
            return str(erro) if isinstance(erro, SemContaMicrosoft) else f"Não consegui ler a agenda agora: {type(erro).__name__}."
        eventos = [e for e in dados.get("value", []) if not e.get("isCancelled")]
        eventos.sort(key=lambda e: (not e.get("isAllDay"), _hora(e)))
        itens = []
        for evento in eventos:
            hora = "dia todo" if evento.get("isAllDay") else _hora(evento).strftime("%H:%M")
            if periodo == "semana":
                hora = f"{_DIAS[_hora(evento).weekday()]} {hora}"
            itens.append([hora, evento.get("subject") or "(sem título)"])
        nome = _NOMES[periodo]
        if not itens:
            return Retorno(f"{nome}: nenhum compromisso na agenda.", cartao={
                "tipo": "texto", "titulo": "Agenda", "texto": "Nenhum compromisso."})
        lista = "; ".join(f"{hora}, {titulo}" for hora, titulo in itens)
        texto = f"{nome}: {len(itens)} compromisso{'s' if len(itens) > 1 else ''}. {lista}."
        cartao = {"tipo": "lista", "titulo": "Agenda", "canto": nome.lower() if periodo != "semana" else "semana", "itens": itens}
        return Retorno(texto, cartao=cartao)

    async def emails_nao_lidos(args: Argumentos) -> Retorno | str:
        try:
            caixa = await conta.get("/me/mailFolders/inbox", {"$select": "unreadItemCount"})
            dados = await conta.get(
                "/me/mailFolders/inbox/messages",
                {"$filter": "isRead eq false", "$top": str(_NA_LISTA), "$orderby": "receivedDateTime desc",
                 "$select": "id,subject,from,receivedDateTime"},
            )
        except (SemContaMicrosoft, httpx.HTTPError) as erro:
            return str(erro) if isinstance(erro, SemContaMicrosoft) else f"Não consegui ler os e-mails agora: {type(erro).__name__}."
        ultimos[:] = dados.get("value", [])
        total = caixa.get("unreadItemCount", len(ultimos))
        if not ultimos:
            return Retorno("Nenhum e-mail não lido na caixa de entrada.", na_integra=True)
        texto = (f"Você tem {total} e-mails não lidos. Os {len(ultimos)} mais recentes estão na tela. "
                 "Qual você quer que eu leia? Diga o número.")
        cartao = {
            "tipo": "escolha", "titulo": "E-mail", "canto": f"{total} não lidos", "pedido": "lê o e-mail",
            "itens": [{"numero": i, "titulo": m.get("subject") or "sem assunto", "detalhe": _remetente(m),
                       "falado": f"de {_remetente(m)}: {m.get('subject') or 'sem assunto'}"}
                      for i, m in enumerate(ultimos, 1)],
        }
        escolhas.guardar(cartao)
        return Retorno(texto, cartao=cartao, na_integra=True)

    async def ler_email(args: ArgsLerEmail) -> Retorno | str:
        if args.numero > len(ultimos):
            return f"Não tenho o e-mail {args.numero}. A lista tem {len(ultimos)}."
        try:
            mensagem = await conta.get(
                f"/me/messages/{ultimos[args.numero - 1]['id']}", {"$select": "subject,from,receivedDateTime,body"},
                {"Prefer": 'outlook.body-content-type="text"'},
            )
        except (SemContaMicrosoft, httpx.HTTPError) as erro:
            return str(erro) if isinstance(erro, SemContaMicrosoft) else f"Não consegui abrir o e-mail agora: {type(erro).__name__}."
        assunto, quem = mensagem.get("subject") or "sem assunto", _remetente(mensagem)
        paragrafos = _paragrafos_do_email((mensagem.get("body") or {}).get("content") or "")
        texto = "\n\n".join([f"E-mail de {quem}: {assunto}.", *paragrafos])
        cartao = {"tipo": "leitura", "rotulo": "E-mail", "lista": True, "titulo": assunto, "subtitulo": f"De {quem}",
                  "imagem": None, "fonte": "Outlook", "paragrafos": paragrafos}
        return Retorno(texto, cartao=cartao, na_integra=True)

    async def escrever_email(args: ArgsEscreverEmail) -> Retorno | str:
        try:
            quem = await destinatario(args.para)
            if isinstance(quem, str):
                return quem
            eu = await conta.get("/me", {"$select": "givenName"})
            assunto, corpo = await redigir(args.sobre, quem.get("name") or quem["address"], eu.get("givenName"))
            criado = await conta.post("/me/messages", {
                "subject": assunto,
                "body": {"contentType": "Text", "content": corpo},
                "toRecipients": [{"emailAddress": quem}],
            })
        except (SemContaMicrosoft, httpx.HTTPError) as erro:
            return str(erro) if isinstance(erro, SemContaMicrosoft) else f"Não consegui escrever o e-mail agora: {type(erro).__name__}."
        rascunho.clear()
        rascunho.update(id=criado["id"], assunto=assunto, endereco=quem["address"])
        nome = f"{quem['name']} ({quem['address']})" if quem.get("name") else quem["address"]
        texto = (f"Escrevi o e-mail para {nome}, com o assunto {assunto}. Está na tela e salvo nos rascunhos. "
                 "Deseja enviar? Se não, ele fica nos rascunhos.")
        cartao = {"tipo": "leitura", "rotulo": "E-mail para enviar", "titulo": assunto, "subtitulo": f"Para {nome}",
                  "imagem": None, "fonte": "rascunho no Outlook", "paragrafos": _paragrafos_do_texto(corpo)}
        return Retorno(texto, cartao=cartao, na_integra=True, confirmar_depois=("enviar_email", {}))

    def confirmar_envio(args: Argumentos) -> str:
        if not rascunho:
            return "Não tenho e-mail escrito para enviar. Confirma?"
        return f"Envio o e-mail {rascunho['assunto']} para {rascunho['endereco']}? Confirma?"

    async def enviar_email(args: Argumentos) -> Retorno | str:
        if not rascunho:
            return "Não tenho e-mail escrito para enviar."
        try:
            await conta.post(f"/me/messages/{rascunho['id']}/send", None)
        except (SemContaMicrosoft, httpx.HTTPError) as erro:
            return str(erro) if isinstance(erro, SemContaMicrosoft) else f"Não consegui enviar agora: {type(erro).__name__}. O e-mail continua nos rascunhos."
        endereco = rascunho["endereco"]
        rascunho.clear()
        return Retorno(f"Enviei o e-mail para {endereco}.", na_integra=True)

    return [
        Ferramenta(
            "escrever_email",
            "Escreve um e-mail para uma pessoa (nome ou endereço), salva como rascunho no Outlook e mostra na tela. "
            "Use para 'escreve um e-mail para…', 'manda um e-mail para…'. O envio é perguntado depois.",
            ArgsEscreverEmail, escrever_email, grupo="email",
        ),
        Ferramenta(
            "enviar_email",
            "Envia o e-mail que acabou de ser escrito. Só depois de escrever_email.",
            Argumentos, enviar_email, risco=Risco.CONFIRMAR, descrever=confirmar_envio, grupo="email",
        ),
        Ferramenta(
            "consultar_agenda",
            "Lê os compromissos da agenda do Outlook de hoje, amanhã, depois de amanhã ou da semana.",
            ArgsAgenda, consultar_agenda, grupo="agenda",
        ),
        Ferramenta(
            "emails_nao_lidos",
            "Lista os e-mails não lidos da caixa de entrada do Outlook. Use para 'tenho e-mail?', 'e-mails novos'.",
            Argumentos, emails_nao_lidos, grupo="email",
        ),
        Ferramenta(
            "ler_email",
            "Lê na íntegra um e-mail da última lista de não lidos, pelo número ('lê o e-mail 2').",
            ArgsLerEmail, ler_email, grupo="email",
        ),
    ]
