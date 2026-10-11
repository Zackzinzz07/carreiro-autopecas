import pytest

pytest.importorskip("ddgs")
import httpx  # noqa: E402
from ddgs.exceptions import DDGSException, RatelimitException  # noqa: E402

from catalogo.fotos import busca  # noqa: E402


class Cliente:
    def __init__(self, resposta=None, erro=None):
        self.resposta, self.erro, self.chamadas = resposta or [], erro, []

    def images(self, consulta, **kwargs):
        self.chamadas.append((consulta, kwargs))
        if self.erro:
            raise self.erro
        return self.resposta


def test_converte_resultados_e_busca_no_brasil():
    c = Cliente([
        {"title": "Pastilha Freio Agile", "image": "https://http2.mlstatic.com/a.jpg",
         "url": "https://produto.mercadolivre.com.br/MLB-1"},
        {"title": "sem url de imagem", "image": "", "url": "https://x"},
    ])
    assert busca.buscar_imagens("pastilha freio agile", cliente=c) == [busca.Resultado(
        "https://http2.mlstatic.com/a.jpg", "https://produto.mercadolivre.com.br/MLB-1", "Pastilha Freio Agile")]
    consulta, kwargs = c.chamadas[0]
    assert consulta == "pastilha freio agile" and kwargs["region"] == "br-pt" and kwargs["max_results"] == 12


def test_sem_resultado_vira_lista_vazia_e_bloqueio_vira_excecao():
    assert busca.buscar_imagens("x", cliente=Cliente(erro=DDGSException("No results found."))) == []
    with pytest.raises(busca.BuscaBloqueada):
        busca.buscar_imagens("x", cliente=Cliente(erro=RatelimitException("202 Ratelimit")))


def test_dominios_de_loja_e_bloqueados():
    ml = busca.Resultado("https://http2.mlstatic.com/D_1.jpg", "https://produto.mercadolivre.com.br/x", "t")
    pin = busca.Resultado("https://i.pinimg.com/a.jpg", "https://br.pinterest.com/pin/1", "t")
    assert busca.eh_loja(ml) and not busca.bloqueado(ml)
    assert busca.bloqueado(pin) and not busca.eh_loja(pin)
    assert busca.dominio("https://Http2.MLSTATIC.com/x") == "http2.mlstatic.com"


def test_baixar_aceita_so_imagem_de_tamanho_razoavel():
    def responder(req):
        caminho = req.url.path
        if caminho == "/foto.jpg":
            return httpx.Response(200, content=b"\xff" * 5000, headers={"content-type": "image/jpeg"})
        if caminho == "/pagina":
            return httpx.Response(200, content=b"<html>" * 1000, headers={"content-type": "text/html"})
        if caminho == "/pequena.jpg":
            return httpx.Response(200, content=b"\xff" * 100, headers={"content-type": "image/jpeg"})
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(responder)) as cliente:
        assert busca.baixar("https://x/foto.jpg", cliente=cliente) == b"\xff" * 5000
        for url in ("https://x/pagina", "https://x/pequena.jpg", "https://x/nada.jpg"):
            assert busca.baixar(url, cliente=cliente) is None
