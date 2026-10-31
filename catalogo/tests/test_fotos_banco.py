import sqlite3

import pytest

from catalogo.db import conectar, criar_schema, upsert_produto
from catalogo.fotos import banco
from catalogo.fotos.normalizar import normalizar
from catalogo.models import Produto

Q = "2026-10-05T12:00:00"
PRODUTOS = [
    ("1", "PASTILHA FREIO DT AGILE/CELTA"),
    ("2", "PASTILHA FREIO DT AGILE/CELTA/PRISMA"),
    ("3", "PASTILHA FREIO DT UNO 10/"),
    ("4", "OLEO MOTOR 15W40 PETRONAS SYNTIUM 800 SE"),
]


def _carregar(conn):
    for codigo, desc in PRODUTOS:
        upsert_produto(conn, Produto(id=0, codigo=codigo, descricao=desc, categoria="Freios"))
    conn.commit()


@pytest.fixture
def conn():
    c = conectar(":memory:")
    criar_schema(c)
    _carregar(c)
    banco.criar_schema_fotos(c)
    banco.sincronizar_grupos(c, Q)
    yield c
    c.close()


def _grupo(conn, codigo):
    return conn.execute("SELECT foto_grupo FROM produtos WHERE codigo = ?", (codigo,)).fetchone()[0]


def _imagem(conn, codigo):
    return conn.execute("SELECT imagem_url FROM produtos WHERE codigo = ?", (codigo,)).fetchone()[0]


def _candidata(conn, dir_c, chave, conteudo):
    dir_c.mkdir(exist_ok=True)
    nome = f"c{len(list(dir_c.iterdir()))}.webp"
    (dir_c / nome).write_bytes(conteudo)
    [cid] = banco.registrar_candidatas(conn, chave, [banco.NovaCandidata(
        arquivo=nome, url="https://loja/x", titulo="Pastilha Freio", dominio="loja", clip_rank=1,
        clip_top="brake pad", ocr_texto="", pontuacao=50, aprovada_auto=True, motivo="")])
    return cid


def test_schema_idempotente_cria_colunas(conn):
    banco.criar_schema_fotos(conn)
    colunas = {r[1] for r in conn.execute("PRAGMA table_info(produtos)")}
    assert {"foto_grupo", "foto_tipo"} <= colunas


def test_sincronizar_agrupa_mesma_peca_e_carro(conn):
    assert _grupo(conn, "1") == _grupo(conn, "2") == "pastilha freio dianteiro|agile|||"
    assert _grupo(conn, "3") != _grupo(conn, "1")
    g = conn.execute("SELECT * FROM foto_grupos WHERE chave = ?", (_grupo(conn, "1"),)).fetchone()
    assert g["n_produtos"] == 2 and g["status"] == "pendente" and g["consulta"] == "pastilha freio dianteiro agile"
    tipos = {r["codigo"]: r["foto_tipo"] for r in conn.execute("SELECT codigo, foto_tipo FROM produtos")}
    assert tipos["1"] == "pastilha freio" and tipos["4"] == ""  # óleo tem marca: nunca usa foto de tipo
    assert banco.sincronizar_grupos(conn, Q) == 0


def test_aprovar_propaga_para_o_grupo_inteiro(conn, tmp_path):
    chave = _grupo(conn, "1")
    cid = _candidata(conn, tmp_path / "cand", chave, b"foto-agile")
    nome = banco.aprovar(conn, chave, cid, origem="agy", quando=Q,
                         dir_candidatas=tmp_path / "cand", dir_fotos=tmp_path / "fotos")
    assert (tmp_path / "fotos" / nome).read_bytes() == b"foto-agile"
    assert _imagem(conn, "1") == _imagem(conn, "2") == f"/fotos/{nome}"
    assert _imagem(conn, "3") == ""


def test_foto_de_tipo_cobre_quem_nao_tem_foto_propria_e_nunca_produto_com_marca(conn, tmp_path):
    tipo = banco.garantir_grupo_tipo(conn, normalizar("PASTILHA FREIO DT UNO 10/"), Q)
    assert tipo == "TIPO:pastilha freio"
    assert banco.garantir_grupo_tipo(conn, normalizar(PRODUTOS[3][1]), Q) is None
    cid = _candidata(conn, tmp_path / "cand", tipo, b"foto-generica")
    generica = banco.aprovar(conn, tipo, cid, origem="agy", quando=Q,
                             dir_candidatas=tmp_path / "cand", dir_fotos=tmp_path / "fotos")
    assert _imagem(conn, "3") == _imagem(conn, "1") == f"/fotos/{generica}"
    assert _imagem(conn, "4") == ""
    chave = _grupo(conn, "1")
    cid = _candidata(conn, tmp_path / "cand", chave, b"foto-agile")
    propria = banco.aprovar(conn, chave, cid, origem="agy", quando=Q,
                            dir_candidatas=tmp_path / "cand", dir_fotos=tmp_path / "fotos")
    assert _imagem(conn, "1") == f"/fotos/{propria}" and _imagem(conn, "3") == f"/fotos/{generica}"


def test_rejeitar_remove_a_foto(conn, tmp_path):
    chave = _grupo(conn, "1")
    cid = _candidata(conn, tmp_path / "cand", chave, b"x")
    banco.aprovar(conn, chave, cid, origem="agy", quando=Q, dir_candidatas=tmp_path / "cand", dir_fotos=tmp_path / "f")
    banco.rejeitar_grupo(conn, chave, origem="auditoria:agy", quando=Q)
    assert _imagem(conn, "1") == ""
    assert conn.execute("SELECT status FROM foto_grupos WHERE chave = ?", (chave,)).fetchone()[0] == "rejeitada"


def test_reimportar_planilha_preserva_foto_aprovada(conn, tmp_path):  # Review Focus 5
    chave = _grupo(conn, "1")
    cid = _candidata(conn, tmp_path / "cand", chave, b"x")
    banco.aprovar(conn, chave, cid, origem="agy", quando=Q, dir_candidatas=tmp_path / "cand", dir_fotos=tmp_path / "f")
    antes = _imagem(conn, "1")
    _carregar(conn)  # reimportação: upsert com imagem_url vazio
    banco.sincronizar_grupos(conn, Q)
    assert _imagem(conn, "1") == antes != ""


def test_candidata_de_outro_grupo_nao_aprova(conn, tmp_path):
    cid = _candidata(conn, tmp_path / "cand", _grupo(conn, "1"), b"x")
    with pytest.raises(ValueError):
        banco.aprovar(conn, _grupo(conn, "3"), cid, origem="agy", quando=Q,
                      dir_candidatas=tmp_path / "cand", dir_fotos=tmp_path / "f")


def test_revisao_nova_torna_a_antiga_obsoleta_e_decisao_registra(conn):
    chave = _grupo(conn, "1")
    r1 = banco.registrar_revisao(conn, chave, "revisao", Q)
    r2 = banco.registrar_revisao(conn, chave, "revisao", Q)
    status = {r["id"]: r["status"] for r in conn.execute("SELECT id, status FROM foto_revisao")}
    assert status == {r1: "obsoleta", r2: "pendente"}
    banco.decidir_revisao(conn, r2, "rejeitada", candidata_id=None, por="agy", quando=Q)
    r = conn.execute("SELECT * FROM foto_revisao WHERE id = ?", (r2,)).fetchone()
    assert (r["status"], r["decidido_por"], r["decidido_em"]) == ("rejeitada", "agy", Q)


def test_resetar_volta_para_pendente_e_limpa(conn, tmp_path):
    chave = _grupo(conn, "1")
    cid = _candidata(conn, tmp_path / "cand", chave, b"x")
    banco.aprovar(conn, chave, cid, origem="agy", quando=Q, dir_candidatas=tmp_path / "cand", dir_fotos=tmp_path / "f")
    banco.registrar_revisao(conn, chave, "auditoria", Q)
    assert banco.resetar_grupos(conn, [chave], tmp_path / "cand") == 1
    g = conn.execute("SELECT * FROM foto_grupos WHERE chave = ?", (chave,)).fetchone()
    assert (g["status"], g["arquivo"]) == ("pendente", "") and _imagem(conn, "1") == ""
    assert conn.execute("SELECT count(*) FROM foto_revisao WHERE status = 'pendente'").fetchone()[0] == 0
    assert list((tmp_path / "cand").iterdir()) == []


def test_grupos_pendentes_ordem_e_filtro(conn):
    fila = banco.grupos_pendentes(conn, 10)
    assert fila[0]["chave"] == _grupo(conn, "1")  # 2 produtos: vem primeiro
    assert [r["chave"] for r in banco.grupos_pendentes(conn, 10, [_grupo(conn, "3")])] == [_grupo(conn, "3")]
    assert banco.grupos_pendentes(conn, 10, []) == []


def test_backup_gera_copia_legivel(tmp_path):
    db = tmp_path / "c.db"
    c = conectar(str(db))
    criar_schema(c)
    _carregar(c)
    c.close()
    copia = banco.backup(db, tmp_path / "bk")
    assert sqlite3.connect(copia).execute("SELECT count(*) FROM produtos").fetchone()[0] == 4


def test_relatorio(conn):
    r = banco.relatorio(conn)
    assert r["grupos"] == {"pendente": 3} and r["produtos_ativos"] == 4 and r["produtos_com_foto"] == 0


def test_grupo_que_ficou_sem_produto_some_e_a_foto_antiga_nao_fica_no_produto(conn, tmp_path):
    """Descrição mudou (ou a chave mudou de formato): o produto vai para outro grupo e não leva a foto do antigo."""
    chave_velha = _grupo(conn, "3")                       # só o produto 3 está neste grupo
    cid = _candidata(conn, tmp_path / "cand", chave_velha, b"foto-uno")
    banco.aprovar(conn, chave_velha, cid, origem="agy", quando=Q, dir_candidatas=tmp_path / "cand", dir_fotos=tmp_path / "f")
    pendente = banco.registrar_revisao(conn, chave_velha, "auditoria", Q)
    assert _imagem(conn, "3") != ""
    upsert_produto(conn, Produto(id=0, codigo="3", descricao="PASTILHA FREIO DT UNO 15/", categoria="Freios"))
    conn.commit()
    banco.sincronizar_grupos(conn, Q, dir_candidatas=tmp_path / "cand")
    assert _grupo(conn, "3") != chave_velha and _imagem(conn, "3") == ""
    assert conn.execute("SELECT count(*) FROM foto_grupos WHERE chave = ?", (chave_velha,)).fetchone()[0] == 0
    assert conn.execute("SELECT status FROM foto_revisao WHERE id = ?", (pendente,)).fetchone()[0] == "obsoleta"
    assert conn.execute("SELECT count(*) FROM foto_candidatas WHERE chave = ?", (chave_velha,)).fetchone()[0] == 0


def test_referencia_que_nao_gera_mais_a_chave_volta_para_pendente(conn, tmp_path):
    """A regra da chave mudou: o produto conferido foi para outro grupo, mas o grupo antigo sobreviveu com outros
    produtos. A foto foi conferida contra a referência antiga (mangote Uno 85 com foto de Novo Uno, piloto 3)."""
    chave = _grupo(conn, "1")
    cid = _candidata(conn, tmp_path / "cand", chave, b"foto")
    banco.aprovar(conn, chave, cid, origem="agy", quando=Q, dir_candidatas=tmp_path / "cand", dir_fotos=tmp_path / "f")
    auditoria = banco.registrar_revisao(conn, chave, "auditoria", Q)
    # referência gravada pela regra antiga; pela regra atual o motor separa: ela não gera mais esta chave
    conn.execute("UPDATE foto_grupos SET descricao_ref = ? WHERE chave = ?", ("PASTILHA FREIO DT AGILE/CELTA 1.4 16V", chave))
    conn.commit()
    banco.sincronizar_grupos(conn, Q, dir_candidatas=tmp_path / "cand")
    g = conn.execute("SELECT * FROM foto_grupos WHERE chave = ?", (chave,)).fetchone()
    assert normalizar(g["descricao_ref"]).texto == chave
    assert (g["status"], g["arquivo"]) == ("pendente", "") and _imagem(conn, "1") == ""
    assert conn.execute("SELECT status FROM foto_revisao WHERE id = ?", (auditoria,)).fetchone()[0] == "obsoleta"
    assert conn.execute("SELECT count(*) FROM foto_candidatas WHERE chave = ?", (chave,)).fetchone()[0] == 0


def test_aprovacao_automatica_so_vai_ao_catalogo_depois_da_auditoria(conn, tmp_path):   # decisão de 2026-10-30
    chave = _grupo(conn, "1")
    cid = _candidata(conn, tmp_path / "cand", chave, b"foto-agile")
    nome = banco.aprovar(conn, chave, cid, origem="auto", quando=Q,
                         dir_candidatas=tmp_path / "cand", dir_fotos=tmp_path / "fotos")
    assert _imagem(conn, "1") == _imagem(conn, "2") == ""
    banco.confirmar_auditoria(conn, chave, por="agy", quando=Q)
    assert _imagem(conn, "1") == _imagem(conn, "2") == f"/fotos/{nome}"
    assert conn.execute("SELECT origem FROM foto_grupos WHERE chave = ?", (chave,)).fetchone()[0] == "auditoria:agy"


def test_sincronizar_aplica_a_regra_de_publicacao_mesmo_sem_mudanca_nos_grupos(conn):
    """Foto publicada por código antigo (ou à mão) sai do catálogo no próximo lote, sem esperar outra mudança."""
    conn.execute("UPDATE produtos SET imagem_url = '/fotos/velha.webp' WHERE codigo = '1'")
    conn.commit()
    banco.sincronizar_grupos(conn, Q)
    assert _imagem(conn, "1") == ""
