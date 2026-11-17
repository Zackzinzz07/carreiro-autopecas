"""Importa a planilha de estoque para o SQLite.  Por padrão só SIMULA (dry-run).

    python -m catalogo.sync.importar --arquivo "../PRODUTOS E PREÇOS v2.xlsx"           # relatório, não grava
    python -m catalogo.sync.importar --arquivo "../PRODUTOS E PREÇOS v2.xlsx" --gravar  # grava no banco
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from dataclasses import replace
from pathlib import Path

from catalogo.config import BASE_DIR, get_settings
from catalogo.db import conectar, criar_schema, marcar_inativos_fora_de, upsert_produto
from catalogo.models import Produto
from catalogo.sync.planilha import ResultadoLeitura, ler_planilha

NOVOS_CSV_PATH = BASE_DIR / "data" / "novos_produtos.csv"


def _existentes(conn) -> dict[str, Produto]:
    rows = conn.execute(
        "SELECT id, codigo, descricao, categoria, tipo, marca, referencia, ean, aplicacao, preco, imagem_url, ativo "
        "FROM produtos"
    )
    return {
        r["codigo"]: Produto(
            id=r["id"], codigo=r["codigo"], descricao=r["descricao"], categoria=r["categoria"],
            tipo=r["tipo"], marca=r["marca"], referencia=r["referencia"], ean=r["ean"],
            aplicacao=r["aplicacao"], preco=r["preco"], imagem_url=r["imagem_url"], ativo=bool(r["ativo"]),
        )
        for r in rows
    }


def mesclar_ausentes(lido: ResultadoLeitura, existentes: dict[str, Produto]) -> list[Produto]:
    """Copia do banco os campos de colunas opcionais que não vieram na planilha."""
    colunas = lido.colunas
    mesclados: list[Produto] = []
    for p in lido.produtos:
        atual = existentes.get(p.codigo)
        if atual is not None:
            campos: dict[str, object] = {}
            if "COD BARRAS" not in colunas:
                campos["referencia"] = atual.referencia
                campos["ean"] = atual.ean
            if "PRECO" not in colunas:
                campos["preco"] = atual.preco
            if "MARCA" not in colunas:
                campos["marca"] = atual.marca
            if "APLICACAO" not in colunas:
                campos["aplicacao"] = atual.aplicacao
            if campos:
                p = replace(p, **campos)
        mesclados.append(p)
    lido.produtos = mesclados
    return mesclados


def _campos_comparacao(p: Produto) -> tuple[object, ...]:
    return (p.descricao, p.categoria, p.marca, p.referencia, p.ean, p.aplicacao, p.preco)


def comparar(lido: ResultadoLeitura, existentes: dict[str, Produto]) -> dict[str, object]:
    mesclar_ausentes(lido, existentes)
    descricoes_ativas = {p.descricao for p in existentes.values() if p.ativo}
    dentro_do_dedupe: list[Produto] = []
    fora_do_dedupe: list[Produto] = []
    alterados = reativados = descricao_alterada = 0

    for p in lido.produtos:
        atual = existentes.get(p.codigo)
        if atual is None:
            if p.descricao in descricoes_ativas:
                dentro_do_dedupe.append(p)
            else:
                fora_do_dedupe.append(p)
        else:
            if not atual.ativo:
                reativados += 1
            if atual.descricao != p.descricao:
                descricao_alterada += 1
            if _campos_comparacao(atual) != _campos_comparacao(p):
                alterados += 1

    ativos_no_banco = {codigo for codigo, p in existentes.items() if p.ativo}
    sumiram = len(ativos_no_banco - {p.codigo for p in lido.produtos})
    return {
        "novos": len(dentro_do_dedupe) + len(fora_do_dedupe),
        "alterados": alterados,
        "sumiram": sumiram,
        "reativados": reativados,
        "descricao_alterada": descricao_alterada,
        "dentro_do_dedupe": dentro_do_dedupe,
        "fora_do_dedupe": fora_do_dedupe,
    }


def gravar_csv_novos(diff: dict[str, object], caminho: str | Path | None = None) -> Path:
    destino = Path(caminho) if caminho is not None else NOVOS_CSV_PATH
    destino.parent.mkdir(parents=True, exist_ok=True)
    dentro: list[Produto] = diff.get("dentro_do_dedupe", [])  # type: ignore[assignment]
    fora: list[Produto] = diff.get("fora_do_dedupe", [])      # type: ignore[assignment]
    with destino.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["codigo", "descricao", "preco", "situacao"])
        for situacao, lista in (("dentro_do_dedupe", dentro), ("fora_do_dedupe", fora)):
            for p in lista:
                preco = f"{p.preco:.2f}" if p.preco is not None else ""
                writer.writerow([p.codigo, p.descricao, preco, situacao])
    return destino


def _fmt_preco(preco: float | None) -> str:
    return f"{preco:.2f}" if preco is not None else "-"


def imprimir_relatorio(lido: ResultadoLeitura, diff: dict[str, object], gravou: bool) -> None:
    total = len(lido.produtos)
    print(f"Produtos ativos lidos: {total}  |  INATIVO na descrição (ignorados): {len(lido.inativos)}")
    print(f"Linhas inválidas: {len(lido.invalidos)}  |  Códigos duplicados: {len(set(lido.duplicados))}")
    for linha, motivo in lido.invalidos[:5]:
        print(f"  linha {linha}: {motivo}")
    print("\nCategorias (INFERIDAS pela descrição — revisar em catalogo/categorias.py):")
    for categoria, n in Counter(p.categoria for p in lido.produtos).most_common():
        print(f"  {categoria:<28}{n:>6}  {n / max(total, 1):6.1%}")
    com_preco = sum(p.preco is not None for p in lido.produtos)
    print(f"\nCom preço: {com_preco}/{total}  |  com EAN: {sum(bool(p.ean) for p in lido.produtos)}"
          f"  |  com código alternativo: {sum(bool(p.referencia) for p in lido.produtos)}")
    print(
        f"Contra o banco atual: {diff['novos']} novos, {diff['alterados']} alterados "
        f"({diff.get('descricao_alterada', 0)} com descrição alterada), "
        f"{diff.get('reativados', 0)} reativados, {diff['sumiram']} sumiram da planilha"
    )
    dentro: list[Produto] = diff.get("dentro_do_dedupe", [])  # type: ignore[assignment]
    fora: list[Produto] = diff.get("fora_do_dedupe", [])      # type: ignore[assignment]
    print(f"\nNovos dentro do dedupe (descrição já existe em produto ativo): {len(dentro)}")
    for p in dentro[:30]:
        print(f"  {p.codigo}  {p.descricao:<45}  {_fmt_preco(p.preco)}")
    print(f"\nNovos fora do dedupe (descrição inédita / card novo): {len(fora)}")
    for p in fora[:30]:
        print(f"  {p.codigo}  {p.descricao:<45}  {_fmt_preco(p.preco)}")
    print("\nGRAVADO no banco." if gravou else "\nDRY-RUN: nada foi gravado. Rode com --gravar para aplicar.")


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arquivo", default=settings.fonte_xlsx_path, help="planilha .xlsx (padrão: FONTE_XLSX_PATH)")
    ap.add_argument("--db", default=settings.db_path)
    ap.add_argument("--csv-novos", default=None, help="caminho do CSV de novos produtos (padrão: catalogo/data/novos_produtos.csv)")
    ap.add_argument("--gravar", action="store_true", help="grava no banco (sem isso é só simulação)")
    args = ap.parse_args(argv)
    if not args.arquivo or not Path(args.arquivo).exists():
        print(f"Planilha não encontrada: {args.arquivo!r}. Use --arquivo ou FONTE_XLSX_PATH.", file=sys.stderr)
        return 2

    lido = ler_planilha(args.arquivo)
    conn = conectar(args.db)
    try:
        criar_schema(conn)
        diff = comparar(lido, _existentes(conn))   # comparar já mescla as colunas ausentes em lido.produtos
        gravar_csv_novos(diff, args.csv_novos)
        if args.gravar:
            with conn:
                for produto in lido.produtos:
                    upsert_produto(conn, produto)
                marcar_inativos_fora_de(conn, {p.codigo for p in lido.produtos})
        imprimir_relatorio(lido, diff, args.gravar)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
