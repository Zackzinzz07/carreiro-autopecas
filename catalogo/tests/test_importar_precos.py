import csv
from pathlib import Path

import openpyxl
import pytest

from catalogo.db import conectar, criar_schema
from catalogo.sync import importar
from catalogo.sync.planilha import ler_planilha


def _criar_xlsx(caminho: Path, cabecalho: list[str], linhas: list[list[object]]) -> Path:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(cabecalho)
    for linha in linhas:
        ws.append(linha)
    wb.save(caminho)
    wb.close()
    return caminho


@pytest.mark.parametrize("coluna_preco", [
    "Pr. Venda",
    "Preço",
    "Preço Venda",
    "Preço de Venda",
    "Preço Venda R$",
    "Valor",
    "Valor:  Venda",
])
def test_cabecalho_pr_venda_e_sinonimos_viram_preco(tmp_path: Path, coluna_preco: str):
    xlsx = _criar_xlsx(
        tmp_path / "precos.xlsx",
        ["Código", "Descrição", coluna_preco],
        [
            ["000001", "AMORT DT GOL G5 08/", "27,00"],
            ["000002", "KIT EMBREAGEM LUK", "1.234,56"],
        ],
    )
    lido = ler_planilha(xlsx)
    assert lido.colunas == {"PRECO"}
    assert [p.preco for p in lido.produtos] == [27.0, 1234.56]


def test_cabecalho_cod_barras_com_ponto_e_planilha_antiga(tmp_path: Path):
    xlsx = _criar_xlsx(
        tmp_path / "antiga.xlsx",
        ["Código", "Descrição", "Cód. Barras"],
        [
            ["000001", "AMORT DT GOL G5 08/", ""],
            ["000002", "AMORT TS CELTA 01/ CORSA 95/", "000099"],
            ["000003", "FILTRO OLEO GOL/PARATI AP 1.6", "7891799419370"],
        ],
    )
    lido = ler_planilha(xlsx)
    assert lido.colunas == {"COD BARRAS"}
    por_cod = {p.codigo: p for p in lido.produtos}
    assert por_cod["000001"].ean == "" and por_cod["000001"].referencia == "" and por_cod["000001"].preco is None
    assert por_cod["000002"].referencia == "000099" and por_cod["000002"].ean == ""
    assert por_cod["000003"].ean == "7891799419370" and por_cod["000003"].referencia == ""


def test_import_sem_cod_barras_preserva_ean_referencia_e_marca(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "catalogo.db"
    csv_path = tmp_path / "novos_produtos.csv"
    monkeypatch.setattr(importar, "NOVOS_CSV_PATH", csv_path)

    # 1ª importação: planilha antiga (com Cód Barras e Marca, sem Preço)
    planilha_antiga = _criar_xlsx(
        tmp_path / "antiga.xlsx",
        ["Código", "Descrição", "Cód Barras", "Marca"],
        [
            ["000002", "AMORT TS CELTA 01/ CORSA 95/", "000099", "COFAP"],
            ["000003", "FILTRO OLEO GOL/PARATI AP 1.6", "7891799419370", "TECFIL"],
        ],
    )
    assert importar.main(["--arquivo", str(planilha_antiga), "--db", str(db_path), "--gravar"]) == 0

    # 2ª importação: planilha nova (com Pr. Venda, sem Cód Barras e sem Marca)
    planilha_nova = _criar_xlsx(
        tmp_path / "nova.xlsx",
        ["Código", "Descrição", "Pr. Venda"],
        [
            ["000002", "AMORT TS CELTA 01/ CORSA 95/", "189,90"],
            ["000003", "FILTRO OLEO GOL/PARATI AP 1.6", "27,00"],
        ],
    )
    assert importar.main(["--arquivo", str(planilha_nova), "--db", str(db_path), "--gravar"]) == 0

    conn = conectar(str(db_path))
    try:
        rows = {
            r["codigo"]: r
            for r in conn.execute("SELECT codigo, referencia, ean, marca, preco FROM produtos").fetchall()
        }
        assert rows["000002"]["referencia"] == "000099"
        assert rows["000002"]["marca"] == "COFAP"
        assert rows["000002"]["preco"] == pytest.approx(189.90)
        assert rows["000003"]["ean"] == "7891799419370"
        assert rows["000003"]["marca"] == "TECFIL"
        assert rows["000003"]["preco"] == pytest.approx(27.00)

        # Reimportar a mesma planilha nova não deve acusar alterados por falta de Cód Barras
        lido_novo = ler_planilha(planilha_nova)
        diff = importar.comparar(lido_novo, importar._existentes(conn))
        assert diff["alterados"] == 0
        assert diff["novos"] == 0

        # E reimportar a planilha antiga (sem preço) preserva os preços já gravados
        assert importar.main(["--arquivo", str(planilha_antiga), "--db", str(db_path), "--gravar"]) == 0
        precos = {
            r["codigo"]: r["preco"]
            for r in conn.execute("SELECT codigo, preco FROM produtos").fetchall()
        }
        assert precos == {"000002": pytest.approx(189.90), "000003": pytest.approx(27.00)}
    finally:
        conn.close()


def test_novos_dentro_e_fora_do_dedupe_reativados_e_csv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    db_path = tmp_path / "catalogo.db"
    csv_path = tmp_path / "novos_produtos.csv"
    monkeypatch.setattr(importar, "NOVOS_CSV_PATH", csv_path)

    conn = conectar(str(db_path))
    criar_schema(conn)
    conn.execute(
        "INSERT INTO produtos (codigo, descricao, categoria, tipo, ativo) VALUES "
        "('000001', 'AMORT DT GOL G5 08/', 'Suspensão e Direção', 'AMORT', 1),"
        "('000002', 'FILTRO OLEO GOL/PARATI AP 1.6', 'Filtros', 'FILTRO', 1),"
        "('000090', 'PECA ANTIGA DESATIVADA', 'Variados', 'PECA', 0)"
    )
    conn.commit()
    conn.close()

    planilha = _criar_xlsx(
        tmp_path / "lote.xlsx",
        ["Código", "Descrição", "Pr. Venda"],
        [
            ["000001", "AMORT DT GOL G5 08/", "210,00"],              # existente ativo
            ["000002", "FILTRO OLEO GOL/PARATI AP 1.6/1.8", "35,00"], # existente com descrição alterada
            ["000090", "PECA ANTIGA DESATIVADA", "50,00"],            # reativado (não é novo)
            ["000100", "AMORT DT GOL G5 08/", "215,00"],              # novo dentro do dedupe
            ["000200", "PASTILHA FREIO NOVA CERAMICA", "120,50"],     # novo fora do dedupe
        ],
    )

    # Dry-run: não grava no banco, mas grava o CSV e imprime o relatório
    assert importar.main(["--arquivo", str(planilha), "--db", str(db_path)]) == 0
    saida = capsys.readouterr().out
    assert "2 novos" in saida
    assert "1 reativados" in saida
    assert "1 com descrição alterada" in saida
    assert "000100" in saida and "000200" in saida

    with csv_path.open(encoding="utf-8") as f:
        linhas_csv = list(csv.DictReader(f))
    assert linhas_csv == [
        {
            "codigo": "000100",
            "descricao": "AMORT DT GOL G5 08/",
            "preco": "215.00",
            "situacao": "dentro_do_dedupe",
        },
        {
            "codigo": "000200",
            "descricao": "PASTILHA FREIO NOVA CERAMICA",
            "preco": "120.50",
            "situacao": "fora_do_dedupe",
        },
    ]

    # Depois de gravar, uma reimportação sem novos sobrescreve o CSV apenas com o cabeçalho
    assert importar.main(["--arquivo", str(planilha), "--db", str(db_path), "--gravar"]) == 0
    assert importar.main(["--arquivo", str(planilha), "--db", str(db_path)]) == 0
    with csv_path.open(encoding="utf-8") as f:
        assert list(csv.reader(f)) == [["codigo", "descricao", "preco", "situacao"]]
