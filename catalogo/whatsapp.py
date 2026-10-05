from __future__ import annotations

from urllib.parse import quote

from catalogo.lojas import Loja
from catalogo.models import Produto


def texto_pedido(produto: Produto) -> str:
    """Mensagem pré-preenchida. Sem preço: a planilha atual não tem essa coluna."""
    partes = [f"Olá! Quero consultar a peça: {produto.descricao} (cód. {produto.codigo})"]
    if produto.preco is not None:
        partes.append(f"— R$ {produto.preco:.2f}".replace(".", ","))
    return " ".join(partes)


def link_pedido(produto: Produto, loja: Loja) -> str:
    return f"https://wa.me/{loja.whatsapp}?text={quote(texto_pedido(produto))}"
