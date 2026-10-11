"""Busca de imagens no DuckDuckGo (ddgs) e download das candidatas.

O domínio NÃO decide se a foto serve (lição do Agrocarreiro: CDN ≠ site, e filtro
eliminatório por fonte jogava fora foto certa). Só bloqueamos fontes que nunca são foto
de produto; 'loja' é apenas um pequeno bônus na pontuação.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

DOMINIOS_BLOQUEADOS = (
    "pinterest.", "pinimg.com", "facebook.", "fbsbx.com", "instagram.", "youtube.", "ytimg.com", "tiktok.",
    "blogspot.", "wordpress.", "shutterstock.", "istockphoto.", "alamy.", "dreamstime.", "freepik.",
    "123rf.", "gettyimages.", "vecteezy.", "pngtree.", "pngwing.", "wallpaper", "clipart",
)
DOMINIOS_LOJA = (
    "mlstatic.com", "mercadolivre.com.br", "mercadolibre.", "magazineluiza.", "mlcdn.com.br", "amazon.com.br",
    "media-amazon.com", "shopee.", "americanas.", "casasbahia.", "canaldapeca.", "hipervarejo.", "autozone.",
    "dpaschoal.", "pecaagora.", "connectparts.", "jocar.", "rodaparts.",
)
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
    return urlparse(url or "").netloc.lower()


def _dominios(r: Resultado) -> str:
    return f"{dominio(r.url_imagem)} {dominio(r.url_pagina)}"


def bloqueado(r: Resultado) -> bool:
    return any(b in _dominios(r) for b in DOMINIOS_BLOQUEADOS)


def eh_loja(r: Resultado) -> bool:
    return any(d in _dominios(r) for d in DOMINIOS_LOJA)


def baixar(url: str, *, timeout: float = 12.0, cliente=None) -> bytes | None:
    import httpx

    try:
        if cliente is None:
            with httpx.Client(headers=_CABECALHOS, follow_redirects=True, timeout=timeout) as c:
                resposta = c.get(url)
        else:
            resposta = cliente.get(url)
    except httpx.HTTPError:
        return None
    tipo = resposta.headers.get("content-type", "").lower()
    if resposta.status_code != 200 or "html" in tipo or "text" in tipo:
        return None
    if not 3_000 <= len(resposta.content) <= 12_000_000:
        return None
    return resposta.content
