import openpyxl
import pytest
from fastapi.testclient import TestClient

from catalogo.sync import importar
from catalogo.sync.planilha import ler_planilha


@pytest.fixture
def xlsx(tmp_path):
    caminho = tmp_path / "estoque.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Código", "Descrição", "Cód Barras"])
    ws.append(["000001", "AMORT DT GOL G5 08/", "000001"])          # barras == código: sem referência
    ws.append(["000002", "FILTRO OLEO GOL", "7891799419370"])       # EAN
    ws.append(["000003", "PASTILHA FREIO DT UNO", "000777"])        # código alternativo
    ws.append(["000004", "INATIVO", "000004"])                      # ignorado
    ws.append(["000005", "COXIM CAMBIO S10 INATIVO", "000005"])     # ignorado
    ws.append([None, None, None])                                   # linha em branco
    ws.append(["000006", "", "000006"])                             # inválida
    wb.save(caminho)
    return caminho


def test_leitura_classifica_e_separa_ean_de_referencia(xlsx):
    r = ler_planilha(xlsx)
    por = {p.codigo: p for p in r.produtos}
    assert set(por) == {"000001", "000002", "000003"}
    assert (por["000001"].referencia, por["000001"].ean) == ("", "")
    assert por["000002"].ean == "7891799419370" and por["000002"].referencia == ""
    assert por["000003"].referencia == "000777" and por["000003"].ean == ""
    assert por["000003"].categoria == "Freios" and por["000003"].preco is None
    assert len(r.inativos) == 2 and len(r.invalidos) == 1


def test_planilha_sem_coluna_obrigatoria_falha_claro(tmp_path):
    caminho = tmp_path / "ruim.xlsx"
    wb = openpyxl.Workbook()
    wb.active.append(["Codigo", "Nome"])
    wb.save(caminho)
    with pytest.raises(ValueError, match="DESCRICAO"):
        ler_planilha(caminho)


def test_dry_run_nao_grava_e_gravar_grava(xlsx, tmp_path, capsys):
    db = tmp_path / "t.db"
    assert importar.main(["--arquivo", str(xlsx), "--db", str(db)]) == 0
    assert "DRY-RUN" in capsys.readouterr().out
    from catalogo.db import conectar
    conn = conectar(str(db))
    assert conn.execute("SELECT count(*) FROM produtos").fetchone()[0] == 0
    assert importar.main(["--arquivo", str(xlsx), "--db", str(db), "--gravar"]) == 0
    assert conn.execute("SELECT count(*) FROM produtos WHERE ativo = 1").fetchone()[0] == 3
    conn.close()


def test_reimportar_desativa_quem_sumiu(xlsx, tmp_path):
    db = tmp_path / "t.db"
    importar.main(["--arquivo", str(xlsx), "--db", str(db), "--gravar"])
    wb = openpyxl.load_workbook(xlsx)
    wb.active.delete_rows(2)  # remove 000001
    wb.save(xlsx)
    importar.main(["--arquivo", str(xlsx), "--db", str(db), "--gravar"])
    from catalogo.db import conectar
    conn = conectar(str(db))
    ativo = {r["codigo"]: r["ativo"] for r in conn.execute("SELECT codigo, ativo FROM produtos")}
    conn.close()
    assert ativo["000001"] == 0 and ativo["000002"] == 1


def test_rotas(xlsx, tmp_path, monkeypatch):
    db = tmp_path / "app.db"
    importar.main(["--arquivo", str(xlsx), "--db", str(db), "--gravar"])
    monkeypatch.setenv("DB_PATH", str(db))
    from catalogo.app import app
    c = TestClient(app)
    assert c.get("/saude").json() == {"status": "ok"}
    home = c.get("/")
    assert home.status_code == 200 and home.text.count('class="card"') == 3
    assert "Consulte o preço" in home.text and "wa.me/5588997270713" in home.text  # fallback = matriz
    assert c.get("/?categoria=freios").text.count('class="card"') == 1
    assert c.get("/?busca=amortecedor").text.count('class="card"') == 1
    assert "Nenhuma peça encontrada" in c.get("/?busca=zzzz").text
    assert c.get("/?pagina=99").status_code == 200
    assert c.get("/?pagina=0").status_code == 422
    assert c.get('/?busca=%22%20OR%20*%20%3B--').status_code == 200
