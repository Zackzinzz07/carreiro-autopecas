import pytest

pytest.importorskip("ddgs")
import httpx  # noqa: E402
from ddgs.exceptions import DDGSException, RatelimitException  # noqa: E402

from catalogo.fotos import busca  # noqa: E402

_RESOLVER_REAL = busca._enderecos
_DNS_FALSO = {"interno.example": ["10.0.0.7"], "misto.example": ["93.184.216.34", "127.0.0.1"]}


@pytest.fixture(autouse=True)
def dns_de_teste(monkeypatch):
    """Hosts .example (e o 'x' dos testes) resolvem para um IP público fixo; o resto usa o resolvedor real."""
    def resolver(host):
        if host in _DNS_FALSO:
            return _DNS_FALSO[host]
        if host == "x" or host.endswith(".example"):
            return ["93.184.216.34"]
        return _RESOLVER_REAL(host)

    monkeypatch.setattr(busca, "_enderecos", resolver)


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


@pytest.mark.parametrize("url", [
    "https://interno.example/a.jpg",     # nome público que resolve para rede interna
    "https://misto.example/a.jpg",       # um dos endereços é interno: recusa
    "http://2130706433/a.jpg",           # 127.0.0.1 em decimal
    "http://0x7f.0.0.1/a.jpg",           # 127.0.0.1 em hexadecimal
    "http://127.1/a.jpg",                # 127.0.0.1 abreviado
    "https://host-que-nao-existe.invalid/a.jpg",
])
def test_baixar_confere_o_endereco_resolvido_e_nao_so_o_texto_do_host(url):
    def nao_deveria_chamar(req):
        raise AssertionError(f"requisição indevida: {req.url}")

    with httpx.Client(transport=httpx.MockTransport(nao_deveria_chamar)) as cliente:
        assert busca.baixar(url, cliente=cliente) is None


def test_baixar_pede_sem_compressao_e_recusa_resposta_comprimida():
    vistos = []

    def responder(req):
        vistos.append(req.headers.get("accept-encoding"))
        cabecalhos = {"content-type": "image/jpeg"}
        if req.url.path == "/comprimida.jpg":
            cabecalhos["content-encoding"] = "gzip"
        return httpx.Response(200, content=b"\xff" * 5000, headers=cabecalhos)

    with httpx.Client(transport=httpx.MockTransport(responder)) as cliente:
        assert busca.baixar("https://x.example/ok.jpg", cliente=cliente) == b"\xff" * 5000
        assert busca.baixar("https://x.example/comprimida.jpg", cliente=cliente) is None
    assert vistos == ["identity", "identity"]


def test_baixar_desiste_de_servidor_que_pinga_bytes_devagar(monkeypatch):
    relogio = {"t": 0.0}
    monkeypatch.setattr(busca.time, "monotonic", lambda: relogio["t"])

    def gerador():
        for _ in range(50):
            relogio["t"] += 20.0          # cada pedaço "demora" 20 s
            yield b"\xff" * 1000

    def responder(req):
        return httpx.Response(200, content=gerador(), headers={"content-type": "image/jpeg"})

    with httpx.Client(transport=httpx.MockTransport(responder)) as cliente:
        assert busca.baixar("https://x.example/lenta.jpg", cliente=cliente) is None
    assert relogio["t"] <= busca.PRAZO_TOTAL + 40


@pytest.mark.parametrize("url", [
    "http://[", "http://exa mple.example/a.jpg", "https://x.example\\@127.0.0.1/a.jpg",
    "https://x.example:99999/a.jpg", "http://x.example\t@127.0.0.1/", "https://127.0.0.1\\.x.example/a.jpg",
    "http:////127.0.0.1/a.jpg", "\x00", "https://",
])
def test_url_malformada_nao_derruba_e_nunca_alcanca_endereco_interno(url):
    hosts = []

    def responder(req):
        hosts.append((req.url.host, req.headers.get("host", "")))
        return httpx.Response(200, content=b"\xff" * 5000, headers={"content-type": "image/jpeg"})

    with httpx.Client(transport=httpx.MockTransport(responder)) as cliente:
        resultado = busca.baixar(url, cliente=cliente)   # não pode levantar exceção
    assert resultado is None or isinstance(resultado, bytes)
    # só o IP público de teste é alcançado, e sempre em nome de um host .example
    assert all(ip == "93.184.216.34" and nome.split(":")[0].endswith(".example") for ip, nome in hosts), hosts


def test_o_host_validado_e_o_mesmo_que_o_cliente_http_requisita():
    """Validação e requisição usam o MESMO analisador (httpx.URL): não há 'URL vista de dois jeitos'."""
    for url in ("https://x.example/a.jpg", "https://X.Example:443/a.jpg", "http://127.0.0.1/a", "http://[::1]/a"):
        assert busca.url_publica(url) is (httpx.URL(url).host.lower().endswith(".example"))


def test_erro_inesperado_do_cliente_vira_none():
    class ClienteQuebrado:
        def stream(self, *a, **k):
            raise httpx.InvalidURL("url esquisita")

    assert busca.baixar("https://x.example/a.jpg", cliente=ClienteQuebrado()) is None


def test_conecta_no_ip_que_foi_validado_mesmo_se_o_dns_mudar_depois(monkeypatch):
    """DNS rebinding: 1ª resposta pública (passa na conferência), 2ª interna. A conexão usa a 1ª."""
    respostas = iter([["93.184.216.34"], ["127.0.0.1"], ["127.0.0.1"]])
    monkeypatch.setattr(busca, "_enderecos", lambda host: next(respostas))
    vistos = []

    def responder(req):
        vistos.append((req.url.host, req.headers.get("host"), req.extensions.get("sni_hostname")))
        return httpx.Response(200, content=b"\xff" * 5000, headers={"content-type": "image/jpeg"})

    with httpx.Client(transport=httpx.MockTransport(responder)) as cliente:
        assert busca.baixar("https://rebind.example/a.jpg", cliente=cliente) == b"\xff" * 5000
    assert vistos == [("93.184.216.34", "rebind.example", "rebind.example")]


def test_resultado_da_busca_tem_quantidade_e_tamanhos_limitados_por_nos():
    """O limite não pode depender de o buscador respeitar max_results nem de o anúncio ser bem-comportado."""
    exagero = [{"title": "T" * 5000, "image": f"https://cdn.example/{i}.jpg", "url": "https://loja.example/" + "p" * 9000}
               for i in range(50)]
    exagero.insert(0, {"title": "url gigante", "image": "https://cdn.example/" + "a" * 5000, "url": "https://x.example"})
    r = busca.buscar_imagens("x", cliente=Cliente(exagero))
    assert len(r) <= 12
    assert all(len(x.titulo) <= busca.MAX_TITULO and len(x.url_pagina) <= busca.MAX_URL
               and len(x.url_imagem) <= busca.MAX_URL for x in r)
    assert all("aaaa" not in x.url_imagem for x in r)
