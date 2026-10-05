from __future__ import annotations

from dataclasses import dataclass


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
