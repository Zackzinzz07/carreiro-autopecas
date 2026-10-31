"""Busca de imagens no DuckDuckGo (ddgs) e download das candidatas.

O domínio NÃO decide se a foto serve (lição do Agrocarreiro: CDN ≠ site, e filtro
eliminatório por fonte jogava fora foto certa). Só bloqueamos fontes que nunca são foto
de produto; 'loja' é apenas um pequeno bônus na pontuação.
"""
from __future__ import annotations

import ipaddress
import socket
import time
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

# Bloqueio por trecho do HOST (errar para mais aqui é seguro: só descarta candidata).
DOMINIOS_BLOQUEADOS = (
    "pinterest.", "pinimg.com", "facebook.", "fbsbx.com", "instagram.", "youtube.", "ytimg.com", "tiktok.",
    "blogspot.", "wordpress.", "shutterstock.", "istockphoto.", "alamy.", "dreamstime.", "freepik.",
    "123rf.", "gettyimages.", "vecteezy.", "pngtree.", "pngwing.", "wallpaper", "clipart",
)
# Loja dá bônus na pontuação, então o casamento é exato: o host é o domínio ou um subdomínio dele.
DOMINIOS_LOJA = (
    "mlstatic.com", "mercadolivre.com.br", "mercadolibre.com", "magazineluiza.com.br", "mlcdn.com.br",
    "amazon.com.br", "media-amazon.com", "shopee.com.br", "americanas.com.br", "casasbahia.com.br",
    "canaldapeca.com.br", "hipervarejo.com.br", "autozone.com.br", "dpaschoal.com.br", "pecaagora.com",
    "connectparts.com.br", "jocar.com.br", "rodaparts.com.br",
)
MIN_BYTES = 3_000
MAX_BYTES = 12_000_000
MAX_REDIRECIONAMENTOS = 3
PRAZO_TOTAL = 10.0  # segundos por download, somando redirecionamentos (miniatura que demora >10s travou)
MAX_TITULO = 300    # caracteres guardados do título do anúncio
MAX_URL = 2000
_CABECALHOS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                             "Chrome/126.0 Safari/537.36"}


class BuscaBloqueada(Exception):
    """DuckDuckGo recusou/limitou a busca. O grupo deve continuar pendente."""


@dataclass(frozen=True)
class Resultado:
    url_imagem: str
    url_pagina: str
    titulo: str


def buscar_imagens(consulta: str, *, max_resultados: int = 12, cliente=None) -> list[Resultado]:
    from ddgs.exceptions import DDGSException, RatelimitException, TimeoutException

    if cliente is None:
        from ddgs import DDGS

        cliente = DDGS()
    try:
        brutos = cliente.images(consulta, region="br-pt", safesearch="moderate", max_results=max_resultados)
    except (RatelimitException, TimeoutException) as erro:
        raise BuscaBloqueada(str(erro)) from erro
    except DDGSException as erro:
        if "no results" in str(erro).lower():
            return []
        raise BuscaBloqueada(str(erro)) from erro
    # Os limites são aplicados aqui, não confiados ao buscador nem ao anúncio.
    resultados = []
    for b in list(brutos)[:max_resultados]:
        url_imagem = str(b.get("image") or "")
        if not url_imagem or len(url_imagem) > MAX_URL:
            continue
        resultados.append(Resultado(url_imagem, str(b.get("url") or "")[:MAX_URL], str(b.get("title") or "")[:MAX_TITULO]))
    return resultados


def dominio(url: str) -> str:
    """Host da URL, sem usuário/senha e sem porta ('https://a.com@b.com/x' → 'b.com')."""
    try:
        return (urlparse(url or "").hostname or "").lower()
    except ValueError:
        return ""


def _hosts(r: Resultado) -> tuple[str, str]:
    return dominio(r.url_imagem), dominio(r.url_pagina)


def bloqueado(r: Resultado) -> bool:
    return any(b in host for host in _hosts(r) for b in DOMINIOS_BLOQUEADOS)


def eh_loja(r: Resultado) -> bool:
    return any(host == d or host.endswith("." + d) for host in _hosts(r) if host for d in DOMINIOS_LOJA)


def _enderecos(host: str) -> list[str]:
    """IPs para os quais o host resolve, do jeito que o sistema resolveria ao conectar.

    Cobre também as grafias numéricas que o cliente HTTP aceita mas `ipaddress` não
    ("2130706433", "0x7f.0.0.1", "127.1" são todas 127.0.0.1). Lista vazia = não resolve.
    """
    try:
        return sorted({info[4][0] for info in socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)})
    except (OSError, UnicodeError):
        return []


def _analisar(url):
    """URL do jeito que o cliente HTTP a entende (httpx.URL), ou None se ele não a aceita.

    Validar com um analisador e requisitar com outro deixaria uma URL malformada ser "vista de
    dois jeitos". Por isso a conferência usa o objeto que depois é entregue ao cliente.
    """
    import httpx

    if isinstance(url, httpx.URL):
        return url
    try:
        return httpx.URL(url or "")
    except (httpx.InvalidURL, ValueError, TypeError):
        return None


def _ip_publico(url) -> str | None:
    """IP público para onde a URL aponta, ou None se ela não pode ser buscada.

    Só http(s), e TODOS os endereços resolvidos precisam ser públicos (nada de file://, localhost
    ou rede interna, nem por nome que resolva para dentro). Quem chama conecta NESTE IP: assim
    não existe intervalo em que o DNS possa responder outra coisa entre conferir e conectar, e
    o nome resolvido é o mesmo (forma ASCII/IDNA do httpx) que seria usado na conexão.
    """
    analisada = _analisar(url)
    if analisada is None or analisada.scheme not in ("http", "https"):
        return None
    try:
        host = analisada.raw_host.decode("ascii").lower()
    except UnicodeDecodeError:
        return None
    if not host or host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        return None
    try:
        ips = [ipaddress.ip_address(e.split("%")[0]) for e in _enderecos(host)]
    except ValueError:
        return None
    if not ips or not all(ip.is_global for ip in ips):
        return None
    return str(next((ip for ip in ips if ip.version == 4), ips[0]))


def url_publica(url) -> bool:
    return _ip_publico(url) is not None


def baixar(url: str, *, timeout: float = 6.0, cliente=None) -> bytes | None:
    """Baixa uma imagem com teto de bytes, de tempo e de redirecionamentos. Nunca levanta exceção:
    URL ou resposta estranha vira None (uma candidata a menos), para não derrubar o lote.

    - Lê os bytes como chegam e desiste ao passar de MAX_BYTES. Pede sem compressão e recusa
      resposta comprimida: descomprimir é o que deixaria poucos KB virarem centenas de MB.
    - PRAZO_TOTAL vale para o download inteiro (o timeout do cliente é só por leitura).
    - Redirecionamentos são seguidos à mão; cada salto é conferido e conectado pelo IP validado.
    """
    import httpx

    inicio = time.monotonic()
    proprio = cliente is None
    try:
        if proprio:
            cliente = httpx.Client(headers=_CABECALHOS, follow_redirects=False, timeout=timeout)
        atual = _analisar(url)
        for _ in range(MAX_REDIRECIONAMENTOS + 1):
            ip = _ip_publico(atual) if atual is not None else None
            if ip is None:
                return None
            # Conecta no IP conferido; o nome do site vai no cabeçalho Host e no SNI (certificado).
            nome = atual.raw_host.decode("ascii")
            cabecalhos = {"Host": atual.netloc.decode("ascii"), "Accept-Encoding": "identity"}
            extensoes = {"sni_hostname": nome} if nome != ip else {}
            with cliente.stream("GET", atual.copy_with(host=ip), headers=cabecalhos, extensions=extensoes) as resposta:
                if resposta.status_code in (301, 302, 303, 307, 308):
                    atual = _analisar(atual.join(resposta.headers.get("location", "")))
                    continue
                tipo = resposta.headers.get("content-type", "").lower()
                if resposta.status_code != 200 or "html" in tipo or "text" in tipo:
                    return None
                if resposta.headers.get("content-encoding", "identity").strip().lower() not in ("", "identity"):
                    return None
                declarado = resposta.headers.get("content-length", "")
                if declarado.isdigit() and int(declarado) > MAX_BYTES:
                    return None
                pedacos, total = [], 0
                # Sem tamanho de pedaço: cada leitura da rede passa pelo teste de prazo (com tamanho fixo
                # o httpx só entrega ao juntar o pedaço inteiro, e um servidor lento escaparia do prazo).
                # Resposta comprimida já foi recusada acima, então isto são os bytes crus.
                for pedaco in resposta.iter_bytes():
                    total += len(pedaco)
                    if total > MAX_BYTES or time.monotonic() - inicio > PRAZO_TOTAL:
                        return None
                    pedacos.append(pedaco)
                return b"".join(pedacos) if total >= MIN_BYTES else None
        return None  # redirecionamentos demais
    except (httpx.HTTPError, httpx.InvalidURL, httpx.StreamError, ValueError, OSError, UnicodeError):
        return None
    finally:
        if proprio and cliente is not None:
            cliente.close()
