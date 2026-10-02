"""O que o Claude pode pedir pela Clarisse: o registro inteiro, menos o que chamaria outro Claude."""
from clarisse.ferramentas.registro import Registro


class FerramentasExternas:
    def __init__(self, registro: Registro, agente, fora: set[str], sempre_confirmar: set[str] = frozenset()):
        self._registro = registro
        self._agente = agente
        self._fora = fora
        # Seguras para o modelo local, mas o Claude lê a web e pode ser enganado: pedem o "sim".
        self._sempre_confirmar = sempre_confirmar

    def esquemas(self) -> list[dict]:
        return [
            {"nome": e["function"]["name"], "descricao": e["function"]["description"], "parametros": e["function"]["parameters"]}
            for e in self._registro.esquemas()
            if e["function"]["name"] not in self._fora
        ]

    async def executar(self, nome: str, argumentos: dict) -> str:
        if nome in self._fora:
            return f"Recusado: {nome} não pode ser pedida pelo Claude."
        return await self._agente.executar_externo(nome, argumentos, sempre_confirmar=nome in self._sempre_confirmar)
