import io

import pytest

pytest.importorskip("PIL")
from PIL import Image, ImageDraw  # noqa: E402

from catalogo.fotos import imagem  # noqa: E402


def _png(tamanho=(300, 300), cor="white", desenho=True, modo="RGB") -> bytes:
    im = Image.new(modo, tamanho, cor)
    if desenho:
        ImageDraw.Draw(im).ellipse((60, 60, tamanho[0] - 60, tamanho[1] - 60), fill="red")
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def test_packshot_vira_webp_quadrado_com_fundo_branco():
    proc, motivo = imagem.processar(_png())
    assert proc is not None, motivo
    assert proc.webp[:4] == b"RIFF" and proc.webp[8:12] == b"WEBP"
    assert proc.fundo_branco is True
    assert Image.open(io.BytesIO(proc.webp)).size == (imagem.LADO, imagem.LADO)


def test_png_transparente_fica_com_fundo_branco_e_nao_preto():
    proc, _ = imagem.processar(_png(cor=(0, 0, 0, 0), modo="RGBA"))
    assert proc is not None and proc.fundo_branco is True
    # (60, 60) na tela = (10, 10) na imagem original, que era transparente
    fora_da_peca = Image.open(io.BytesIO(proc.webp)).convert("RGB").getpixel((60, 60))
    assert min(fora_da_peca) > 240


def test_cena_com_cantos_diferentes_nao_e_fundo_branco():
    im = Image.new("RGB", (300, 300), "white")
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 150, 150), fill="black")
    d.rectangle((150, 150, 300, 300), fill="blue")
    buf = io.BytesIO()
    im.save(buf, "PNG")
    proc, _ = imagem.processar(buf.getvalue())
    assert proc is not None and proc.fundo_branco is False


@pytest.mark.parametrize("dados,trecho", [(b"", "insuficientes"), (b"isto nao e imagem" * 100, "inválida")])
def test_rejeita_bytes_ruins(dados, trecho):
    proc, motivo = imagem.processar(dados)
    assert proc is None and trecho in motivo


def test_rejeita_pequena_e_proporcao_absurda():
    assert imagem.processar(_png((100, 100), desenho=False))[0] is None
    assert imagem.processar(_png((900, 300)))[0] is None


def test_termo_placeholder_e_sha1():
    assert imagem.termo_placeholder("Imagem indisponível")
    assert imagem.termo_placeholder("https://x.com/no_image.png")
    assert not imagem.termo_placeholder("Pastilha Freio Dianteira Agile")
    assert imagem.sha1(b"abc") == "a9993e364706816aba3e25717850c26c9cd0d89d"
