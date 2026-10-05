import pytest

from catalogo.categorias import categoria_para_descricao, tipo_da_peca
from catalogo.db import conectar, criar_schema, upsert_produto
from catalogo.models import Produto

AMOSTRA = [
    ("000001", "AMORT DT GOL G5 08/", "", ""),
    ("000002", "AMORT TS CELTA 01/ CORSA 95/", "000099", ""),
    ("000003", "FILTRO OLEO GOL/PARATI AP 1.6", "", "7891799419370"),
    ("000004", "PASTILHA FREIO DT UNO 10/ MOBI", "", ""),
    ("000005", "PNEU 205/65 R15 MAZZINI 94V", "", ""),
]


@pytest.fixture
def conn():
    c = conectar(":memory:")
    criar_schema(c)
    for i, (codigo, desc, ref, ean) in enumerate(AMOSTRA, start=1):
        upsert_produto(c, Produto(id=0, codigo=codigo, descricao=desc, categoria=categoria_para_descricao(desc),
                                  tipo=tipo_da_peca(desc), referencia=ref, ean=ean))
    c.commit()
    yield c
    c.close()
