from __future__ import annotations

from urllib.parse import quote

from catalogo.lojas import Loja
from catalogo.models import Produto, reais


def texto_pedido(produto: Produto) -> str:
    """Mensagem pré-preenchida: preço único no final ou preço por código quando varia."""
    if produto.precos_variam:
        itens = [
            f"{c} — {reais(pr)}" if pr is not None else c
            for c, pr in zip(produto.todos_codigos, produto.precos)
        ]
        return f"Olá! Quero consultar a peça: {produto.descricao} (cód. {'; '.join(itens)})"
    partes = [f"Olá! Quero consultar a peça: {produto.descricao} (cód. {', '.join(produto.todos_codigos)})"]
    if produto.preco is not None:
        partes.append(f"— {reais(produto.preco)}")
    return " ".join(partes)


def link_pedido(produto: Produto, loja: Loja) -> str:
    return f"https://wa.me/{loja.whatsapp}?text={quote(texto_pedido(produto))}"
