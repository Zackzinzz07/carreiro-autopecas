from catalogo.db import contar_por_categoria, listar_produtos, montar_match


def codigos(conn, **kw):
    produtos, _ = listar_produtos(conn, **kw)
    return {p.codigo for p in produtos}


def test_match_ignora_caracteres_de_sintaxe_fts():
    assert montar_match('" OR * ; --') == '("or"*)'  # só sobra o token alfanumérico, entre aspas
    assert montar_match("   ") is None and montar_match(None) is None


def test_sinonimo_amortecedor_acha_amort(conn):
    assert codigos(conn, busca="amortecedor") == {"000001", "000002"}


def test_todos_os_termos_precisam_casar(conn):
    assert codigos(conn, busca="amortecedor dianteiro gol") == {"000001"}


def test_busca_por_codigo_referencia_e_ean(conn):
    assert codigos(conn, busca="000003") == {"000003"}
    assert codigos(conn, busca="000099") == {"000002"}
    assert codigos(conn, busca="7891799419370") == {"000003"}


def test_prefixo_e_sem_acento(conn):
    assert codigos(conn, busca="pastil") == {"000004"}


def test_filtro_por_categoria_e_paginacao(conn):
    assert codigos(conn, categoria="Suspensão e Direção") == {"000001", "000002"}
    pagina2, total = listar_produtos(conn, pagina=2, por_pagina=2)
    assert total == 5 and len(pagina2) == 2


def test_contagem_por_categoria_respeita_busca_e_ordem(conn):
    assert list(contar_por_categoria(conn)) == ["Suspensão e Direção", "Freios", "Filtros", "Pneus e Rodas"]
    assert contar_por_categoria(conn, "gol") == {"Suspensão e Direção": 1, "Filtros": 1}


def test_inativo_nao_aparece(conn):
    conn.execute("UPDATE produtos SET ativo = 0 WHERE codigo = '000001'")
    assert "000001" not in codigos(conn, busca="amort")
