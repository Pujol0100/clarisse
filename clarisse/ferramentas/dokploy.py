"""Situação de um sistema nos painéis do Dokploy: se está no ar e como foi o último deploy. Só leitura,
com a mesma chave que já lista os sites (ver clarisse/sites.py). A lista de projetos traz só nome,
identificador e situação de cada aplicação; nada de variável de ambiente passa por aqui."""
from collections.abc import Callable
from datetime import datetime
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
from pydantic import Field

from clarisse.cartoes import Retorno
from clarisse.config import normalizar
from clarisse.ferramentas.registro import Argumentos, Ferramenta

_BRASILIA = ZoneInfo("America/Sao_Paulo")
_SITUACOES = {"done": "no ar", "idle": "parado", "running": "subindo", "error": "com erro"}
_DEPLOYS = {"done": "concluído", "error": "com erro", "running": "rodando", "queued": "na fila", "cancelled": "cancelado"}


class ArgsSistema(Argumentos):
    sistema: str = Field(min_length=2, max_length=80, description="Nome do sistema, como o usuário falou")


def ferramentas_do_dokploy(http: httpx.AsyncClient, paineis: Callable[[], list[tuple[str, str]]]) -> list[Ferramenta]:
    async def get(url: str, chave: str, rota: str, **parametros):
        resposta = await http.get(f"{url}/api/{rota}", params=parametros, headers={"x-api-key": chave}, timeout=20)
        resposta.raise_for_status()
        return resposta.json()

    async def situacao_do_sistema(args: ArgsSistema) -> Retorno | str:
        acessos = paineis()
        if not acessos:
            return "Não tenho acesso a nenhum painel do Dokploy."
        aplicacoes = []
        for url, chave in acessos:
            try:
                projetos = await get(url, chave, "project.all")
            except httpx.HTTPError:
                continue
            for projeto in projetos:
                for ambiente in projeto.get("environments", []):
                    for app in ambiente.get("applications", []):
                        aplicacoes.append((app, url, chave))
        alvo = normalizar(args.sistema)
        exatas = [a for a in aplicacoes if normalizar(a[0]["name"]) == alvo]
        achadas = exatas or [a for a in aplicacoes if alvo in normalizar(a[0]["name"])]
        if not achadas:
            return f"Não achei o sistema {args.sistema} no Dokploy."
        if len(achadas) > 1:
            return f"Achei mais de um sistema com esse nome: {', '.join(a[0]['name'] for a in achadas)}. Qual deles?"
        app, url, chave = achadas[0]
        nome, situacao = app["name"], _SITUACOES.get(app.get("applicationStatus"), app.get("applicationStatus") or "sem situação")
        deploys = await get(url, chave, "deployment.all", applicationId=app["applicationId"])
        painel = urlparse(url).hostname
        itens = [["situação", situacao]]
        if deploys:
            ultimo = deploys[0]
            quando = datetime.fromisoformat(ultimo["createdAt"].replace("Z", "+00:00")).astimezone(_BRASILIA)
            como = _DEPLOYS.get(ultimo.get("status"), ultimo.get("status") or "")
            titulo = (ultimo.get("title") or "").strip()
            texto = (f"{nome} está {situacao}. Último deploy em {quando:%d/%m} às {quando:%H:%M}, {como}"
                     + (f": {titulo}." if titulo else "."))
            itens.append(["último deploy", f"{quando:%d/%m %H:%M} · {como}"])
        else:
            texto = f"{nome} está {situacao}. Nenhum deploy registrado."
        itens.append(["painel", painel])
        cartao = {"tipo": "lista", "titulo": "Servidores", "canto": nome, "itens": itens}
        return Retorno(texto, cartao=cartao, na_integra=True)

    return [
        Ferramenta(
            "situacao_do_sistema",
            "Diz se um sistema da empresa está no ar no Dokploy e como foi o último deploy. "
            "Use para 'o omni está no ar?', 'como foi o último deploy do X?'.",
            ArgsSistema, situacao_do_sistema, grupo="servidores",
        )
    ]
