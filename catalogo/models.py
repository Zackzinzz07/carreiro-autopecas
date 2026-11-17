from __future__ import annotations

from dataclasses import dataclass


def reais(valor: float) -> str:
    """Formata valor numérico como moeda brasileira: 'R$ 1.234,56'."""
    numero = f"{valor:,.2f}".translate(str.maketrans(",.", ".,"))
    return f"R$ {numero}"


@dataclass(frozen=True)
class Produto:
    id: int
    codigo: str
    descricao: str
    categoria: str
    tipo: str = ""
    marca: str = ""
    referencia: str = ""   # código alternativo (coluna "Cód Barras" quando difere do código)
    ean: str = ""          # EAN/GTIN de verdade (8, 12, 13 ou 14 dígitos)
    aplicacao: str = ""
    preco: float | None = None
    imagem_url: str = ""
    ativo: bool = True
    codigos: tuple[str, ...] = ()   # card que junta linhas repetidas da planilha: todos os códigos da mesma descrição
    precos: tuple[float | None, ...] = ()   # preços na mesma ordem de codigos

    @property
    def todos_codigos(self) -> tuple[str, ...]:
        return self.codigos or (self.codigo,)

    @property
    def preco_min(self) -> float | None:
        validos = [p for p in self.precos if p is not None]
        return min(validos) if validos else self.preco

    @property
    def precos_variam(self) -> bool:
        # Código sem preço também conta como diferença: o card mostra "a partir de" com os que têm preço.
        return len(set(self.precos)) > 1 and any(p is not None for p in self.precos)
