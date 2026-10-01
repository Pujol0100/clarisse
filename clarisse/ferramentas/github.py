"""PRs abertas e checagens de uma PR pelo gh, que já está logado nesta máquina. Só leitura.

A resposta é falada pelo sistema: título de PR pode ter sido escrito por outra pessoa."""
import json
from typing import Literal

from pydantic import Field, create_model

from clarisse.cartoes import Retorno
from clarisse.config import Cadastros
from clarisse.ferramentas.projetos import campo_projeto, projeto_desconhecido
from clarisse.ferramentas.registro import Argumentos, Ferramenta

# Situação de cada checagem no singular e no plural, na ordem em que importa ouvir.
_SITUACOES = {
    "fail": ("falhou", "falharam"), "cancel": ("cancelada", "canceladas"), "pending": ("rodando", "rodando"),
    "pass": ("passou", "passaram"), "skipping": ("pulada", "puladas"),
}


class ArgsPrs(Argumentos):
    de: Literal["minhas", "para_eu_revisar"] = Field(
        "minhas", description="minhas = PRs que o usuário abriu; para_eu_revisar = PRs que pedem a revisão dele",
    )


def ferramentas_do_github(executor, cadastros: Cadastros) -> list[Ferramenta]:
    ArgsPr = create_model(
        "ArgsPr", __base__=Argumentos,
        projeto=campo_projeto(cadastros),
        numero=(int, Field(ge=1, description="Número da PR")),
    )

    async def prs_abertas(args: ArgsPrs) -> Retorno | str:
        filtro = "--author=@me" if args.de == "minhas" else "--review-requested=@me"
        resultado = await executor.executar(
            ["gh", "search", "prs", filtro, "--state=open", "--json", "number,title,repository", "--limit", "10"],
            timeout=30,
        )
        try:
            prs = json.loads(resultado.saida)
        except json.JSONDecodeError:
            return "Não consegui consultar o GitHub agora."
        if not prs:
            vazio = "Nenhuma PR sua aberta." if args.de == "minhas" else "Nenhuma PR esperando a sua revisão."
            return Retorno(vazio, na_integra=True)
        quais = "abertas" if args.de == "minhas" else "esperando a sua revisão"
        lista = " ".join(f"{p['number']} do {p['repository']['name']}, {p['title']}." for p in prs)
        texto = f"Você tem {len(prs)} PR{'s' if len(prs) > 1 else ''} {quais}: {lista}"
        cartao = {
            "tipo": "lista", "titulo": "GitHub",
            "canto": "suas PRs abertas" if args.de == "minhas" else "para você revisar",
            "itens": [[f"#{p['number']}", f"{p['repository']['name']} · {p['title']}"] for p in prs],
        }
        return Retorno(texto, cartao=cartao, na_integra=True)

    async def situacao_da_pr(args) -> Retorno | str:
        chave = cadastros.achar_projeto(args.projeto)
        if chave is None:
            return projeto_desconhecido(cadastros, args.projeto)
        repositorio = await executor.executar(["gh", "repo", "view", "--json", "nameWithOwner"], cadastros.projetos[chave])
        try:
            nome = json.loads(repositorio.saida)["nameWithOwner"]
        except (json.JSONDecodeError, KeyError):
            return f"Não achei o repositório do GitHub do projeto {chave}."
        # O gh sai com código diferente de zero quando alguma checagem falhou ou está rodando: vale a saída.
        checagens = await executor.executar(
            ["gh", "pr", "checks", str(args.numero), "--repo", nome, "--json", "name,state,bucket"], timeout=30,
        )
        try:
            lista = json.loads(checagens.saida) if checagens.saida.strip() else []
        except json.JSONDecodeError:
            lista = []
        if not lista:
            return f"A PR {args.numero} do {chave} não tem checagens automáticas."
        ordem = list(_SITUACOES)
        lista.sort(key=lambda c: ordem.index(c["bucket"]) if c["bucket"] in ordem else len(ordem))
        partes = []
        for bucket, (singular, plural) in _SITUACOES.items():
            quais = [c["name"] for c in lista if c["bucket"] == bucket]
            if not quais:
                continue
            detalhe = f" ({', '.join(quais)})" if bucket != "pass" else ""
            partes.append(f"{len(quais)} {singular if len(quais) == 1 else plural}{detalhe}")
        texto = f"PR {args.numero} do {chave}: {', '.join(partes)}."
        cartao = {
            "tipo": "lista", "titulo": "GitHub", "canto": f"PR {args.numero} · {chave}",
            "itens": [[_SITUACOES.get(c["bucket"], (c["bucket"],))[0], c["name"]] for c in lista],
        }
        return Retorno(texto, cartao=cartao, na_integra=True)

    return [
        Ferramenta(
            "prs_abertas",
            "Lista as PRs abertas no GitHub: as do usuário, ou as que esperam a revisão dele.",
            ArgsPrs, prs_abertas, grupo="github",
        ),
        Ferramenta(
            "situacao_da_pr",
            "Diz se as checagens automáticas (CI) de uma PR de um projeto passaram, falharam ou estão rodando.",
            ArgsPr, situacao_da_pr, grupo="github",
        ),
    ]
