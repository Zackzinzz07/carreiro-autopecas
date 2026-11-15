"""Gera o site estático do Netlify em publico/: catálogo em /catalogo/, lista em JSON e só as fotos usadas.

O Netlify não tem o banco nem as fotos (ficam fora do git), então o catálogo é gerado aqui e a pasta
publico/ vai para o git. A landing (index.html e assets/ da raiz) é copiada para publico/ pelo próprio
Netlify no deploy (netlify.toml); aqui ela só é copiada para a prévia local.

Uso:
    catalogo/.venv-fotos/bin/python -m catalogo.scripts.gerar_estatico
    cd publico && python3 -m http.server 8000   # prévia em http://localhost:8000
"""
from __future__ import annotations

import dataclasses
import json
import shutil
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

from catalogo.categorias import slug
from catalogo.config import BASE_DIR, get_settings
from catalogo.db import SINONIMOS, conectar, contar_por_categoria, criar_schema, listar_produtos
from catalogo.icones import icone_svg
from catalogo.lojas import LOJAS, MATRIZ
from catalogo.whatsapp import link_pedido

RAIZ = BASE_DIR.parent
SAIDA_PADRAO = RAIZ / "publico"
ESTATICOS = ("catalogo.css", "catalogo.js", "catalogo-estatico.js", "logo.png", "fundo-motor.webp")
PRIMEIRA_PAGINA = 48
_PREFIXO_FOTO = "/fotos/"


def _foto(imagem_url: str, fotos_dir: Path) -> str:
    """Nome do arquivo (sem .webp) quando a foto existe em disco; senão ''."""
    if not imagem_url.startswith(_PREFIXO_FOTO) or not imagem_url.endswith(".webp"):
        return ""
    nome = imagem_url[len(_PREFIXO_FOTO):-len(".webp")]
    if "/" in nome or not (fotos_dir / f"{nome}.webp").is_file():
        return ""
    return nome


def _item(p, foto: str, indice_categoria: dict[str, int]) -> dict:
    item = {"d": p.descricao, "c": indice_categoria[p.categoria], "k": list(p.todos_codigos)}
    for chave, valor in (("r", p.referencia), ("e", p.ean), ("m", p.marca), ("a", p.aplicacao), ("f", foto)):
        if valor:
            item[chave] = valor
    if p.preco is not None:
        item["p"] = p.preco
    return item


def _sincronizar_fotos(usadas: set[str], fotos_dir: Path, destino: Path) -> tuple[int, int]:
    destino.mkdir(parents=True, exist_ok=True)
    apagadas = 0
    for arq in destino.glob("*.webp"):
        if arq.stem not in usadas:
            arq.unlink()
            apagadas += 1
    copiadas = 0
    for nome in usadas:
        alvo = destino / f"{nome}.webp"
        if not alvo.exists():   # o nome é o hash do conteúdo: mesmo nome, mesma foto
            shutil.copy2(fotos_dir / f"{nome}.webp", alvo)
            copiadas += 1
    return copiadas, apagadas


def gerar(db_path: str, fotos_dir: Path, saida: Path, landing: Path | None = RAIZ) -> dict[str, int]:
    fotos_dir, saida = Path(fotos_dir), Path(saida)
    settings = get_settings()
    conn = conectar(db_path)
    try:
        criar_schema(conn)
        produtos, _ = listar_produtos(conn, pagina=1, por_pagina=10**7)
        por_categoria = contar_por_categoria(conn)
    finally:
        conn.close()

    categorias = list(por_categoria)
    for p in produtos:   # categoria sem contagem não deveria existir, mas não pode quebrar o índice
        if p.categoria not in por_categoria:
            categorias.append(p.categoria)
    indice = {nome: i for i, nome in enumerate(categorias)}

    itens, usadas, primeira = [], set(), []
    for p in produtos:
        foto = _foto(p.imagem_url, fotos_dir)
        if foto:
            usadas.add(foto)
        itens.append(_item(p, foto, indice))
        if len(primeira) < PRIMEIRA_PAGINA:
            primeira.append(dataclasses.replace(p, imagem_url=f"{_PREFIXO_FOTO}{foto}.webp" if foto else ""))

    (saida / "catalogo").mkdir(parents=True, exist_ok=True)
    dados = {
        "categorias": [{"nome": n, "slug": slug(n)} for n in categorias],
        "sinonimos": SINONIMOS,
        "matriz": MATRIZ.whatsapp,
        "produtos": itens,
    }
    (saida / "catalogo" / "produtos.json").write_text(
        json.dumps(dados, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    copiadas, apagadas = _sincronizar_fotos(usadas, fotos_dir, saida / "fotos")

    (saida / "static").mkdir(parents=True, exist_ok=True)
    for nome in ESTATICOS:
        shutil.copy2(BASE_DIR / "static" / nome, saida / "static" / nome)

    env = Environment(loader=FileSystemLoader(str(BASE_DIR / "templates")), autoescape=True)
    env.globals.update(icone=lambda c: Markup(icone_svg(c)), slug=slug, lojas=LOJAS, matriz=MATRIZ,
                       link_matriz=link_pedido)
    html = env.get_template("estatico.html").render(
        produtos=primeira, total=len(itens), por_categoria=por_categoria, nome_loja=settings.nome_loja)
    (saida / "catalogo" / "index.html").write_text(html, encoding="utf-8")

    if landing is not None:
        shutil.copy2(landing / "index.html", saida / "index.html")
        if (landing / "assets").is_dir():
            shutil.copytree(landing / "assets", saida / "assets", dirs_exist_ok=True)

    return {"produtos": len(itens), "com_foto": sum("f" in i for i in itens), "fotos": len(usadas),
            "copiadas": copiadas, "apagadas": apagadas}


def main() -> None:
    settings = get_settings()
    r = gerar(settings.db_path, Path(settings.fotos_dir), SAIDA_PADRAO)
    json_kb = (SAIDA_PADRAO / "catalogo" / "produtos.json").stat().st_size // 1024
    print(f"{r['produtos']} cards ({r['com_foto']} com foto) | {r['fotos']} fotos "
          f"(+{r['copiadas']} novas, -{r['apagadas']} removidas) | produtos.json {json_kb} KB")
    print(f"Pronto em {SAIDA_PADRAO}. Prévia: cd publico && python3 -m http.server 8000")


if __name__ == "__main__":
    main()
