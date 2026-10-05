# catalogo/db.py
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from catalogo.categorias import CATEGORIAS, normalizar
from catalogo.models import Produto

_SCHEMA = """
CREATE TABLE IF NOT EXISTS produtos (
    id INTEGER PRIMARY KEY,
    codigo TEXT NOT NULL UNIQUE,
    descricao TEXT NOT NULL,
    categoria TEXT NOT NULL,
    tipo TEXT NOT NULL DEFAULT '',
    marca TEXT NOT NULL DEFAULT '',
    referencia TEXT NOT NULL DEFAULT '',
    ean TEXT NOT NULL DEFAULT '',
    aplicacao TEXT NOT NULL DEFAULT '',
    preco REAL,
    imagem_url TEXT NOT NULL DEFAULT '',
    ativo INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_produtos_categoria ON produtos(categoria, ativo);

CREATE VIRTUAL TABLE IF NOT EXISTS produtos_fts USING fts5(
    descricao, codigo, referencia, ean,
    content='produtos', content_rowid='id',
    tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER IF NOT EXISTS produtos_ai AFTER INSERT ON produtos BEGIN
    INSERT INTO produtos_fts(rowid, descricao, codigo, referencia, ean)
    VALUES (new.id, new.descricao, new.codigo, new.referencia, new.ean);
END;
CREATE TRIGGER IF NOT EXISTS produtos_ad AFTER DELETE ON produtos BEGIN
    INSERT INTO produtos_fts(produtos_fts, rowid, descricao, codigo, referencia, ean)
    VALUES ('delete', old.id, old.descricao, old.codigo, old.referencia, old.ean);
END;
CREATE TRIGGER IF NOT EXISTS produtos_au AFTER UPDATE ON produtos BEGIN
    INSERT INTO produtos_fts(produtos_fts, rowid, descricao, codigo, referencia, ean)
    VALUES ('delete', old.id, old.descricao, old.codigo, old.referencia, old.ean);
    INSERT INTO produtos_fts(rowid, descricao, codigo, referencia, ean)
    VALUES (new.id, new.descricao, new.codigo, new.referencia, new.ean);
END;
"""

# A planilha abrevia muito ("AMORT DT"). Quem digita "amortecedor dianteiro" precisa achar.
# Só entram abreviações confirmadas nos dados; ampliar conforme o cliente reclamar.
SINONIMOS: dict[str, list[str]] = {
    "amortecedor": ["amort"],
    "amortecedores": ["amort"],
    "dianteiro": ["dt", "diant"],
    "dianteira": ["dt", "diant"],
    "traseiro": ["tras", "ts"],
    "traseira": ["tras", "ts"],
    "embreagem": ["embr"],
    "lampada": ["lamp"],
}

_COLUNAS = "id, codigo, descricao, categoria, tipo, marca, referencia, ean, aplicacao, preco, imagem_url, ativo"


def conectar(db_path: str) -> sqlite3.Connection:
    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def criar_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    conn.commit()


def _row_para_produto(row: sqlite3.Row) -> Produto:
    return Produto(
        id=row["id"], codigo=row["codigo"], descricao=row["descricao"], categoria=row["categoria"],
        tipo=row["tipo"], marca=row["marca"], referencia=row["referencia"], ean=row["ean"],
        aplicacao=row["aplicacao"], preco=row["preco"], imagem_url=row["imagem_url"], ativo=bool(row["ativo"]),
    )


def upsert_produto(conn: sqlite3.Connection, p: Produto) -> None:
    conn.execute(
        """
        INSERT INTO produtos (codigo, descricao, categoria, tipo, marca, referencia, ean, aplicacao, preco, imagem_url, ativo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(codigo) DO UPDATE SET
            descricao=excluded.descricao, categoria=excluded.categoria, tipo=excluded.tipo,
            marca=excluded.marca, referencia=excluded.referencia, ean=excluded.ean,
            aplicacao=excluded.aplicacao, preco=excluded.preco, ativo=excluded.ativo,
            imagem_url=CASE WHEN excluded.imagem_url != '' THEN excluded.imagem_url ELSE produtos.imagem_url END
        """,
        (p.codigo, p.descricao, p.categoria, p.tipo, p.marca, p.referencia, p.ean, p.aplicacao,
         p.preco, p.imagem_url, int(p.ativo)),
    )


def marcar_inativos_fora_de(conn: sqlite3.Connection, codigos_ativos: set[str]) -> int:
    """Desativa (não apaga) quem sumiu da planilha. Retorna quantos foram desativados."""
    atuais = {r["codigo"] for r in conn.execute("SELECT codigo FROM produtos WHERE ativo = 1")}
    sumiram = sorted(atuais - codigos_ativos)
    conn.executemany("UPDATE produtos SET ativo = 0 WHERE codigo = ?", [(c,) for c in sumiram])
    return len(sumiram)


def montar_match(busca: str | None) -> str | None:
    """Converte o texto digitado em consulta FTS5: todos os termos (AND), cada um como prefixo."""
    termos = re.findall(r"[0-9A-Za-z]+", normalizar(busca or ""))
    grupos = []
    for termo in termos:
        variantes = [termo.lower(), *SINONIMOS.get(termo.lower(), [])]
        grupos.append("(" + " OR ".join(f'"{v}"*' for v in variantes) + ")")
    return " AND ".join(grupos) or None


def _filtro(categoria: str | None, tipo: str | None, busca: str | None) -> tuple[str, str, list[object]]:
    """Retorna (FROM+JOIN, WHERE, params) compartilhado por listagem e contagens."""
    clausulas = ["p.ativo = 1"]
    params: list[object] = []
    origem = "produtos p"
    match = montar_match(busca)
    if match:
        origem = "produtos_fts JOIN produtos p ON p.id = produtos_fts.rowid"
        clausulas.append("produtos_fts MATCH ?")
        params.append(match)
    if categoria:
        clausulas.append("p.categoria = ?")
        params.append(categoria)
    if tipo:
        clausulas.append("p.tipo = ?")
        params.append(tipo)
    return origem, " AND ".join(clausulas), params


def listar_produtos(
    conn: sqlite3.Connection,
    categoria: str | None = None,
    tipo: str | None = None,
    busca: str | None = None,
    pagina: int = 1,
    por_pagina: int = 48,
) -> tuple[list[Produto], int]:
    origem, where, params = _filtro(categoria, tipo, busca)
    total = conn.execute(f"SELECT count(*) FROM {origem} WHERE {where}", params).fetchone()[0]
    ordem = "rank, p.descricao" if montar_match(busca) else "p.descricao"
    rows = conn.execute(
        f"SELECT {', '.join('p.' + c.strip() for c in _COLUNAS.split(','))} FROM {origem} WHERE {where} "
        f"ORDER BY {ordem} LIMIT ? OFFSET ?",
        [*params, por_pagina, max(pagina - 1, 0) * por_pagina],
    ).fetchall()
    return [_row_para_produto(r) for r in rows], total


def contar_por_categoria(conn: sqlite3.Connection, busca: str | None = None) -> dict[str, int]:
    """Contagem por categoria respeitando a busca (não a categoria selecionada), na ordem de CATEGORIAS."""
    origem, where, params = _filtro(None, None, busca)
    rows = conn.execute(f"SELECT p.categoria, count(*) n FROM {origem} WHERE {where} GROUP BY p.categoria", params)
    contagem = {r["categoria"]: r["n"] for r in rows}
    return {c: contagem[c] for c in CATEGORIAS if c in contagem}


def contar_por_tipo(conn: sqlite3.Connection, categoria: str, busca: str | None = None) -> list[tuple[str, int]]:
    origem, where, params = _filtro(categoria, None, busca)
    rows = conn.execute(
        f"SELECT p.tipo, count(*) n FROM {origem} WHERE {where} AND p.tipo != '' GROUP BY p.tipo "
        "HAVING n >= 3 ORDER BY n DESC, p.tipo",
        params,
    )
    return [(r["tipo"], r["n"]) for r in rows]
