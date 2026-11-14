"""Mesma descrição com códigos diferentes (a planilha repete peças): um card só, com todos os códigos."""
import pytest
from fastapi.testclient import TestClient

from catalogo.categorias import categoria_para_descricao, tipo_da_peca
from catalogo.db import conectar, contar_por_categoria, contar_por_tipo, criar_schema, listar_produtos, upsert_produto
from catalogo.models import Produto
from catalogo.whatsapp import texto_pedido

COXIM = "COXIM INF CAMBIO UNO/FIORINO 1.0 1.4 01/"
FILTRO = "FILTRO OLEO GOL/PARATI AP 1.6"
LINHAS = [("005735", COXIM, "000136"), ("000136", COXIM, "005735"), ("008527", COXIM, ""), ("000003", FILTRO, "")]


def _carregar(conn):
    for codigo, desc, ref in LINHAS:
        upsert_produto(conn, Produto(id=0, codigo=codigo, descricao=desc, categoria=categoria_para_descricao(desc),
                                     tipo=tipo_da_peca(desc), referencia=ref, imagem_url="/fotos/coxim.webp" if desc == COXIM else ""))
    conn.commit()


@pytest.fixture
def conn():
    c = conectar(":memory:")
    criar_schema(c)
    _carregar(c)
    yield c
    c.close()


def _por_descricao(produtos):
    return {p.descricao: p for p in produtos}


def test_codigos_repetidos_viram_um_card_com_todos_os_codigos(conn):
    produtos, total = listar_produtos(conn)
    assert total == 2 and len(produtos) == 2
    card = _por_descricao(produtos)
    assert card[COXIM].codigos == ("000136", "005735", "008527")
    assert card[COXIM].imagem_url == "/fotos/coxim.webp"
    assert card[FILTRO].codigos == ("000003",)


def test_busca_por_qualquer_codigo_acha_o_card_inteiro(conn):
    for busca in ("008527", "005735", "000136"):
        produtos, total = listar_produtos(conn, busca=busca)
        assert total == 1 and produtos[0].codigos == ("000136", "005735", "008527")
    produtos, total = listar_produtos(conn, busca="coxim")           # busca por texto também não duplica
    assert total == 1 and len(produtos) == 1


def test_contagens_e_paginacao_contam_cards(conn):
    assert sum(contar_por_categoria(conn).values()) == 2
    assert sum(contar_por_categoria(conn, "coxim").values()) == 1
    primeira, total = listar_produtos(conn, por_pagina=1, pagina=1)
    segunda, _ = listar_produtos(conn, por_pagina=1, pagina=2)
    assert total == 2 and len(primeira) == len(segunda) == 1 and primeira[0].descricao != segunda[0].descricao
    assert contar_por_tipo(conn, categoria_para_descricao(COXIM)) == []   # menos de 3 cards do tipo: não vira filtro


def test_codigo_inativo_sai_do_card_e_card_sem_codigo_ativo_some(conn):
    conn.execute("UPDATE produtos SET ativo = 0 WHERE codigo = '008527'")
    produtos, total = listar_produtos(conn, busca="coxim")
    assert total == 1 and produtos[0].codigos == ("000136", "005735")
    conn.execute("UPDATE produtos SET ativo = 0 WHERE descricao = ?", (COXIM,))
    assert listar_produtos(conn, busca="coxim") == ([], 0)


def test_pedido_no_whatsapp_cita_todos_os_codigos(conn):
    card = _por_descricao(listar_produtos(conn)[0])[COXIM]
    texto = texto_pedido(card)
    assert texto.count(COXIM) == 1 and all(c in texto for c in ("000136", "005735", "008527"))
    assert texto_pedido(Produto(id=1, codigo="008087", descricao="ABRACADEIRA", categoria="Variados")) == \
        "Olá! Quero consultar a peça: ABRACADEIRA (cód. 008087)"


def test_pagina_mostra_um_card_so_com_todos_os_codigos(tmp_path, monkeypatch):
    db = tmp_path / "rep.db"
    c = conectar(str(db))
    criar_schema(c)
    _carregar(c)
    c.close()
    monkeypatch.setenv("DB_PATH", str(db))
    from catalogo.app import app
    home = TestClient(app).get("/")
    assert home.status_code == 200 and home.text.count('class="card"') == 2
    assert all(cod in home.text for cod in ("000136", "005735", "008527"))
    assert "<strong>2</strong> peças" in home.text


def _dois_codigos(c, a, b):
    for cod, (marca, ean, preco) in zip(("A1", "B2"), (a, b)):
        upsert_produto(c, Produto(id=0, codigo=cod, descricao="AMORT DT GOL", categoria="Suspensão e Direção",
                                  marca=marca, ean=ean, preco=preco))
    c.commit()


def test_card_nao_mistura_marca_ean_e_preco_de_codigos_diferentes():
    c = conectar(":memory:")
    criar_schema(c)
    _dois_codigos(c, ("AXIOS", "11111111", 10.0), ("SAMPEL", "99999999", 50.0))
    for busca in (None, "A1"):                                   # buscar por um código não pode mudar o que o card mostra
        card = listar_produtos(c, busca=busca)[0][0]
        assert card.codigos == ("A1", "B2")
        assert (card.marca, card.ean, card.preco) == ("", "", None)


def test_card_mostra_preco_e_marca_quando_todos_os_codigos_concordam():
    c = conectar(":memory:")
    criar_schema(c)
    _dois_codigos(c, ("AXIOS", "", 10.0), ("AXIOS", "", 10.0))
    card = listar_produtos(c)[0][0]
    assert (card.marca, card.preco) == ("AXIOS", 10.0)


def test_um_codigo_sem_preco_esconde_o_preco_do_card():
    c = conectar(":memory:")
    criar_schema(c)
    _dois_codigos(c, ("", "", 10.0), ("", "", None))
    assert listar_produtos(c)[0][0].preco is None
