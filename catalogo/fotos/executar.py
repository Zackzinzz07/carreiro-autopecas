"""Processa grupos pendentes: busca → baixa → verifica → aprova, manda para revisão ou fica sem foto.

    catalogo/.venv-fotos/bin/python -m catalogo.fotos.executar --limite 100     # um lote
    catalogo/.venv-fotos/bin/python -m catalogo.fotos.executar --piloto         # amostra fixa, audita 100%
    catalogo/.venv-fotos/bin/python -m catalogo.fotos.executar --refazer-piloto # volta o piloto a pendente
    catalogo/.venv-fotos/bin/python -m catalogo.fotos.executar --relatorio

Retorno: 0 = lote processado, 3 = DuckDuckGo bloqueando (rode de novo depois), 4 = nada pendente.
O status do grupo só é gravado no fim do processamento: interrompido no meio, ele continua pendente.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sqlite3
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from catalogo.config import get_settings
from catalogo.db import conectar, criar_schema
from catalogo.fotos import banco, busca, imagem
from catalogo.fotos.dados.tipos_en import TIPOS_EN
from catalogo.fotos.normalizar import Chave
from catalogo.fotos.verificar import Decisao, Sinais, decidir, marca_no_ocr, outra_marca_no_ocr, sinais_de_texto

MAX_DOWNLOADS = 8        # candidatas baixadas por consulta
MAX_REVISAO = 4          # candidatas mostradas ao Agy
PAUSAS_BLOQUEIO = (0, 30, 90, 300)  # segundos antes de cada tentativa quando o DuckDuckGo recusa


@dataclass
class Contexto:
    conn: sqlite3.Connection
    buscador: Callable[[str], list[busca.Resultado]]
    baixador: Callable[[str], bytes | None]
    visao: Any
    ocr: Any
    dir_candidatas: Path
    dir_fotos: Path
    agora: Callable[[], str]
    fracao_auditoria: float
    rng: random.Random
    espera: float = 0.0
    hashes_bloqueados: frozenset[str] = frozenset()


@dataclass
class Avaliada:
    decisao: Decisao
    resultado: busca.Resultado
    webp: bytes
    clip_rank: int | None
    clip_top: str
    ocr: str


def _avaliar(ctx: Contexto, ch: Chave, resultados: list[busca.Resultado]) -> list[Avaliada]:
    avaliadas: list[Avaliada] = []
    baixadas = 0
    for r in resultados:
        if baixadas >= MAX_DOWNLOADS:
            break
        if busca.bloqueado(r) or imagem.termo_placeholder(f"{r.titulo} {r.url_imagem}"):
            continue
        dados = ctx.baixador(r.url_imagem)
        baixadas += 1
        if not dados or imagem.sha1(dados) in ctx.hashes_bloqueados:
            continue
        processada, _motivo = imagem.processar(dados)
        if processada is None:
            continue
        rank, lixo, topo = ctx.visao.ranking(processada.webp, ch.tipo_en)
        texto_ocr = ctx.ocr.ler(dados) if ch.marca else ""
        sinais = Sinais(
            valida=True, clip_rank=rank, clip_top_lixo=lixo, **sinais_de_texto(ch, r.titulo),
            ocr_marca=bool(ch.marca) and marca_no_ocr(ch.marca, texto_ocr),
            ocr_outra_marca=bool(ch.marca) and outra_marca_no_ocr(ch.marca, texto_ocr),
            dominio_loja=busca.eh_loja(r), fundo_branco=processada.fundo_branco,
        )
        avaliadas.append(Avaliada(decidir(ch, sinais), r, processada.webp, rank, topo, texto_ocr))
    return avaliadas


def _nome_candidata(chave: str, i: int) -> str:
    return f"{hashlib.sha1(chave.encode()).hexdigest()[:12]}_{i}.webp"


def _registrar(ctx: Contexto, chave: str, avaliadas: list[Avaliada]) -> list[int]:
    Path(ctx.dir_candidatas).mkdir(parents=True, exist_ok=True)
    novas = []
    for i, a in enumerate(avaliadas):
        nome = _nome_candidata(chave, i)
        (Path(ctx.dir_candidatas) / nome).write_bytes(a.webp)
        novas.append(banco.NovaCandidata(
            arquivo=nome, url=a.resultado.url_pagina or a.resultado.url_imagem, titulo=a.resultado.titulo,
            dominio=busca.dominio(a.resultado.url_imagem), clip_rank=a.clip_rank, clip_top=a.clip_top,
            ocr_texto=a.ocr[:300], pontuacao=a.decisao.pontuacao, aprovada_auto=a.decisao.aprovada,
            motivo="; ".join(a.decisao.motivos)))
    return banco.registrar_candidatas(ctx.conn, chave, novas)


def _por_pontuacao(avaliadas: list[Avaliada]) -> list[Avaliada]:
    return sorted(avaliadas, key=lambda a: -a.decisao.pontuacao)


def processar_grupo(ctx: Contexto, row: sqlite3.Row) -> str:
    ch = banco.chave_de(row)
    chave = row["chave"]
    avaliadas: list[Avaliada] = []
    for consulta in (c for c in (row["consulta"], row["consulta_alt"]) if c):
        avaliadas = _avaliar(ctx, ch, ctx.buscador(consulta))
        if ctx.espera:
            time.sleep(ctx.espera)
        if any(a.decisao.plausivel for a in avaliadas):
            break

    quando = ctx.agora()
    banco.limpar_candidatas(ctx.conn, chave, ctx.dir_candidatas)
    aprovadas = _por_pontuacao([a for a in avaliadas if a.decisao.aprovada])
    if aprovadas:
        [candidata_id] = _registrar(ctx, chave, aprovadas[:1])
        banco.aprovar(ctx.conn, chave, candidata_id, origem="auto", quando=quando,
                      dir_candidatas=ctx.dir_candidatas, dir_fotos=ctx.dir_fotos)
        banco.limpar_candidatas(ctx.conn, chave, ctx.dir_candidatas)
        if ctx.rng.random() < ctx.fracao_auditoria:
            banco.registrar_revisao(ctx.conn, chave, "auditoria", quando)
        return "aprovada"

    plausiveis = _por_pontuacao([a for a in avaliadas if a.decisao.plausivel])[:MAX_REVISAO]
    if plausiveis:
        _registrar(ctx, chave, plausiveis)
        banco.marcar_status(ctx.conn, chave, "revisao", quando)
        banco.registrar_revisao(ctx.conn, chave, "revisao", quando)
        return "revisao"

    banco.marcar_status(ctx.conn, chave, "sem_foto", quando, tentativa=True)
    banco.garantir_grupo_tipo(ctx.conn, ch, quando)
    return "sem_foto"


def selecionar_piloto(conn: sqlite3.Connection, n: int = 100, seed: int = 42) -> list[str]:
    """Amostra fixa estratificada pelas categorias; devolve as chaves de grupo (sem repetir)."""
    rng = random.Random(seed)
    categorias = [r[0] for r in conn.execute(
        "SELECT DISTINCT categoria FROM produtos WHERE ativo = 1 AND foto_grupo != '' ORDER BY categoria")]
    if not categorias:
        return []
    por_categoria = math.ceil(n / len(categorias))
    chaves: list[str] = []
    for categoria in categorias:
        grupos = [r[0] for r in conn.execute(
            "SELECT foto_grupo FROM produtos WHERE ativo = 1 AND foto_grupo != '' AND categoria = ? ORDER BY codigo",
            (categoria,))]
        chaves += rng.sample(grupos, min(por_categoria, len(grupos)))
    return list(dict.fromkeys(chaves))


def _hashes_bloqueados(pasta: Path) -> frozenset[str]:
    arquivo = pasta / "hashes_bloqueados.txt"
    if not arquivo.exists():
        return frozenset()
    return frozenset(l.strip() for l in arquivo.read_text().splitlines() if l.strip() and not l.startswith("#"))


def _imprimir_relatorio(conn: sqlite3.Connection) -> None:
    print(json.dumps(banco.relatorio(conn), ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    s = get_settings()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=s.db_path)
    ap.add_argument("--limite", type=int, default=100, help="grupos por lote")
    ap.add_argument("--piloto", action="store_true", help="só a amostra fixa (~100 produtos); audita 100%%")
    ap.add_argument("--refazer-piloto", action="store_true", help="volta os grupos do piloto para pendente")
    ap.add_argument("--espera", type=float, default=3.0, help="segundos entre buscas")
    ap.add_argument("--auditar", type=float, default=0.03, help="fração das aprovações automáticas auditada")
    ap.add_argument("--relatorio", action="store_true")
    args = ap.parse_args(argv)

    conn = conectar(args.db)
    try:
        criar_schema(conn)
        banco.criar_schema_fotos(conn)
        if args.relatorio:
            _imprimir_relatorio(conn)
            return 0
        banco.sincronizar_grupos(conn, banco.agora())
        chaves = selecionar_piloto(conn) if (args.piloto or args.refazer_piloto) else None
        if args.refazer_piloto:
            n = banco.resetar_grupos(conn, chaves or [], Path(s.candidatas_dir))
            print(f"{n} grupos do piloto voltaram para pendente.")
            return 0
        fila = banco.grupos_pendentes(conn, len(chaves) if chaves is not None else args.limite, chaves)
        if not fila:
            print("Nada pendente.")
            return 4

        from catalogo.fotos import modelos  # pesado: só carrega quando há trabalho

        ctx = Contexto(
            conn=conn, buscador=busca.buscar_imagens, baixador=busca.baixar,
            visao=modelos.Visao(sorted(set(TIPOS_EN.values()))), ocr=modelos.Ocr(),
            dir_candidatas=Path(s.candidatas_dir), dir_fotos=Path(s.fotos_dir), agora=banco.agora,
            fracao_auditoria=1.0 if args.piloto else args.auditar, rng=random.Random(),
            espera=args.espera, hashes_bloqueados=_hashes_bloqueados(Path(args.db).parent),
        )
        contagem: Counter[str] = Counter()
        for i, row in enumerate(fila, 1):
            for pausa in PAUSAS_BLOQUEIO:
                time.sleep(pausa)
                try:
                    status = processar_grupo(ctx, row)
                    break
                except busca.BuscaBloqueada as erro:
                    print(f"  DuckDuckGo recusou ({erro}); tentando de novo...", flush=True)
            else:
                print("DuckDuckGo segue bloqueando. Parei; o que já foi feito está salvo. Rode de novo mais tarde.")
                return 3
            contagem[status] += 1
            print(f"[{i}/{len(fila)}] {status:<9} {row['n_produtos']:>4} prod.  {row['consulta'][:70]}", flush=True)
        print("Lote:", dict(contagem))
        _imprimir_relatorio(conn)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
