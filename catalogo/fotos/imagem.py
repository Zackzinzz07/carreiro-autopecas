"""Validação e padronização das fotos candidatas (WebP 400x400 sobre fundo branco).

Adaptado de Agrocarreiro/catalogo/imagens.py. Aqui só se barra defeito técnico;
quem decide se a foto é da peça certa é `verificar.decidir`.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from io import BytesIO

LADO = 400
QUALIDADE = 80
PESO_ALVO = 38_000  # bytes
LADO_MINIMO = 140
PROPORCAO_MAXIMA = 2.1
VARIACAO_MAXIMA_CANTOS = 45
# As imagens vêm de sites desconhecidos: só os formatos comuns de anúncio e um teto de pixels,
# conferido pelo cabeçalho ANTES de decodificar (uma "bomba" de poucos KB declara bilhões de pixels).
FORMATOS = ("JPEG", "PNG", "WEBP")
MAX_PIXELS = 40_000_000

_PLACEHOLDER = re.compile(
    r"sem[\s_-]*imagem|indispon[ií]vel|no[\s_-]*image|not[\s_-]*available"
    r"|imagem[\s_-]*n[ãa]o[\s_-]*dispon|placeholder",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Processada:
    webp: bytes
    fundo_branco: bool  # a ORIGINAL tinha fundo uniforme (packshot)


def termo_placeholder(texto: str) -> bool:
    """Título/URL que denuncia imagem de 'indisponível' antes de baixar."""
    return bool(_PLACEHOLDER.search(texto or ""))


def sha1(dados: bytes) -> str:
    return hashlib.sha1(dados).hexdigest()


class ImagemRecusada(ValueError):
    """Bytes que não vamos decodificar: formato fora da lista, grande demais ou corrompido."""


def abrir(dados: bytes):
    """Abre bytes vindos da internet com os limites acima. Levanta ImagemRecusada."""
    from PIL import Image

    try:
        imagem = Image.open(BytesIO(dados), formats=FORMATOS)
    except Exception as erro:
        raise ImagemRecusada(f"imagem inválida ({type(erro).__name__})") from erro
    largura, altura = imagem.size
    if largura * altura > MAX_PIXELS:
        raise ImagemRecusada(f"grande demais ({largura}x{altura})")
    try:
        imagem.load()
    except Exception as erro:
        raise ImagemRecusada(f"imagem inválida ({type(erro).__name__})") from erro
    return imagem


def _fundo_uniforme(imagem) -> bool:
    """Os quatro cantos (blocos 4x4, ~5% para dentro) têm a mesma cor?"""
    largura, altura = imagem.size
    inset = max(6, min(largura, altura) // 20)
    bloco = 4
    rgb = imagem.convert("RGB")
    cantos = ((inset, inset), (largura - inset - bloco, inset),
              (inset, altura - inset - bloco), (largura - inset - bloco, altura - inset - bloco))
    amostras = []
    for x, y in cantos:
        x = max(0, min(x, largura - bloco))
        y = max(0, min(y, altura - bloco))
        pixels = [rgb.getpixel((x + dx, y + dy)) for dx in range(bloco) for dy in range(bloco)]
        amostras.append(tuple(sum(canal) // len(pixels) for canal in zip(*pixels)))
    return all(
        max(a[c] for a in amostras) - min(a[c] for a in amostras) <= VARIACAO_MAXIMA_CANTOS for c in range(3)
    )


def processar(dados: bytes) -> tuple[Processada | None, str]:
    if not dados or len(dados) < 500:
        return None, "dados insuficientes (< 500 bytes)"
    from PIL import Image

    try:
        imagem = abrir(dados)
    except ImagemRecusada as erro:
        return None, str(erro)

    largura, altura = imagem.size
    if min(largura, altura) < LADO_MINIMO:
        return None, f"pequena demais ({largura}x{altura})"
    if max(largura, altura) / min(largura, altura) > PROPORCAO_MAXIMA:
        return None, f"proporção inadequada ({largura}x{altura})"

    if imagem.mode in ("RGBA", "LA") or (imagem.mode == "P" and "transparency" in imagem.info):
        # PNG transparente: convert("RGB") direto deixaria o fundo PRETO
        fundo = Image.new("RGBA", imagem.size, (255, 255, 255, 255))
        fundo.alpha_composite(imagem.convert("RGBA"))
        imagem = fundo

    fundo_branco = _fundo_uniforme(imagem)
    imagem = imagem.convert("RGB")
    imagem.thumbnail((LADO, LADO), Image.LANCZOS)
    tela = Image.new("RGB", (LADO, LADO), (255, 255, 255))
    tela.paste(imagem, ((LADO - imagem.width) // 2, (LADO - imagem.height) // 2))

    for qualidade in (QUALIDADE, 70, 60):
        buffer = BytesIO()
        tela.save(buffer, "WEBP", quality=qualidade, method=6)
        if buffer.tell() <= PESO_ALVO or qualidade == 60:
            return Processada(buffer.getvalue(), fundo_branco), f"webp q{qualidade} {buffer.tell() // 1024}KB"
    return None, "falha na compressão"
