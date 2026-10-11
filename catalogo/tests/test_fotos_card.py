from fastapi.testclient import TestClient

from catalogo.db import conectar, criar_schema, upsert_produto
from catalogo.models import Produto


def test_card_mostra_foto_com_selo_ou_icone(tmp_path, monkeypatch):
    db = tmp_path / "app.db"
    conn = conectar(str(db))
    criar_schema(conn)
    upsert_produto(conn, Produto(id=0, codigo="000001", descricao="PASTILHA FREIO DT AGILE",
                                 categoria="Freios", imagem_url="/fotos/abc.webp"))
    upsert_produto(conn, Produto(id=0, codigo="000002", descricao="AMORT DT GOL G5", categoria="Suspensão e Direção"))
    conn.commit()
    conn.close()
    monkeypatch.setenv("DB_PATH", str(db))
    from catalogo.app import app

    c = TestClient(app)
    pagina = c.get("/").text
    assert 'src="/fotos/abc.webp"' in pagina and 'loading="lazy"' in pagina
    assert pagina.count("Imagem ilustrativa") == 1
    assert pagina.count('class="card-ico"') == 1
    assert c.get("/fotos/nao-existe.webp").status_code == 404
