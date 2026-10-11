import pytest

pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from catalogo.db import conectar, criar_schema, upsert_produto  # noqa: E402
from catalogo.fotos import banco, revisar  # noqa: E402
from catalogo.models import Produto  # noqa: E402

Q = "2026-10-05T12:00:00"


@pytest.fixture
def estado(tmp_path):
    db = tmp_path / "c.db"
    conn = conectar(str(db))
    criar_schema(conn)
    for codigo, desc in [("1", "PASTILHA FREIO DT AGILE/CELTA"), ("2", "AMORT DT UNO 10/")]:
        upsert_produto(conn, Produto(id=0, codigo=codigo, descricao=desc, categoria="Freios"))
    conn.commit()
    banco.criar_schema_fotos(conn)
    banco.sincronizar_grupos(conn, Q)
    cand = tmp_path / "cand"
    cand.mkdir()
    rids = {}
    for codigo in ("1", "2"):
        chave = conn.execute("SELECT foto_grupo FROM produtos WHERE codigo = ?", (codigo,)).fetchone()[0]
        novas = []
        for i, cor in enumerate(("red", "blue")):
            nome = f"{codigo}_{i}.webp"
            Image.new("RGB", (400, 400), cor).save(cand / nome, "WEBP")
            novas.append(banco.NovaCandidata(nome, f"https://loja/{codigo}/{i}", f"Titulo {codigo} {i}", "loja",
                                             1, "brake pad", "", 50 - i, False, "titulo_sem_veiculo"))
        banco.registrar_candidatas(conn, chave, novas)
        banco.marcar_status(conn, chave, "revisao", Q)
        rids[codigo] = banco.registrar_revisao(conn, chave, "revisao", Q)
    yield {"db": db, "conn": conn, "cand": cand, "fotos": tmp_path / "fotos", "rids": rids}
    conn.close()


def _imagem(conn, codigo):
    return conn.execute("SELECT imagem_url FROM produtos WHERE codigo = ?", (codigo,)).fetchone()[0]


def _aplicar(e, texto):
    return revisar.aplicar(e["conn"], revisar.parse_decisoes(texto), por="agy", quando=Q,
                           dir_candidatas=e["cand"], dir_fotos=e["fotos"])


def test_parse_decisoes():
    assert revisar.parse_decisoes("12:0, 13:X") == [(12, "0"), (13, "x")]
    for ruim in ("", "12-0", "12:9x", "1:0,1:x", "abc"):
        with pytest.raises(ValueError):
            revisar.parse_decisoes(ruim)


def test_escolher_candidata_aprova_na_ordem_da_folha(estado):
    r1 = estado["rids"]["1"]
    azul = (estado["cand"] / "1_1.webp").read_bytes()  # [1] na folha = 2ª maior pontuação
    assert _aplicar(estado, f"{r1}:1")["aprovadas"] == 1
    url = _imagem(estado["conn"], "1")
    assert (estado["fotos"] / url.removeprefix("/fotos/")).read_bytes() == azul
    rev = estado["conn"].execute("SELECT * FROM foto_revisao WHERE id = ?", (r1,)).fetchone()
    assert (rev["status"], rev["decidido_por"]) == ("aprovada", "agy")
    assert banco.candidatas_de(estado["conn"], rev["chave"]) == []
    assert not (estado["cand"] / "1_0.webp").exists()  # candidatas do grupo decidido são apagadas


def test_x_rejeita_e_cria_grupo_de_tipo(estado):
    _aplicar(estado, f"{estado['rids']['2']}:x")
    tipo = estado["conn"].execute("SELECT status FROM foto_grupos WHERE chave = 'TIPO:amortecedor'").fetchone()
    assert tipo[0] == "pendente"
    assert _imagem(estado["conn"], "2") == ""


def test_erro_no_comando_nao_aplica_nada(estado):  # Review Focus 3
    r1, r2 = estado["rids"]["1"], estado["rids"]["2"]
    for texto in (f"{r1}:0,999:0", f"{r1}:0,{r2}:7"):
        with pytest.raises(ValueError):
            _aplicar(estado, texto)
    status = [r[0] for r in estado["conn"].execute("SELECT status FROM foto_revisao ORDER BY id")]
    assert status == ["pendente", "pendente"] and _imagem(estado["conn"], "1") == ""


def test_auditoria_confirma_ou_desfaz(estado):
    _aplicar(estado, f"{estado['rids']['1']}:0")
    chave = estado["conn"].execute("SELECT foto_grupo FROM produtos WHERE codigo = '1'").fetchone()[0]
    aud = banco.registrar_revisao(estado["conn"], chave, "auditoria", Q)
    with pytest.raises(ValueError):
        _aplicar(estado, f"{aud}:1")
    assert _aplicar(estado, f"{aud}:x")["desfeitas"] == 1
    assert _imagem(estado["conn"], "1") == ""


def test_gerar_folhas_png_txt_e_html(estado, tmp_path):
    arquivos = revisar.gerar(estado["conn"], tmp_path / "folhas", estado["cand"], estado["fotos"])
    nomes = sorted(p.name for p in arquivos)
    assert nomes == ["folha_001.png", "folha_001.txt", "index.html"]
    texto = (tmp_path / "folhas" / "folha_001.txt").read_text()
    assert f"R{estado['rids']['1']}" in texto and "Titulo 1 0" in texto
    assert Image.open(tmp_path / "folhas" / "folha_001.png").width == 4 * (revisar.LADO_MINIATURA + 10) + 10


def test_main_faz_backup_antes_de_decidir(estado, tmp_path, monkeypatch):
    monkeypatch.setenv("BACKUPS_DIR", str(tmp_path / "bk"))
    monkeypatch.setenv("CANDIDATAS_DIR", str(estado["cand"]))
    monkeypatch.setenv("FOTOS_DIR", str(estado["fotos"]))
    assert revisar.main(["--db", str(estado["db"]), "--decidir", "abc"]) == 2      # nem chega ao backup
    assert revisar.main(["--db", str(estado["db"]), "--decidir", "999:0"]) == 2    # backup feito, nada aplicado
    assert revisar.main(["--db", str(estado["db"]), "--decidir", f"{estado['rids']['1']}:0"]) == 0
    assert len(list((tmp_path / "bk").glob("*.db"))) == 2
