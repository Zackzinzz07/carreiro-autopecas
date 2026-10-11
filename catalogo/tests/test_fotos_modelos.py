import io

import pytest

pytest.importorskip("torch")
pytest.importorskip("open_clip")
pytest.importorskip("easyocr")
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from catalogo.fotos import modelos  # noqa: E402

pytestmark = pytest.mark.skipif(not (modelos.CACHE_MODELOS / "open_clip").exists(),
                                reason="pesos do CLIP não estão em /mnt/dados/cache")


def _png(im) -> bytes:
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture(scope="module")
def visao():
    return modelos.Visao(["car tire", "brake pad", "spark plug"])


def test_ranking_devolve_posicao_lixo_e_primeiro_lugar(visao):
    pneu = Image.new("RGB", (300, 300), "white")
    d = ImageDraw.Draw(pneu)
    d.ellipse((30, 30, 270, 270), fill="black")
    d.ellipse((110, 110, 190, 190), fill="gray")
    rank, lixo, topo = visao.ranking(_png(pneu), "car tire")
    assert isinstance(rank, int) and 1 <= rank <= len(visao.nomes)
    assert isinstance(lixo, bool) and topo in visao.nomes
    assert visao.ranking(_png(pneu), "rotulo que nao existe")[0] is None
    assert len(visao.nomes) == 3 + len(modelos.LIXO)


def test_ocr_le_marca_impressa():
    im = Image.new("RGB", (600, 200), "white")
    fonte = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 90)
    ImageDraw.Draw(im).text((20, 40), "BOSCH", fill="black", font=fonte)
    assert "BOSCH" in modelos.Ocr().ler(_png(im))
