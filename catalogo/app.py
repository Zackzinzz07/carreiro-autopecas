from __future__ import annotations

import math
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

from catalogo.categorias import CATEGORIAS, slug
from catalogo.config import get_settings
from catalogo.db import conectar, contar_por_categoria, contar_por_tipo, criar_schema, listar_produtos
from catalogo.icones import icone_svg
from catalogo.lojas import LOJAS, MATRIZ
from catalogo.whatsapp import link_pedido

BASE_DIR = Path(__file__).resolve().parent
SLUG_PARA_CATEGORIA = {slug(c): c for c in CATEGORIAS}

app = FastAPI(title="Catálogo Carreiro Auto Peças")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals.update(
    icone=lambda categoria: Markup(icone_svg(categoria)),
    slug=slug,
    lojas=LOJAS,
    matriz=MATRIZ,
    link_matriz=link_pedido,
)


def _url(**params: object) -> str:
    validos = {k: v for k, v in params.items() if v not in (None, "") and not (k == "pagina" and v == 1)}
    return "/?" + urlencode(validos) if validos else "/"


@app.get("/saude")
def saude() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    categoria: str | None = Query(None),
    tipo: str | None = Query(None),
    busca: str | None = Query(None),
    pagina: int = Query(1, ge=1),
):
    settings = get_settings()
    nome_categoria = SLUG_PARA_CATEGORIA.get(categoria or "")
    busca = (busca or "").strip()[:80]

    conn = conectar(settings.db_path)
    try:
        criar_schema(conn)
        produtos, total = listar_produtos(
            conn, categoria=nome_categoria, tipo=tipo or None, busca=busca or None,
            pagina=pagina, por_pagina=settings.por_pagina,
        )
        ultima = max(math.ceil(total / settings.por_pagina), 1)
        if pagina > ultima:  # ?pagina= além do fim: mostra a última em vez de lista vazia
            pagina = ultima
            produtos, total = listar_produtos(
                conn, categoria=nome_categoria, tipo=tipo or None, busca=busca or None,
                pagina=pagina, por_pagina=settings.por_pagina,
            )
        por_categoria = contar_por_categoria(conn, busca or None)
        tipos = contar_por_tipo(conn, nome_categoria, busca or None) if nome_categoria else []
        total_geral = conn.execute("SELECT count(*) FROM produtos WHERE ativo = 1").fetchone()[0]
    finally:
        conn.close()

    total_paginas = max(math.ceil(total / settings.por_pagina), 1)
    base = {"categoria": categoria if nome_categoria else None, "tipo": tipo, "busca": busca}
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "produtos": produtos,
            "total": total,
            "total_geral": total_geral,
            "por_categoria": por_categoria,
            "tipos": tipos,
            "categoria_atual": nome_categoria,
            "tipo_atual": tipo or "",
            "busca_atual": busca,
            "pagina": pagina,
            "total_paginas": total_paginas,
            "url_categoria": lambda s: _url(categoria=s, busca=busca),
            "url_pagina": lambda n: _url(**{**base, "pagina": n}),
            "url_limpar": _url(busca=busca),
            "nome_loja": settings.nome_loja,
            "site_url": settings.site_url,
        },
    )
