"""Busca de imagens no DuckDuckGo (ddgs) e download das candidatas.

O domínio NÃO decide se a foto serve (lição do Agrocarreiro: CDN ≠ site, e filtro
eliminatório por fonte jogava fora foto certa). Só bloqueamos fontes que nunca são foto
de produto; 'loja' é apenas um pequeno bônus na pontuação.
"""
from __future__ import annotations

import ipaddress
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
    return [Resultado(b.get("image", ""), b.get("url", ""), b.get("title", "")) for b in brutos if b.get("image")]


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


def url_publica(url: str) -> bool:
    """Só http(s) para host público. As URLs vêm de resultado de busca: nada de file://, localhost ou rede interna."""
    try:
        partes = urlparse(url or "")
    except ValueError:
        return False
    host = (partes.hostname or "").lower()
    if partes.scheme not in ("http", "https") or not host:
        return False
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        return False
    try:
        return ipaddress.ip_address(host).is_global
    except ValueError:
        return True  # nome de domínio


def baixar(url: str, *, timeout: float = 12.0, cliente=None) -> bytes | None:
    """Baixa uma imagem lendo em pedaços e desistindo ao passar de MAX_BYTES.

    Redirecionamentos são seguidos à mão (no máximo MAX_REDIRECIONAMENTOS), conferindo
    `url_publica` a cada salto: um anúncio não pode nos mandar buscar um endereço interno.
    """
    import httpx

    proprio = cliente is None
    if proprio:
        cliente = httpx.Client(headers=_CABECALHOS, follow_redirects=False, timeout=timeout)
    try:
        for _ in range(MAX_REDIRECIONAMENTOS + 1):
            if not url_publica(url):
                return None
            with cliente.stream("GET", url) as resposta:
                if resposta.status_code in (301, 302, 303, 307, 308):
                    url = urljoin(url, resposta.headers.get("location", ""))
                    continue
                tipo = resposta.headers.get("content-type", "").lower()
                if resposta.status_code != 200 or "html" in tipo or "text" in tipo:
                    return None
                declarado = resposta.headers.get("content-length", "")
                if declarado.isdigit() and int(declarado) > MAX_BYTES:
                    return None
                pedacos, total = [], 0
                for pedaco in resposta.iter_bytes(65_536):
                    total += len(pedaco)
                    if total > MAX_BYTES:
                        return None
                    pedacos.append(pedaco)
                return b"".join(pedacos) if total >= MIN_BYTES else None
        return None  # redirecionamentos demais
    except httpx.HTTPError:
        return None
    finally:
        if proprio:
            cliente.close()
