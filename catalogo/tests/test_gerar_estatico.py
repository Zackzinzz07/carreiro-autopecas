"""Site estático para o Netlify: catálogo em /catalogo/, lista em JSON e só as fotos que o site usa."""
import json

import pytest

from catalogo.db import conectar, criar_schema, upsert_produto
from catalogo.models import Produto
from catalogo.scripts.gerar_estatico import gerar

COXIM = "COXIM INF CAMBIO UNO/FIORINO 1.0 1.4 01/"
FILTRO = "FILTRO OLEO GOL/PARATI AP 1.6"
MALICIOSO = 'PASTILHA <script>alert(1)</script> "X"'


@pytest.fixture
def ambiente(tmp_path):
    db = tmp_path / "catalogo.db"
    conn = conectar(str(db))
    criar_schema(conn)
    for codigo, desc, foto in [
        ("005735", COXIM, "/fotos/coxim.webp"), ("000136", COXIM, "/fotos/coxim.webp"),
        ("000003", FILTRO, "/fotos/sumiu.webp"),   # arquivo apagado: o card sai sem foto
        ("000009", MALICIOSO, ""),
    ]:
        upsert_produto(conn, Produto(id=0, codigo=codigo, descricao=desc, categoria="Motor", imagem_url=foto))
    conn.commit()
    conn.close()

    fotos = tmp_path / "fotos"
    fotos.mkdir()
    (fotos / "coxim.webp").write_bytes(b"webp-coxim")
    (fotos / "orfa.webp").write_bytes(b"nao-usada")

    landing = tmp_path / "site"
    (landing / "assets").mkdir(parents=True)
    (landing / "index.html").write_text("<html>landing</html>", encoding="utf-8")
    (landing / "assets" / "hero.mp4").write_bytes(b"video")

    saida = tmp_path / "publico"
    (saida / "fotos").mkdir(parents=True)
    (saida / "fotos" / "antiga.webp").write_bytes(b"de-um-deploy-anterior")
    return db, fotos, landing, saida


def _gerar(ambiente, com_landing=True):
    db, fotos, landing, saida = ambiente
    gerar(db_path=str(db), fotos_dir=fotos, saida=saida, landing=landing if com_landing else None)
    return saida


def _produtos(saida):
    return json.loads((saida / "catalogo" / "produtos.json").read_text(encoding="utf-8"))


def test_um_card_por_descricao_com_todos_os_codigos(ambiente):
    itens = {p["d"]: p for p in _produtos(_gerar(ambiente))["produtos"]}
    assert set(itens) == {COXIM, FILTRO, MALICIOSO}
    assert itens[COXIM]["k"] == ["000136", "005735"]


def test_so_copia_as_fotos_usadas_e_apaga_as_que_sobraram(ambiente):
    saida = _gerar(ambiente)
    assert sorted(f.name for f in (saida / "fotos").iterdir()) == ["coxim.webp"]
    itens = {p["d"]: p for p in _produtos(saida)["produtos"]}
    assert itens[COXIM]["f"] == "coxim"
    assert "f" not in itens[FILTRO]   # foto no banco, arquivo ausente: não aponta para um 404


def test_pagina_do_catalogo_escapa_texto_da_planilha(ambiente):
    html = (_gerar(ambiente) / "catalogo" / "index.html").read_text(encoding="utf-8")
    assert "<script>alert(1)" not in html
    assert "&lt;script&gt;alert(1)" in html
    assert 'src="/static/catalogo-estatico.js"' in html


def test_copia_estilos_scripts_e_landing(ambiente):
    saida = _gerar(ambiente)
    for nome in ("catalogo.css", "catalogo.js", "catalogo-estatico.js", "logo.png", "fundo-motor.webp"):
        assert (saida / "static" / nome).is_file(), nome
    assert (saida / "index.html").read_text(encoding="utf-8") == "<html>landing</html>"
    assert (saida / "assets" / "hero.mp4").is_file()


def test_sem_landing_nao_cria_raiz(ambiente):
    saida = _gerar(ambiente, com_landing=False)
    assert not (saida / "index.html").exists()
    assert (saida / "catalogo" / "index.html").is_file()
