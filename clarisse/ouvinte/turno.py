"""O marcador que autoriza a Clarisse a falar sozinha.

A regra de 21/08, depois de ela interromper uma reuniao: a fala automatica so
acontece dentro de um turno que o usuario abriu. Ditar abre o turno; o hook Stop
consome. Sem marcador, o hook so bipa e espera o atalho.

O turno e por projeto porque sao ~10 sessoes abertas. Marcador de um projeto
abrindo a boca de outro seria a mesma interrupcao com outro nome.

O `UserPromptSubmit` nao serve para abrir turno sozinho: ele dispara em todo
prompt, inclusive digitado, e a Clarisse voltaria a falar em todas as sessoes.

O nome do arquivo segue a mesma troca de caractere proibido que o
`Get-CaminhoEntrada` do nucleo.ps1 faz — os dois lados precisam chegar ao mesmo
nome, porque quem escreve e quem le nao sao o mesmo processo.
"""

from __future__ import annotations

from pathlib import Path

VALIDADE_S = 15 * 60

_PROIBIDOS = '<>:"/\\|?*'


def caminho_do_marcador(pasta: Path, projeto: str) -> Path | None:
    """Devolve o arquivo daquele projeto, ou None se o projeto nao tem nome."""
    if not projeto or not projeto.strip():
        return None

    limpo = ''.join('-' if c in _PROIBIDOS or ord(c) < 32 else c for c in projeto)
    return Path(pasta) / f'{limpo}.txt'


def abrir(pasta: Path, projeto: str, *, agora: float) -> None:
    """Marca que o usuario falou neste projeto, agora."""
    arquivo = caminho_do_marcador(pasta, projeto)
    if arquivo is None:
        return

    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(repr(agora), encoding='utf-8')


def consumir(
    pasta: Path,
    projeto: str,
    *,
    agora: float,
    validade_s: float = VALIDADE_S,
) -> bool:
    """Gasta o turno daquele projeto. Verdadeiro so uma vez por ditado.

    Marcador vencido, estragado ou do futuro e removido em vez de ignorado: um
    arquivo esquecido que volta a valer depois e pior do que marcador nenhum.
    """
    arquivo = caminho_do_marcador(pasta, projeto)
    if arquivo is None:
        return False

    try:
        marcado = float(arquivo.read_text(encoding='utf-8').strip())
    except (OSError, ValueError):
        arquivo.unlink(missing_ok=True)
        return False

    arquivo.unlink(missing_ok=True)
    return 0 <= agora - marcado <= validade_s
