"""Sinais por candidata e a regra de decisão (funções puras, testáveis sem modelos).

Regra (spec, seção 4.3): aprovação automática só quando TODOS os sinais concordam.
Qualquer dúvida vira revisão; imagem inválida ou lixo (CLIP) nem chega à revisão.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from catalogo.fotos.dados.marcas import MARCAS
from catalogo.fotos.normalizar import Chave

LIMIAR_RANK_CLIP = 3        # tipo esperado precisa estar entre os 3 primeiros do CLIP
LIMIAR_OCR_MARCA = 0.72     # semelhança mínima entre marca esperada e palavra lida no rótulo
_QUALIFICADORES = frozenset({
    "dianteiro", "traseiro", "superior", "inferior", "externo", "interno", "lado", "direito", "esquerdo",
    "com", "sem", "central", "jogo", "kit", "par", "intermediario", "auxiliar", "lateral",
})
# Tipos em que a marca não aparece legível na foto (fica na lateral do pneu): o OCR não é exigido,
# e a marca é garantida por título + medida + modelo. Em todo o resto, marca citada tem de ser LIDA.
_SEM_ROTULO_LEGIVEL = frozenset({"pneu", "camara"})
# (presente na peça, oposto no título): título com o oposto e sem o próprio = conflito
_OPOSTOS = (("diant", "trase"), ("trase", "diant"), ("direit", "esquerd"), ("esquerd", "direit"),
            ("superior", "inferior"), ("inferior", "superior"))


def _norm(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", sem_acento).strip()


def _radical(palavra: str) -> str:
    """'dianteira'/'dianteiros' → 'dianteir': tolera plural e gênero."""
    for sufixo in ("es", "s"):
        if len(palavra) > 4 and palavra.endswith(sufixo):
            palavra = palavra[: -len(sufixo)]
            break
    if len(palavra) > 4 and palavra[-1] in "ao":
        palavra = palavra[:-1]
    return palavra


def nucleo_da_peca(peca: str) -> list[str]:
    """As duas primeiras palavras que dizem O QUE é a peça (sem posição, lado ou medida)."""
    return [w for w in peca.split()
            if len(w) >= 3 and w not in _QUALIFICADORES and not re.search(r"\d", w)][:2]


def sinais_de_texto(chave: Chave, titulo: str) -> dict[str, bool]:
    t = _norm(titulo)
    radicais = {_radical(p) for p in t.split()}
    compacto = t.replace(" ", "")

    def contem(palavra: str) -> bool:
        p = _norm(palavra).replace(" ", "")
        return bool(p) and (_radical(p) in radicais or (len(p) >= 4 and p in compacto))

    nucleo = nucleo_da_peca(chave.peca)
    titulo_peca = bool(nucleo) and all(contem(p) for p in nucleo)
    titulo_veiculo = (not chave.veiculo or contem(chave.veiculo)
                      or (bool(chave.veiculo_alt) and contem(chave.veiculo_alt)))
    if chave.veiculo:
        titulo_spec = True
    else:
        medidas = [_norm(w).replace(" ", "") for w in chave.peca.split() if re.search(r"\d", w)][:4]
        titulo_spec = all(m in compacto for m in medidas)
    alvo = _norm(f"{chave.peca} {chave.lado}")
    titulo_conflito = any(a in alvo and b in t and a not in t for a, b in _OPOSTOS)
    titulo_marca = not chave.marca or contem(chave.marca)
    return {"titulo_peca": titulo_peca, "titulo_veiculo": titulo_veiculo, "titulo_spec": titulo_spec,
            "titulo_conflito": titulo_conflito, "titulo_marca": titulo_marca}


def _so_alnum(texto: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", texto.upper())


def marca_no_ocr(marca: str, texto_ocr: str) -> bool:
    """Cada palavra da marca aparece no rótulo, aceitando letra trocada pelo OCR."""
    if not marca or not texto_ocr:
        return False
    palavras_ocr = [t for t in re.findall(r"[A-Z0-9]+", texto_ocr.upper()) if len(t) >= 3]
    compacto = _so_alnum(texto_ocr)
    for parte in re.findall(r"[A-Z0-9]+", marca.upper()):
        if parte in compacto:
            continue
        if not any(SequenceMatcher(None, parte, p).ratio() >= LIMIAR_OCR_MARCA for p in palavras_ocr):
            return False
    return True


def outra_marca_no_ocr(marca: str, texto_ocr: str) -> bool:
    """O rótulo mostra, por extenso, outra marca conhecida (ex.: MOTORLUB num produto CRACHI)."""
    if not texto_ocr:
        return False
    palavras = set(re.findall(r"[A-Z0-9-]+", texto_ocr.upper()))
    compacto = _so_alnum(texto_ocr)
    propria = _so_alnum(marca or "")
    for m in MARCAS:
        nome = _so_alnum(m)
        if len(nome) < 4:
            continue  # VOX, ELF, 3M...: curtas demais, o OCR forma por acaso
        if propria and (nome == propria or nome in propria or propria in nome):
            continue
        if m in palavras or ("_" in m and nome in compacto):
            return True
    return False


@dataclass(frozen=True)
class Sinais:
    valida: bool = True
    clip_rank: int | None = None
    clip_top_lixo: bool = False
    titulo_peca: bool = False
    titulo_veiculo: bool = False
    titulo_spec: bool = False
    titulo_conflito: bool = False
    titulo_marca: bool = False
    ocr_marca: bool = False
    ocr_outra_marca: bool = False
    dominio_loja: bool = False
    fundo_branco: bool = False


@dataclass(frozen=True)
class Decisao:
    aprovada: bool
    plausivel: bool
    pontuacao: int
    motivos: tuple[str, ...]


def decidir(chave: Chave, s: Sinais) -> Decisao:
    if not s.valida:
        return Decisao(False, False, 0, ("imagem_invalida",))
    if s.clip_top_lixo:
        return Decisao(False, False, 0, ("clip_lixo",))
    motivos: list[str] = []
    if chave.e_tipo:
        motivos.append("foto_de_tipo_exige_revisao")
    if chave.marca_incerta:
        motivos.append("marca_nao_reconhecida")
    if s.clip_rank is None:
        motivos.append("tipo_sem_rotulo_clip")
    elif s.clip_rank > LIMIAR_RANK_CLIP:
        motivos.append(f"clip_rank_{s.clip_rank}")
    if not s.titulo_peca:
        motivos.append("titulo_sem_peca")
    if not s.titulo_veiculo:
        motivos.append("titulo_sem_veiculo")
    if not s.titulo_spec:
        motivos.append("titulo_sem_medida")
    if s.titulo_conflito:
        motivos.append("titulo_lado_ou_posicao_oposta")
    if chave.marca and not s.titulo_marca:
        motivos.append("titulo_sem_marca")
    if chave.marca and s.ocr_outra_marca:
        motivos.append("ocr_outra_marca")
    if chave.marca and not s.ocr_marca and chave.peca.split()[0] not in _SEM_ROTULO_LEGIVEL:
        motivos.append("ocr_sem_marca")

    pontuacao = (20 * s.titulo_peca + 15 * s.titulo_veiculo + 10 * s.titulo_spec
                 + 15 * (bool(chave.marca) and s.titulo_marca) + 10 * s.ocr_marca
                 + 5 * s.dominio_loja + 5 * s.fundo_branco - 30 * s.titulo_conflito - 30 * s.ocr_outra_marca)
    if s.clip_rank is not None:
        pontuacao += 25 if s.clip_rank == 1 else 15 if s.clip_rank <= LIMIAR_RANK_CLIP else 0
    return Decisao(not motivos, True, int(pontuacao), tuple(motivos))
