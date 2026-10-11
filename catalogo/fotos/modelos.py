"""Modelos locais de visão: CLIP zero-shot (qual tipo de peça? é lixo?) e OCR (marca no rótulo).

Medido no spike de 2026-10-05: o CLIP separou 10/10 imagens ruins (placeholder, desenho,
peça errada) e pôs o tipo certo no top 3 em 79% das fotos boas. Pesado: importe só quando for usar.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

# O disco principal tem pouco espaço; os pesos já estão aqui (compartilhados com o Agrocarreiro).
CACHE_MODELOS = Path("/mnt/dados/cache")
LIXO: dict[str, str] = {
    "LIXO:carro": "a photo of a car",
    "LIXO:desenho": "a technical drawing with dimensions",
    "LIXO:placeholder": "a gray placeholder icon meaning image not available",
    "LIXO:caixa": "a cardboard product box",
    "LIXO:banner": "an advertisement banner with text",
}


class Visao:
    def __init__(self, rotulos: list[str], cache_dir: Path = CACHE_MODELOS):
        import open_clip
        import torch

        self._torch = torch
        self.modelo, _, self.preparo = open_clip.create_model_and_transforms(
            "ViT-B-32-quickgelu", pretrained="openai", cache_dir=str(cache_dir / "open_clip"))
        self.modelo.eval()
        tokenizador = open_clip.get_tokenizer("ViT-B-32-quickgelu")
        self.nomes = list(rotulos) + list(LIXO)
        prompts = [f"a product photo of a {r}" for r in rotulos] + list(LIXO.values())
        with torch.no_grad():
            textos = self.modelo.encode_text(tokenizador(prompts))
            self.textos = textos / textos.norm(dim=-1, keepdim=True)

    def ranking(self, dados: bytes, tipo_en: str) -> tuple[int | None, bool, str]:
        from PIL import Image

        imagem = Image.open(BytesIO(dados)).convert("RGB")
        with self._torch.no_grad():
            f = self.modelo.encode_image(self.preparo(imagem).unsqueeze(0))
            f = f / f.norm(dim=-1, keepdim=True)
            probabilidades = (100 * f @ self.textos.T).softmax(-1)[0]
        ordem = [self.nomes[i] for i in probabilidades.argsort(descending=True).tolist()]
        rank = ordem.index(tipo_en) + 1 if tipo_en and tipo_en in self.nomes else None
        return rank, ordem[0].startswith("LIXO:"), ordem[0]


class Ocr:
    def __init__(self, cache_dir: Path = CACHE_MODELOS):
        import easyocr

        # quantize=False: a CPU desta máquina só tem AVX; o caminho quantizado morre com SIGILL.
        self.leitor = easyocr.Reader(["pt", "en"], gpu=False, verbose=False, quantize=False,
                                     model_storage_directory=str(cache_dir / "easyocr"))

    def ler(self, dados: bytes) -> str:
        import numpy as np
        from PIL import Image

        imagem = Image.open(BytesIO(dados)).convert("RGB")
        imagem.thumbnail((1200, 1200))
        return " ".join(self.leitor.readtext(np.array(imagem), detail=0)).upper()
