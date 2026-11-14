#!/usr/bin/env python3
"""Export catalog to static JSON for Netlify hosting."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def exportar_catalogo(db_path: str, output_path: str) -> None:
    """Export active products to JSON."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Get active products grouped by description
    query = """
    SELECT
        MIN(p.id) as id,
        p.descricao,
        p.categoria,
        p.tipo,
        p.marca,
        p.imagem_url,
        p.preco,
        GROUP_CONCAT(p.codigo, '|') as codigos
    FROM produtos p
    WHERE p.ativo = 1
    GROUP BY p.descricao
    ORDER BY
        (p.imagem_url <> '') DESC,
        p.descricao
    """

    rows = c.execute(query).fetchall()
    produtos = []

    for row in rows:
        codigos = [c.strip() for c in (row["codigos"] or "").split("|") if c.strip()]

        produtos.append({
            "id": row["id"],
            "descricao": row["descricao"],
            "categoria": row["categoria"],
            "tipo": row["tipo"],
            "marca": row["marca"] or None,
            "imagem": row["imagem_url"] or None,
            "preco": row["preco"],
            "codigos": codigos,
        })

    conn.close()

    # Write JSON
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w", encoding="utf-8") as f:
        json.dump(
            {
                "versao": "1.0",
                "total_produtos": len(produtos),
                "produtos": produtos,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"✅ Exported {len(produtos)} products to {output}")


if __name__ == "__main__":
    import sys

    db = sys.argv[1] if len(sys.argv) > 1 else "catalogo/data/catalogo.db"
    out = sys.argv[2] if len(sys.argv) > 2 else "catalogo/static/catalogo.json"

    exportar_catalogo(db, out)
