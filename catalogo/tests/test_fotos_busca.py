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


def test_dominio_e_conferido_pelo_host_e_nao_por_trecho_do_texto():
    falso = busca.Resultado("https://mlstatic.com@site-ruim.example/a.jpg", "https://mlstatic.com.site-ruim.example/x", "t")
    assert not busca.eh_loja(falso)
    sub = busca.Resultado("https://http2.mlstatic.com:443/a.jpg", "https://x.example/p", "t")
    assert busca.eh_loja(sub)
    assert busca.dominio("https://usuario:senha@Loja.Example:8443/x") == "loja.example"
    assert busca.bloqueado(busca.Resultado("https://br.pinterest.com/a.jpg", "", "t"))


@pytest.mark.parametrize("url", [
    "file:///etc/passwd", "ftp://x.example/a.jpg", "http://localhost/a.jpg", "http://127.0.0.1:8000/a.jpg",
    "http://192.168.0.10/a.jpg", "http://10.0.0.5/a.jpg", "http://169.254.169.254/latest", "http://[::1]/a.jpg", "",
])
def test_baixar_recusa_esquemas_e_enderecos_internos_sem_requisitar(url):
    def nao_deveria_chamar(req):
        raise AssertionError(f"requisição indevida: {req.url}")

    with httpx.Client(transport=httpx.MockTransport(nao_deveria_chamar)) as cliente:
        assert busca.baixar(url, cliente=cliente) is None


def test_baixar_para_de_ler_quando_passa_do_limite():
    lidos = []

    def gerador():
        for _ in range(100):  # 100 MB se alguém lesse tudo
            lidos.append(1)
            yield b"\xff" * 1_000_000

    def responder(req):
        if req.url.path == "/mentiroso.jpg":   # sem Content-Length, corpo enorme
            return httpx.Response(200, content=gerador(), headers={"content-type": "image/jpeg"})
        return httpx.Response(200, content=b"\xff" * 10, headers={"content-type": "image/jpeg",
                                                                  "content-length": "99999999"})

    with httpx.Client(transport=httpx.MockTransport(responder)) as cliente:
        assert busca.baixar("https://x.example/mentiroso.jpg", cliente=cliente) is None
        assert len(lidos) <= 14   # parou logo depois de 12 MB
        assert busca.baixar("https://x.example/declarado.jpg", cliente=cliente) is None


def test_baixar_segue_redirecionamento_publico_e_recusa_o_interno():
    def responder(req):
        if req.url.path == "/vai":
            return httpx.Response(302, headers={"location": "https://cdn.example/foto.jpg"})
        if req.url.path == "/foto.jpg":
            return httpx.Response(200, content=b"\xff" * 5000, headers={"content-type": "image/jpeg"})
        if req.url.path == "/armadilha":
            return httpx.Response(302, headers={"location": "http://127.0.0.1:8000/admin"})
        if req.url.path == "/laco":
            return httpx.Response(302, headers={"location": "/laco"})
        raise AssertionError(f"requisição indevida: {req.url}")

    with httpx.Client(transport=httpx.MockTransport(responder)) as cliente:
        assert busca.baixar("https://x.example/vai", cliente=cliente) == b"\xff" * 5000
        assert busca.baixar("https://x.example/armadilha", cliente=cliente) is None
        assert busca.baixar("https://x.example/laco", cliente=cliente) is None
