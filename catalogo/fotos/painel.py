"""Painel visual no terminal para acompanhar o pipeline de fotos em tempo real.

    catalogo/.venv-fotos/bin/python -m catalogo.fotos.painel             # atualiza a cada 2 s (Ctrl+C sai)
    catalogo/.venv-fotos/bin/python -m catalogo.fotos.painel --uma-vez   # imprime uma vez e sai
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from catalogo.config import get_settings
from catalogo.db import conectar, criar_schema
from catalogo.fotos import banco

VERDE = "\033[92m"
AMARELO = "\033[93m"
VERMELHO = "\033[91m"
CIANO = "\033[96m"
CINZA = "\033[90m"
NEGRITO = "\033[1m"
RESET = "\033[0m"

LOGS_PADRAO = (Path("/tmp/fotos_carreiro.log"), Path("/tmp/piloto3_fotos.log"), Path("/tmp/piloto2_fotos.log"))
_LINHA_ITEM = re.compile(r"^\[(\d+)/(\d+)\]\s+(\S+)\s+(\d+)\s+prod\.\s+(.*)$")


def _log_ativo(caminho: str) -> Path | None:
    if caminho:
        p = Path(caminho)
        return p if p.exists() else None
    existentes = [p for p in LOGS_PADRAO if p.exists()]
    return max(existentes, key=lambda p: p.stat().st_mtime) if existentes else None


def _processo_rodando() -> bool:
    try:
        r = subprocess.run(["pgrep", "-f", "catalogo[./]fotos[./](executar|loop)"], capture_output=True, text=True)
        return r.returncode == 0
    except OSError:
        return False


def _barra(atual: int, total: int, largura: int = 32, cor: str = VERDE) -> str:
    if total <= 0:
        return f"[{'░' * largura}]   0.0%"
    cheios = min(largura, int(round(largura * atual / total)))
    pct = 100.0 * atual / total
    return f"{cor}{'█' * cheios}{CINZA}{'░' * (largura - cheios)}{RESET} {NEGRITO}{pct:5.1f}%{RESET}"


def _formatar_linha_log(linha: str, largura_max: int) -> str:
    m = _LINHA_ITEM.match(linha.strip())
    if not m:
        if "DuckDuckGo recusou" in linha:
            return f"  {VERMELHO}⚠ {linha.strip()[:largura_max - 4]}{RESET}"
        if linha.startswith("Lote:"):
            return f"  {CIANO}➔ {linha.strip()}{RESET}"
        return f"  {CINZA}{linha.strip()[:largura_max - 2]}{RESET}"
    i, n, status, n_prod, consulta = m.groups()
    progresso = f"[{int(i):>3}/{n}]"
    if status == "aprovada":
        selo = f"{VERDE}✔ APROVADA{RESET}"
    elif status == "revisao":
        selo = f"{AMARELO}● REVISÃO {RESET}"
    else:
        selo = f"{CINZA}○ SEM FOTO{RESET}"
    sobra = max(20, largura_max - 36)
    return f"  {CINZA}{progresso}{RESET}  {selo}  {NEGRITO}{int(n_prod):>3}p{RESET}  {consulta[:sobra]}"


def _ultimas_linhas(arquivo: Path | None, n: int = 15) -> list[str]:
    if not arquivo or not arquivo.exists():
        return []
    linhas = []
    for l in arquivo.read_text(errors="replace").splitlines():
        s = l.strip()
        if not s or "NNPACK" in s or "pin_memory" in s or s.startswith(("{", "}", '"')):
            continue
        if _LINHA_ITEM.match(s) or "DuckDuckGo" in s or s.startswith("Lote:") or "Nada pendente" in s:
            linhas.append(s)
    return linhas[-n:]


def renderizar(db_path: str, log_path: Path | None, linhas_log: int = 14) -> str:
    largura = min(shutil.get_terminal_size((100, 30)).columns, 100)
    conn = conectar(db_path)
    try:
        criar_schema(conn)
        banco.criar_schema_fotos(conn)
        rel = banco.relatorio(conn)
    finally:
        conn.close()

    g = rel.get("grupos", {})
    aprov = g.get("aprovada", 0)
    rev = g.get("revisao", 0)
    sem = g.get("sem_foto", 0)
    rej = g.get("rejeitada", 0)
    pend = g.get("pendente", 0)
    processados = aprov + rev + sem + rej
    total_grupos = processados + pend

    prod_foto = rel.get("produtos_com_foto", 0)
    prod_ativos = rel.get("produtos_ativos", 0)
    fila = rel.get("fila_pendente", {})
    fila_rev = fila.get("revisao", 0)
    fila_aud = fila.get("auditoria", 0)

    rodando = _processo_rodando()
    status_proc = f"{VERDE}● BUSCA RODANDO{RESET}" if rodando else f"{CINZA}○ BUSCA PARADA / CONCLUÍDA{RESET}"
    hora = time.strftime("%H:%M:%S")
    div = f"{CINZA}{'─' * largura}{RESET}"

    out = [
        f"{NEGRITO}{CIANO}━━━ CATÁLOGO CARREIRO AUTO PEÇAS · PAINEL DE FOTOS ━━━{RESET}  {status_proc}  {CINZA}{hora}{RESET}",
        div,
        f"  {NEGRITO}Grupos processados:{RESET} {_barra(processados, total_grupos, 28, CIANO)}  ({processados:,}/{total_grupos:,})".replace(",", "."),
        f"  {NEGRITO}Produtos com foto: {RESET} {_barra(prod_foto, prod_ativos, 28, VERDE)}  ({prod_foto:,}/{prod_ativos:,})".replace(",", "."),
        div,
        (f"  {VERDE}✔ Aprovados: {NEGRITO}{aprov:>5}{RESET}   "
         f"{AMARELO}● Em revisão: {NEGRITO}{rev:>5}{RESET}   "
         f"{CINZA}○ Sem foto: {NEGRITO}{sem:>5}{RESET}   "
         f"⏳ Pendentes: {NEGRITO}{pend:>6}{RESET}"),
        (f"  {NEGRITO}Fila do Agy:{RESET}  "
         f"{AMARELO}Revisão pendente: {NEGRITO}{fila_rev}{RESET}   |   "
         f"{CIANO}Auditoria pendente: {NEGRITO}{fila_aud}{RESET}"),
        div,
    ]
    nome_log = str(log_path) if log_path else "nenhum log encontrado"
    out.append(f"  {NEGRITO}Últimos itens processados{RESET} {CINZA}({nome_log}):{RESET}")
    ultimas = _ultimas_linhas(log_path, linhas_log)
    if ultimas:
        out.extend(_formatar_linha_log(l, largura) for l in ultimas)
    else:
        out.append(f"  {CINZA}(nenhum item registrado ainda){RESET}")
    out.append(div)
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    s = get_settings()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=s.db_path)
    ap.add_argument("--log", default="", help="arquivo de log (padrão: mais recente em /tmp)")
    ap.add_argument("--intervalo", type=float, default=2.0, help="segundos entre atualizações")
    ap.add_argument("--linhas", type=int, default=14, help="quantas linhas recentes do log mostrar")
    ap.add_argument("--uma-vez", action="store_true", help="imprime o painel uma vez e sai")
    args = ap.parse_args(argv)

    if args.uma_vez or not sys.stdout.isatty():
        print(renderizar(args.db, _log_ativo(args.log), args.linhas))
        return 0

    try:
        while True:
            painel = renderizar(args.db, _log_ativo(args.log), args.linhas)
            sys.stdout.write("\033[2J\033[H" + painel + f"\n  {CINZA}Pressione Ctrl+C para sair do painel (não interrompe a busca){RESET}\n")
            sys.stdout.flush()
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        print(f"\n{CINZA}Painel fechado.{RESET}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
