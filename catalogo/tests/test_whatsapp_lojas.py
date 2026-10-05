from urllib.parse import parse_qs, urlparse

from catalogo.lojas import LOJAS, MATRIZ
from catalogo.models import Produto
from catalogo.whatsapp import link_pedido

P = Produto(id=1, codigo="008087", descricao="ABRACADEIRA 1/2 X 62", categoria="Variados")


def test_cinco_lojas_com_uma_matriz_e_numeros_validos():
    assert len(LOJAS) == 5 and MATRIZ.cidade == "Poranga"
    assert all(l.whatsapp.isdigit() and l.whatsapp.startswith("55") and len(l.whatsapp) == 13 for l in LOJAS)


def test_link_usa_numero_da_loja_e_texto_codificado():
    for loja in LOJAS:
        url = urlparse(link_pedido(P, loja))
        assert url.netloc == "wa.me" and url.path == f"/{loja.whatsapp}"
        texto = parse_qs(url.query)["text"][0]
        assert "ABRACADEIRA 1/2 X 62" in texto and "008087" in texto and "R$" not in texto


def test_link_inclui_preco_quando_existe():
    com_preco = Produto(**{**P.__dict__, "preco": 12.5})
    assert "R$ 12,50" in parse_qs(urlparse(link_pedido(com_preco, MATRIZ)).query)["text"][0]
