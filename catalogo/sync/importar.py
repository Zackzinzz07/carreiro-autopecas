"""Importa a planilha de estoque para o SQLite.  Por padrão só SIMULA (dry-run).

    python -m catalogo.sync.importar --arquivo "../PRODUTOS E PREÇOS v2.xlsx"           # relatório, não grava
    python -m catalogo.sync.importar --arquivo "../PRODUTOS E PREÇOS v2.xlsx" --gravar  # grava no banco
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

from catalogo.config import get_settings
from catalogo.db import conectar, criar_schema, marcar_inativos_fora_de, upsert_produto
from catalogo.sync.planilha import ResultadoLeitura, ler_planilha


def _existentes(conn) -> dict[str, tuple]:
    rows = conn.execute("SELECT codigo, descricao, categoria, referencia, ean, preco FROM produtos WHERE ativo = 1")
    return {r["codigo"]: (r["descricao"], r["categoria"], r["referencia"], r["ean"], r["preco"]) for r in rows}


def comparar(lido: ResultadoLeitura, existentes: dict[str, tuple]) -> dict[str, int]:
    novos = alterados = 0
    for p in lido.produtos:
        atual = existentes.get(p.codigo)
        if atual is None:
            novos += 1
        elif atual != (p.descricao, p.categoria, p.referencia, p.ean, p.preco):
            alterados += 1
    sumiram = len(set(existentes) - {p.codigo for p in lido.produtos})
    return {"novos": novos, "alterados": alterados, "sumiram": sumiram}


def imprimir_relatorio(lido: ResultadoLeitura, diff: dict[str, int], gravou: bool) -> None:
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
    print(f"Contra o banco atual: {diff['novos']} novos, {diff['alterados']} alterados, {diff['sumiram']} sumiram da planilha")
    print("\nGRAVADO no banco." if gravou else "\nDRY-RUN: nada foi gravado. Rode com --gravar para aplicar.")


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arquivo", default=settings.fonte_xlsx_path, help="planilha .xlsx (padrão: FONTE_XLSX_PATH)")
    ap.add_argument("--db", default=settings.db_path)
    ap.add_argument("--gravar", action="store_true", help="grava no banco (sem isso é só simulação)")
    args = ap.parse_args(argv)
    if not args.arquivo or not Path(args.arquivo).exists():
        print(f"Planilha não encontrada: {args.arquivo!r}. Use --arquivo ou FONTE_XLSX_PATH.", file=sys.stderr)
        return 2

    lido = ler_planilha(args.arquivo)
    conn = conectar(args.db)
    try:
        criar_schema(conn)
        diff = comparar(lido, _existentes(conn))
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
