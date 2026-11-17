from catalogo.app import templates
from catalogo.db import listar_produtos, upsert_produto
from catalogo.models import Produto, reais
from catalogo.scripts.gerar_estatico import _item
from catalogo.whatsapp import texto_pedido


def _abracadeira(conn):
    # Inserido fora de ordem para garantir que precos acompanha a ordenação de codigos.
    upsert_produto(conn, Produto(id=0, codigo="008096", descricao="ABRACADEIRA 2.1/4", categoria="Motor", preco=13.0))
    upsert_produto(conn, Produto(id=0, codigo="008089", descricao="ABRACADEIRA 2.1/4", categoria="Motor", preco=14.0))
    conn.commit()
    produtos, _ = listar_produtos(conn, busca="ABRACADEIRA")
    return produtos[0]


def test_card_com_precos_diferentes_alinha_precos_e_calcula_minimo(conn):
    card = _abracadeira(conn)
    assert card.codigos == ("008089", "008096")
    assert card.preco is None
    assert card.precos == (14.0, 13.0)
    assert card.preco_min == 13.0
    assert card.precos_variam is True


def test_card_com_precos_iguais_mantem_preco_unico(conn):
    upsert_produto(conn, Produto(id=0, codigo="009002", descricao="PORCA SEXTAVADA", categoria="Motor", preco=14.0))
    upsert_produto(conn, Produto(id=0, codigo="009001", descricao="PORCA SEXTAVADA", categoria="Motor", preco=14.0))
    conn.commit()
    (card,), _ = listar_produtos(conn, busca="PORCA SEXTAVADA")
    assert card.codigos == ("009001", "009002")
    assert card.preco == 14.0
    assert card.precos == (14.0, 14.0)
    assert card.preco_min == 14.0
    assert card.precos_variam is False


def test_html_do_card_mostra_a_partir_de_e_codigos_com_preco(conn):
    card = _abracadeira(conn)
    html = templates.env.get_template("_card_produto.html").render(p=card)
    assert "a partir de" in html
    assert "R$ 13,00" in html
    assert "008089 — R$ 14,00 · 008096 — R$ 13,00" in html
    assert 'data-precos="008089=14.0|008096=13.0"' in html


def test_texto_pedido_lista_codigos_com_preco_quando_varia(conn):
    card = _abracadeira(conn)
    assert texto_pedido(card) == (
        "Olá! Quero consultar a peça: ABRACADEIRA 2.1/4 (cód. 008089 — R$ 14,00; 008096 — R$ 13,00)"
    )


def test_item_estatico_produz_v_so_quando_varia(conn):
    card_varia = _abracadeira(conn)
    item_varia = _item(card_varia, "", {"Motor": 0})
    assert "p" not in item_varia
    assert item_varia["v"] == [14.0, 13.0]

    card_igual = Produto(
        id=1, codigo="009001", descricao="PORCA", categoria="Motor",
        preco=14.0, codigos=("009001", "009002"), precos=(14.0, 14.0),
    )
    item_igual = _item(card_igual, "", {"Motor": 0})
    assert item_igual["p"] == 14.0
    assert "v" not in item_igual

    card_sem = Produto(
        id=2, codigo="009003", descricao="ARRUELA", categoria="Motor",
        preco=None, codigos=("009003", "009004"), precos=(None, None),
    )
    item_sem = _item(card_sem, "", {"Motor": 0})
    assert "p" not in item_sem and "v" not in item_sem


def test_formatacao_reais_com_separador_de_milhar():
    assert reais(1234.56) == "R$ 1.234,56"
    assert reais(13) == "R$ 13,00"
    assert reais(1000000.5) == "R$ 1.000.000,50"


def test_texto_pedido_preco_unico_formatado():
    card = Produto(
        id=1, codigo="009001", descricao="PORCA", categoria="Motor",
        preco=1234.56, codigos=("009001", "009002"), precos=(1234.56, 1234.56),
    )
    assert texto_pedido(card) == "Olá! Quero consultar a peça: PORCA (cód. 009001, 009002) — R$ 1.234,56"


def test_variacao_com_codigo_sem_preco(conn):
    _abracadeira(conn)
    upsert_produto(conn, Produto(id=0, codigo="008099", descricao="ABRACADEIRA 2.1/4", categoria="Motor", preco=None))
    conn.commit()
    (card,), _ = listar_produtos(conn, busca="ABRACADEIRA")
    assert card.codigos == ("008089", "008096", "008099")
    assert card.precos == (14.0, 13.0, None)
    assert card.preco is None
    assert card.preco_min == 13.0
    assert card.precos_variam is True

    html = templates.env.get_template("_card_produto.html").render(p=card)
    assert "008089 — R$ 14,00 · 008096 — R$ 13,00 · 008099" in html
    assert 'data-precos="008089=14.0|008096=13.0|008099="' in html
    assert texto_pedido(card) == (
        "Olá! Quero consultar a peça: ABRACADEIRA 2.1/4 (cód. 008089 — R$ 14,00; 008096 — R$ 13,00; 008099)"
    )
    assert _item(card, "", {"Motor": 0})["v"] == [14.0, 13.0, None]


def test_card_com_um_preco_e_um_codigo_sem_preco_mostra_a_partir_de(conn):
    upsert_produto(conn, Produto(id=0, codigo="007001", descricao="RETENTOR RODA TRAS", categoria="Motor", preco=None))
    upsert_produto(conn, Produto(id=0, codigo="007002", descricao="RETENTOR RODA TRAS", categoria="Motor", preco=22.5))
    conn.commit()
    (card,), _ = listar_produtos(conn, busca="RETENTOR RODA TRAS")
    assert card.preco is None and card.precos == (None, 22.5)
    assert card.precos_variam is True and card.preco_min == 22.5
    assert _item(card, "", {"Motor": 0})["v"] == [None, 22.5]
    assert texto_pedido(card).endswith("(cód. 007001; 007002 — R$ 22,50)")
