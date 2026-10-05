import pytest

from catalogo.categorias import CATEGORIAS, categoria_para_descricao, slug, tipo_da_peca


@pytest.mark.parametrize("desc,esperada", [
    ("AMORT DT GOL G5 08/", "Suspensão e Direção"),
    ("FILTRO OLEO GOL/PARATI AP 1.6", "Filtros"),
    ("PASTILHA FREIO DT UNO 10/", "Freios"),
    ("PNEU 205/65 R15 MAZZINI 94V", "Pneus e Rodas"),
    ("JG JUNTA MOTOR CORSA 1.0 MPFI", "Motor"),          # prefixo JG é ignorado
    ("JUNTA HOMOC DUSTER 1.6", "Câmbio e Embreagem"),    # exceção de duas palavras vence a regra genérica de JUNTA
    ("TAMPA RESERV GASOL PALIO", "Motor"),               # não é arrefecimento
    ("BOMBA DAGUA CORSA 1.0", "Arrefecimento"),
    ("ROLAMENTO INDUSTRIAL 629", "Variados"),
    ("ABRACADEIRA 12MM", "Variados"),
])
def test_categoria(desc, esperada):
    assert categoria_para_descricao(desc) == esperada


def test_toda_categoria_devolvida_esta_na_lista():
    assert categoria_para_descricao("QUALQUER COISA ESTRANHA") in CATEGORIAS


def test_tipo_ignora_prefixo_e_barra():
    assert tipo_da_peca("JG JUNTA MOTOR") == "JUNTA"
    assert tipo_da_peca("BORRACHA/ABRAC 12") == "BORRACHA"


def test_slug():
    assert slug("Suspensão e Direção") == "suspensao-e-direcao"
