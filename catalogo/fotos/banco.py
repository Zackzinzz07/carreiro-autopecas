"""Tabelas do pipeline de fotos e as operações sobre elas.

Toda aprovação/rejeição termina em `propagar`, que recalcula `produtos.imagem_url`:
foto do próprio grupo aprovada > foto do tipo (só produto sem marca) > nenhuma.
"""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from catalogo.fotos.normalizar import Chave, normalizar

_SCHEMA = """
CREATE TABLE IF NOT EXISTS foto_grupos (
    chave TEXT PRIMARY KEY,
    descricao_ref TEXT NOT NULL DEFAULT '',
    e_tipo INTEGER NOT NULL DEFAULT 0,
    tipo_pt TEXT NOT NULL DEFAULT '',
    consulta TEXT NOT NULL,
    consulta_alt TEXT NOT NULL DEFAULT '',
    tipo_en TEXT NOT NULL DEFAULT '',
    marca TEXT NOT NULL DEFAULT '',
    lado TEXT NOT NULL DEFAULT '',
    n_produtos INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pendente',   -- pendente|aprovada|revisao|sem_foto|rejeitada
    origem TEXT NOT NULL DEFAULT '',           -- auto|agy|auditoria:agy
    arquivo TEXT NOT NULL DEFAULT '',          -- <sha1>.webp em data/fotos/
    url_origem TEXT NOT NULL DEFAULT '',
    titulo_origem TEXT NOT NULL DEFAULT '',
    tentativas INTEGER NOT NULL DEFAULT 0,
    atualizado_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_foto_grupos_fila ON foto_grupos(status, e_tipo, n_produtos);

CREATE TABLE IF NOT EXISTS foto_candidatas (
    id INTEGER PRIMARY KEY,
    chave TEXT NOT NULL REFERENCES foto_grupos(chave),
    arquivo TEXT NOT NULL,
    url TEXT NOT NULL,
    titulo TEXT NOT NULL,
    dominio TEXT NOT NULL,
    clip_rank INTEGER,
    clip_top TEXT NOT NULL DEFAULT '',
    ocr_texto TEXT NOT NULL DEFAULT '',
    pontuacao INTEGER NOT NULL,
    aprovada_auto INTEGER NOT NULL,
    motivo TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_foto_candidatas_chave ON foto_candidatas(chave);

CREATE TABLE IF NOT EXISTS foto_revisao (
    id INTEGER PRIMARY KEY,
    chave TEXT NOT NULL REFERENCES foto_grupos(chave),
    tipo TEXT NOT NULL,                         -- revisao|auditoria
    status TEXT NOT NULL DEFAULT 'pendente',    -- pendente|aprovada|rejeitada|obsoleta
    candidata_escolhida INTEGER,
    decidido_por TEXT,
    criado_em TEXT NOT NULL,
    decidido_em TEXT
);
CREATE INDEX IF NOT EXISTS idx_foto_revisao_status ON foto_revisao(status, tipo);
"""

_PROPAGAR = """
UPDATE produtos SET imagem_url = COALESCE(
    (SELECT '/fotos/' || g.arquivo FROM foto_grupos g
      WHERE g.chave = produtos.foto_grupo AND g.status = 'aprovada' AND g.arquivo != ''),
    (SELECT '/fotos/' || t.arquivo FROM foto_grupos t
      WHERE produtos.foto_tipo != '' AND t.chave = 'TIPO:' || produtos.foto_tipo
        AND t.status = 'aprovada' AND t.arquivo != ''),
    '')
WHERE foto_grupo != '' {filtro}
"""


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def criar_schema_fotos(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    colunas = {r[1] for r in conn.execute("PRAGMA table_info(produtos)")}
    for coluna in ("foto_grupo", "foto_tipo"):
        if coluna not in colunas:
            conn.execute(f"ALTER TABLE produtos ADD COLUMN {coluna} TEXT NOT NULL DEFAULT ''")
    conn.commit()


def _inserir_grupo(conn: sqlite3.Connection, ch: Chave, descricao_ref: str, quando: str) -> bool:
    cur = conn.execute(
        "INSERT OR IGNORE INTO foto_grupos (chave, descricao_ref, e_tipo, tipo_pt, consulta, consulta_alt,"
        " tipo_en, marca, lado, atualizado_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (ch.texto, descricao_ref, int(ch.e_tipo), ch.tipo_pt, ch.consulta, ch.consulta_alt,
         ch.tipo_en, ch.marca, ch.lado, quando),
    )
    return cur.rowcount == 1


def foto_tipo_de(ch: Chave) -> str:
    """Tipo cuja foto genérica pode cobrir este produto ('' se tiver marca ou marca incerta)."""
    return ch.tipo_pt if ch.tipo_pt and not ch.marca and not ch.marca_incerta and not ch.e_tipo else ""


def sincronizar_grupos(conn: sqlite3.Connection, quando: str, dir_candidatas: Path | None = None) -> int:
    """Calcula o grupo de cada produto ativo, cria os grupos que faltam e remove os que ficaram vazios.

    Idempotente. Grupo sem nenhum produto (descrição mudou, produto saiu da planilha, ou a regra da
    chave mudou) é apagado junto com candidatas e revisões pendentes: a foto dele não vale mais para
    ninguém. Havendo qualquer mudança, as fotos dos produtos são recalculadas.
    """
    novos = 0
    vistos: set[str] = set()
    atualizacoes = []
    for r in conn.execute("SELECT id, descricao FROM produtos WHERE ativo = 1").fetchall():
        ch = normalizar(r["descricao"])
        if not ch.peca:
            continue
        atualizacoes.append((ch.texto, foto_tipo_de(ch), r["id"]))
        if ch.texto not in vistos:
            vistos.add(ch.texto)
            novos += _inserir_grupo(conn, ch, r["descricao"], quando)
    mudaram = conn.executemany(
        "UPDATE produtos SET foto_grupo = ?, foto_tipo = ? WHERE id = ? AND (foto_grupo != ? OR foto_tipo != ?)",
        [(g, t, i, g, t) for g, t, i in atualizacoes],
    ).rowcount
    conn.execute("UPDATE foto_grupos SET n_produtos = (SELECT count(*) FROM produtos p"
                 " WHERE p.ativo = 1 AND p.foto_grupo = foto_grupos.chave) WHERE e_tipo = 0")
    conn.execute("UPDATE foto_grupos SET n_produtos = (SELECT count(*) FROM produtos p"
                 " WHERE p.ativo = 1 AND 'TIPO:' || p.foto_tipo = foto_grupos.chave) WHERE e_tipo = 1")
    orfaos = [r["chave"] for r in conn.execute("SELECT chave FROM foto_grupos WHERE e_tipo = 0 AND n_produtos = 0")]
    for chave in orfaos:
        if dir_candidatas is not None:
            limpar_candidatas(conn, chave, dir_candidatas)
        conn.execute("DELETE FROM foto_candidatas WHERE chave = ?", (chave,))
        conn.execute("UPDATE foto_revisao SET status = 'obsoleta' WHERE chave = ? AND status = 'pendente'", (chave,))
        conn.execute("DELETE FROM foto_grupos WHERE chave = ?", (chave,))
    if novos or mudaram or orfaos:
        propagar(conn)
    conn.commit()
    return novos


def chave_de(row) -> Chave:
    if row["e_tipo"]:
        return Chave.para_tipo(row["tipo_pt"], row["tipo_en"])
    return normalizar(row["descricao_ref"])


def garantir_grupo_tipo(conn: sqlite3.Connection, ch: Chave, quando: str) -> str | None:
    tipo = foto_tipo_de(ch)
    if not tipo:
        return None
    t = Chave.para_tipo(tipo, ch.tipo_en)
    _inserir_grupo(conn, t, "", quando)
    conn.execute("UPDATE foto_grupos SET n_produtos = (SELECT count(*) FROM produtos p"
                 " WHERE p.ativo = 1 AND p.foto_tipo = ?) WHERE chave = ?", (tipo, t.texto))
    conn.commit()
    return t.texto


def grupos_pendentes(conn: sqlite3.Connection, limite: int, chaves: list[str] | None = None) -> list[sqlite3.Row]:
    ordem = "ORDER BY e_tipo, n_produtos DESC, chave LIMIT ?"
    if chaves is None:
        return conn.execute(f"SELECT * FROM foto_grupos WHERE status = 'pendente' {ordem}", (limite,)).fetchall()
    if not chaves:
        return []
    marcadores = ",".join("?" * len(chaves))
    return conn.execute(
        f"SELECT * FROM foto_grupos WHERE status = 'pendente' AND chave IN ({marcadores}) {ordem}",
        [*chaves, limite],
    ).fetchall()


@dataclass(frozen=True)
class NovaCandidata:
    arquivo: str
    url: str
    titulo: str
    dominio: str
    clip_rank: int | None
    clip_top: str
    ocr_texto: str
    pontuacao: int
    aprovada_auto: bool
    motivo: str


def registrar_candidatas(conn: sqlite3.Connection, chave: str, candidatas: list[NovaCandidata]) -> list[int]:
    ids = []
    for c in candidatas:
        cur = conn.execute(
            "INSERT INTO foto_candidatas (chave, arquivo, url, titulo, dominio, clip_rank, clip_top, ocr_texto,"
            " pontuacao, aprovada_auto, motivo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (chave, c.arquivo, c.url, c.titulo, c.dominio, c.clip_rank, c.clip_top, c.ocr_texto,
             c.pontuacao, int(c.aprovada_auto), c.motivo),
        )
        ids.append(cur.lastrowid)
    conn.commit()
    return ids


def candidatas_de(conn: sqlite3.Connection, chave: str) -> list[sqlite3.Row]:
    """Ordem fixa (pontuação, id): é a numeração 0..3 mostrada nas folhas de revisão."""
    return conn.execute("SELECT * FROM foto_candidatas WHERE chave = ? ORDER BY pontuacao DESC, id",
                        (chave,)).fetchall()


def limpar_candidatas(conn: sqlite3.Connection, chave: str, dir_candidatas: Path) -> None:
    for r in conn.execute("SELECT arquivo FROM foto_candidatas WHERE chave = ?", (chave,)).fetchall():
        (Path(dir_candidatas) / r["arquivo"]).unlink(missing_ok=True)
    conn.execute("DELETE FROM foto_candidatas WHERE chave = ?", (chave,))
    conn.commit()


def marcar_status(conn: sqlite3.Connection, chave: str, status: str, quando: str, *, tentativa: bool = False) -> None:
    conn.execute("UPDATE foto_grupos SET status = ?, atualizado_em = ?, tentativas = tentativas + ? WHERE chave = ?",
                 (status, quando, int(tentativa), chave))
    conn.commit()


def propagar(conn: sqlite3.Connection, chave: str | None = None) -> None:
    if chave is None:
        conn.execute(_PROPAGAR.format(filtro=""))
    elif chave.startswith("TIPO:"):
        conn.execute(_PROPAGAR.format(filtro="AND foto_tipo = ?"), (chave[len("TIPO:"):],))
    else:
        conn.execute(_PROPAGAR.format(filtro="AND foto_grupo = ?"), (chave,))
    conn.commit()


def aprovar(conn: sqlite3.Connection, chave: str, candidata_id: int, *, origem: str, quando: str,
            dir_candidatas: Path, dir_fotos: Path) -> str:
    c = conn.execute("SELECT * FROM foto_candidatas WHERE id = ? AND chave = ?", (candidata_id, chave)).fetchone()
    if c is None:
        raise ValueError(f"candidata {candidata_id} não pertence ao grupo {chave!r}")
    dados = (Path(dir_candidatas) / c["arquivo"]).read_bytes()
    nome = hashlib.sha1(dados).hexdigest() + ".webp"
    Path(dir_fotos).mkdir(parents=True, exist_ok=True)
    (Path(dir_fotos) / nome).write_bytes(dados)
    conn.execute("UPDATE foto_grupos SET status = 'aprovada', origem = ?, arquivo = ?, url_origem = ?,"
                 " titulo_origem = ?, atualizado_em = ? WHERE chave = ?",
                 (origem, nome, c["url"], c["titulo"], quando, chave))
    propagar(conn, chave)
    return nome


def rejeitar_grupo(conn: sqlite3.Connection, chave: str, *, origem: str, quando: str) -> None:
    conn.execute("UPDATE foto_grupos SET status = 'rejeitada', origem = ?, arquivo = '', atualizado_em = ?"
                 " WHERE chave = ?", (origem, quando, chave))
    propagar(conn, chave)


def registrar_revisao(conn: sqlite3.Connection, chave: str, tipo: str, quando: str) -> int:
    conn.execute("UPDATE foto_revisao SET status = 'obsoleta' WHERE chave = ? AND tipo = ? AND status = 'pendente'",
                 (chave, tipo))
    cur = conn.execute("INSERT INTO foto_revisao (chave, tipo, criado_em) VALUES (?, ?, ?)", (chave, tipo, quando))
    conn.commit()
    return cur.lastrowid


def decidir_revisao(conn: sqlite3.Connection, revisao_id: int, status: str, *, candidata_id: int | None,
                    por: str, quando: str) -> None:
    conn.execute("UPDATE foto_revisao SET status = ?, candidata_escolhida = ?, decidido_por = ?, decidido_em = ?"
                 " WHERE id = ?", (status, candidata_id, por, quando, revisao_id))
    conn.commit()


def resetar_grupos(conn: sqlite3.Connection, chaves: list[str], dir_candidatas: Path) -> int:
    if not chaves:
        return 0
    for chave in chaves:
        limpar_candidatas(conn, chave, dir_candidatas)
    marcadores = ",".join("?" * len(chaves))
    cur = conn.execute(f"UPDATE foto_grupos SET status = 'pendente', origem = '', arquivo = '', url_origem = '',"
                       f" titulo_origem = '', tentativas = 0 WHERE chave IN ({marcadores})", chaves)
    n = cur.rowcount
    conn.execute(f"UPDATE foto_revisao SET status = 'obsoleta' WHERE status = 'pendente'"
                 f" AND chave IN ({marcadores})", chaves)
    propagar(conn)
    return n


def backup(db_path: Path | str, dir_backups: Path | str) -> Path:
    Path(dir_backups).mkdir(parents=True, exist_ok=True)
    destino = Path(dir_backups) / f"catalogo_{datetime.now():%Y%m%d_%H%M%S_%f}.db"
    origem = sqlite3.connect(str(db_path))
    copia = sqlite3.connect(str(destino))
    try:
        origem.backup(copia)
    finally:
        copia.close()
        origem.close()
    return destino


def relatorio(conn: sqlite3.Connection) -> dict:
    def contar(sql: str) -> dict[str, int]:
        return {r[0]: r[1] for r in conn.execute(sql)}

    return {
        "grupos": contar("SELECT status, count(*) FROM foto_grupos WHERE e_tipo = 0 GROUP BY status"),
        "grupos_tipo": contar("SELECT status, count(*) FROM foto_grupos WHERE e_tipo = 1 GROUP BY status"),
        "aprovadas_por": contar("SELECT origem, count(*) FROM foto_grupos WHERE status = 'aprovada' GROUP BY origem"),
        "fila_pendente": contar("SELECT tipo, count(*) FROM foto_revisao WHERE status = 'pendente' GROUP BY tipo"),
        "produtos_com_foto": conn.execute(
            "SELECT count(*) FROM produtos WHERE ativo = 1 AND imagem_url != ''").fetchone()[0],
        "produtos_ativos": conn.execute("SELECT count(*) FROM produtos WHERE ativo = 1").fetchone()[0],
    }
