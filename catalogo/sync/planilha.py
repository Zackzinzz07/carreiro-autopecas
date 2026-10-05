"""Leitura e normalização da planilha de estoque (.xlsx) exportada do sistema da loja.

Colunas reconhecidas pelo cabeçalho (sem acento, maiúsculas):
  obrigatórias: CODIGO, DESCRICAO
  opcionais:    COD BARRAS, PRECO, MARCA, APLICACAO
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from catalogo.categorias import categoria_para_descricao, normalizar, tipo_da_peca
from catalogo.models import Produto

_OBRIGATORIAS = {"CODIGO", "DESCRICAO"}
_TAMANHOS_EAN = {8, 12, 13, 14}


@dataclass
class ResultadoLeitura:
    produtos: list[Produto] = field(default_factory=list)   # ativos, prontos para gravar
    inativos: list[str] = field(default_factory=list)       # códigos marcados INATIVO na descrição
    duplicados: list[str] = field(default_factory=list)     # códigos repetidos (vale a última ocorrência)
    invalidos: list[tuple[int, str]] = field(default_factory=list)  # (linha, motivo)


def _texto(valor: object) -> str:
    return "" if valor is None else str(valor).strip()


def _preco(valor: object) -> float | None:
    if valor in (None, ""):
        return None
    try:
        numero = float(str(valor).replace("R$", "").replace(".", "").replace(",", ".")) if isinstance(valor, str) else float(valor)
    except ValueError:
        return None
    return numero if numero > 0 else None


def _eh_inativo(descricao: str) -> bool:
    return bool(re.search(r"\bINATIVO\b", normalizar(descricao)))


def ler_planilha(caminho: str | Path) -> ResultadoLeitura:
    import openpyxl  # import tardio: só o sync precisa

    wb = openpyxl.load_workbook(caminho, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    linhas = ws.iter_rows(values_only=True)
    cabecalho = [normalizar(_texto(c)) for c in next(linhas)]
    faltando = _OBRIGATORIAS - set(cabecalho)
    if faltando:
        raise ValueError(f"Planilha sem coluna(s) obrigatória(s): {', '.join(sorted(faltando))}. Encontrei: {cabecalho}")
    idx = {nome: i for i, nome in enumerate(cabecalho)}

    def col(linha: tuple, nome: str) -> str:
        i = idx.get(nome)
        return _texto(linha[i]) if i is not None and i < len(linha) else ""

    resultado = ResultadoLeitura()
    por_codigo: dict[str, Produto] = {}
    for n, linha in enumerate(linhas, start=2):
        codigo, descricao = col(linha, "CODIGO"), col(linha, "DESCRICAO")
        if not codigo and not descricao:
            continue  # linha em branco
        if not codigo or not descricao:
            resultado.invalidos.append((n, "código ou descrição vazio"))
            continue
        if _eh_inativo(descricao):
            resultado.inativos.append(codigo)
            continue
        barras = col(linha, "COD BARRAS")
        ean = barras if barras.isdigit() and len(barras) in _TAMANHOS_EAN and barras != codigo else ""
        referencia = barras if barras and not ean and barras != codigo else ""
        if codigo in por_codigo:
            resultado.duplicados.append(codigo)
        por_codigo[codigo] = Produto(
            id=0, codigo=codigo, descricao=descricao, categoria=categoria_para_descricao(descricao),
            tipo=tipo_da_peca(descricao), marca=col(linha, "MARCA"), referencia=referencia, ean=ean,
            aplicacao=col(linha, "APLICACAO"), preco=_preco(linha[idx["PRECO"]]) if "PRECO" in idx else None,
        )
    resultado.produtos = list(por_codigo.values())
    return resultado
