"""Ferramentas dos projetos cadastrados: abrir no VS Code e git."""
from typing import Literal

from pydantic import Field, create_model

from clarisse.config import Cadastros
from clarisse.ferramentas.registro import Argumentos, Ferramenta, Risco

_LIMITE_DA_SAIDA = 1500


def campo_projeto(cadastros: Cadastros, descricao: str = "Nome do projeto cadastrado", obrigatorio: bool = True):
    extra = {"enum": list(cadastros.projetos)} if cadastros.projetos else None
    padrao = ... if obrigatorio else None
    tipo = str if obrigatorio else str | None
    return tipo, Field(padrao, max_length=80, description=descricao, json_schema_extra=extra)


def projeto_desconhecido(cadastros: Cadastros, nome: str) -> str:
    return f"Não conheço o projeto {nome}. Os cadastrados são: {', '.join(cadastros.projetos) or 'nenhum'}."


def ferramentas_de_projetos(cadastros: Cadastros, executor) -> list[Ferramenta]:
    ArgsProjeto = create_model("ArgsProjeto", __base__=Argumentos, projeto=campo_projeto(cadastros))
    ArgsGit = create_model(
        "ArgsGit",
        __base__=Argumentos,
        projeto=campo_projeto(cadastros),
        operacao=(Literal["status", "log", "pull"], Field(description="Operação git")),
    )
    comandos = {
        "status": ["status", "--short", "--branch"],
        "log": ["log", "--oneline", "-5"],
        "pull": ["pull", "--ff-only"],
    }

    async def abrir_projeto_vscode(args) -> str:
        chave = cadastros.achar_projeto(args.projeto)
        if chave is None:
            return projeto_desconhecido(cadastros, args.projeto)
        await executor.iniciar(["code", str(cadastros.projetos[chave])])
        return f"Abri o projeto {chave} no VS Code."

    async def git(args) -> str:
        chave = cadastros.achar_projeto(args.projeto)
        if chave is None:
            return projeto_desconhecido(cadastros, args.projeto)
        pasta = str(cadastros.projetos[chave])
        resultado = await executor.executar(["git", "-C", pasta, *comandos[args.operacao]], timeout=120)
        texto = (resultado.saida + resultado.erro).strip()[:_LIMITE_DA_SAIDA]
        if resultado.codigo != 0:
            return f"O git {args.operacao} no {chave} falhou: {texto}"
        return f"git {args.operacao} no {chave}:\n{texto or 'sem saída'}"

    def confirmar_pull(args) -> str:
        return f"Vou atualizar o projeto {args.projeto} com git pull. Confirma?"

    return [
        Ferramenta("abrir_projeto_vscode", "Abre um projeto no VS Code.", ArgsProjeto, abrir_projeto_vscode),
        Ferramenta(
            "git", "Executa uma operação git num projeto: status, log ou pull.", ArgsGit, git,
            risco=lambda a: Risco.CONFIRMAR if a.operacao == "pull" else Risco.SEGURO,
            descrever=confirmar_pull,
        ),
    ]
