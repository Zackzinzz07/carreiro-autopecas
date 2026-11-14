"""Listagem: cards com foto primeiro; dentro do grupo, alfabética (sem busca) ou relevância (com busca)."""
import pytest

from catalogo.db import conectar, criar_schema, listar_produtos, upsert_produto
from catalogo.models import Produto

FOTO = "/fotos/x.webp"
# (codigo, descricao, imagem)
LINHAS = [
    ("1", "AMORTECEDOR A", ""), ("2", "AMORTECEDOR B", FOTO), ("3", "AMORTECEDOR C", ""),
    ("4", "AMORTECEDOR D", FOTO),
    # repetida: só uma das linhas tem foto -> o card inteiro conta como com foto
    ("5", "AMORTECEDOR E", ""), ("6", "AMORTECEDOR E", FOTO),
    ("7", "BUCHA Z", ""), ("8", "BUCHA Y", FOTO),
]


@pytest.fixture
def conn():
    c = conectar(":memory:")
    criar_schema(c)
    for cod, desc, img in LINHAS:
        upsert_produto(c, Produto(id=0, codigo=cod, descricao=desc, categoria="Suspensão e Direção", imagem_url=img))
    c.commit()
    yield c
    c.close()


def descs(conn, **kw):
    return [p.descricao for p in listar_produtos(conn, **kw)[0]]


def test_sem_busca_fotos_primeiro_e_alfabetico_em_cada_grupo(conn):
    assert descs(conn) == ["AMORTECEDOR B", "AMORTECEDOR D", "AMORTECEDOR E", "BUCHA Y",
                           "AMORTECEDOR A", "AMORTECEDOR C", "BUCHA Z"]


def test_com_busca_fotos_primeiro_mantendo_ordem_do_grupo(conn):
    r = descs(conn, busca="amortecedor")
    assert r[:3] == ["AMORTECEDOR B", "AMORTECEDOR D", "AMORTECEDOR E"]
    assert sorted(r[3:]) == ["AMORTECEDOR A", "AMORTECEDOR C"] and len(r) == 5


def test_paginacao_estavel_sem_repetir_nem_pular(conn):
    for busca in (None, "amortecedor"):
        todos = descs(conn, busca=busca, por_pagina=100)
        paginas = []
        for pg in (1, 2, 3, 4):
            paginas += descs(conn, busca=busca, pagina=pg, por_pagina=2)
        assert paginas == todos and len(set(paginas)) == len(paginas)


def test_total_nao_muda(conn):
    assert listar_produtos(conn)[1] == 7
    assert listar_produtos(conn, busca="amortecedor")[1] == 5
