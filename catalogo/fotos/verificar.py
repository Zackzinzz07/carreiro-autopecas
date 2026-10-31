"""Sinais por candidata e a regra de decisão (funções puras, testáveis sem modelos).

Regra (spec, seção 4.3): aprovação automática só quando TODOS os sinais concordam.
Qualquer dúvida vira revisão; imagem inválida ou lixo (CLIP) nem chega à revisão.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from catalogo.fotos.atributos import conflitos, do_anuncio
from catalogo.fotos.dados.marcas import MARCAS
from catalogo.fotos.normalizar import Chave

LIMIAR_RANK_CLIP = 3        # tipo esperado precisa estar entre os 3 primeiros do CLIP
LIMIAR_OCR_MARCA = 0.72     # semelhança mínima entre marca esperada e palavra lida no rótulo
_QUALIFICADORES = frozenset({
    "dianteiro", "traseiro", "superior", "inferior", "externo", "interno", "lado", "direito", "esquerdo",
    "com", "sem", "central", "jogo", "kit", "par", "intermediario", "auxiliar", "lateral",
})
# Tipos em que a marca não aparece legível na foto (fica na lateral do pneu): a marca é garantida por
# título + medida + modelo.
_SEM_ROTULO_LEGIVEL = frozenset({"pneu", "camara"})
# (presente na peça, oposto no título): o oposto no título é conflito MESMO com o próprio junto.
# Anúncio "dianteiro e traseiro" ou "superior inferior" é kit das duas peças (erros R33 e R17 do piloto).
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
    titulo_conflito = any(a in alvo and b in t for a, b in _OPOSTOS)
    titulo_marca = not chave.marca or contem(chave.marca)
    titulo_kit = bool(_KIT.search(titulo)) and not (_PRODUTO_E_KIT & set(chave.peca.split()))
    return {"titulo_peca": titulo_peca, "titulo_veiculo": titulo_veiculo, "titulo_spec": titulo_spec,
            "titulo_conflito": titulo_conflito, "titulo_marca": titulo_marca,
            "titulo_ano": _ano_compativel(chave, titulo), "titulo_kit": titulo_kit,
            "titulo_ano_incerto": _ano_incerto(chave, titulo),
            "conflitos": tuple(conflitos(chave.atributos, do_anuncio(titulo))),
            "titulo_outra_marca": bool(chave.marca) and outra_marca_no_ocr(chave.marca, titulo.upper())}


# Kit/combo/"peça + outra peça" no anúncio de um produto que não é kit: a foto traz peças a mais.
_KIT = re.compile(r"\b(?:kit|combo)\b|\+", re.IGNORECASE)
_PRODUTO_E_KIT = frozenset({"kit", "jogo", "conjunto"})
_ANO_TITULO = re.compile(r"(?<!\d)((?:19[5-9]|20[0-3])\d)(?!\d)")
_FAIXA_TITULO = re.compile(
    r"(?<!\d)((?:19[5-9]|20[0-3])\d)\s*(?:a|à|ao|ate|até|-|–|/)\s*((?:19[5-9]|20[0-3])\d)(?!\d)", re.IGNORECASE)


def anos_do_titulo(titulo: str) -> set[int]:
    """Anos de 4 dígitos citados no anúncio; "2009 a 2013" conta todos os anos do intervalo."""
    anos = {int(a) for a in _ANO_TITULO.findall(titulo)}
    for ini, fim in _FAIXA_TITULO.findall(titulo):
        anos.update(range(int(ini), int(fim) + 1))
    return anos


def _ano_compativel(chave: Chave, titulo: str) -> bool:
    """Falso só quando o anúncio cita anos e NENHUM cai na faixa do produto (outra geração do carro).

    Anúncio sem ano não é reprovado por isso: não dá para negar o que ele não diz.
    """
    ini, fim = chave.faixa
    if ini is None and fim is None:
        return True
    anos = anos_do_titulo(titulo)
    if not anos:
        return True
    return any((ini is None or a >= ini) and (fim is None or a <= fim) for a in anos)


def _ano_incerto(chave: Chave, titulo: str) -> bool:
    """O anúncio cita ano e o produto não: não dá para confirmar a geração (pastilha Corolla GLi com
    foto de Corolla 2019, piloto 2). Decisão de 2026-10-30: zero erro vale mais que aprovação automática."""
    return bool(chave.veiculo) and not chave.anos and bool(anos_do_titulo(titulo))


_TELEFONE = re.compile(r"(?<!\d)\d{4,5}[-.\s]\d{4}(?!\d)")
_PALAVRAS_DE_ANUNCIO = ("WHATS", "ZAP ", "WWW", ".COM", "@", "AUTO PECAS", "AUTO PEÇAS", "AUTOPECAS", "AUTOPEÇAS",
                        "DISTRIBUIDORA", "DDD", "FRETE", "PROMO", "OFERTA", "PARCEL")


def anuncio_na_imagem(texto_ocr: str) -> bool:
    """A imagem traz telefone, site ou propaganda de quem vendeu (erro R14 do piloto)? Não é foto para o nosso catálogo."""
    texto = f"{(texto_ocr or '').upper()} "
    return bool(_TELEFONE.search(texto)) or any(p in texto for p in _PALAVRAS_DE_ANUNCIO)


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
    titulo_ano: bool = False       # anúncio é de ano compatível (ou não cita ano)
    titulo_kit: bool = False       # anúncio de kit/combo para produto que não é kit
    titulo_ano_incerto: bool = False   # anúncio cita ano, produto com carro não cita
    conflitos: tuple[str, ...] = ()    # motor, geração, quantidade ou versão excluída (atributos.py)
    titulo_outra_marca: bool = False   # consumível: o anúncio cita outra marca conhecida
    imagem_anuncio: bool = False   # telefone/site/propaganda de vendedor escrito na imagem
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
    if not s.titulo_ano:
        motivos.append("titulo_ano_fora")
    if s.titulo_kit:
        motivos.append("titulo_kit")
    if s.titulo_ano_incerto:
        motivos.append("titulo_ano_produto_sem_ano")
    motivos.extend(s.conflitos)
    if s.imagem_anuncio:
        motivos.append("imagem_com_texto_de_vendedor")
    # Consumível (stakeholders, 2026-10-30): foto da marca certa ou sem marca aparente serve; outra marca não.
    # Pneu é exceção: a marca fica na lateral, o OCR não confere a foto, então o título precisa citá-la.
    if chave.marca and not s.titulo_marca and chave.peca.split()[0] in _SEM_ROTULO_LEGIVEL:
        motivos.append("titulo_sem_marca")
    if chave.marca and s.ocr_outra_marca:
        motivos.append("ocr_outra_marca")
    if s.titulo_outra_marca:
        motivos.append("titulo_outra_marca")

    pontuacao = (20 * s.titulo_peca + 15 * s.titulo_veiculo + 10 * s.titulo_spec
                 + 15 * (bool(chave.marca) and s.titulo_marca) + 10 * s.ocr_marca
                 + 5 * s.dominio_loja + 5 * s.fundo_branco - 30 * s.titulo_conflito - 30 * s.ocr_outra_marca)
    if s.clip_rank is not None:
        pontuacao += 25 if s.clip_rank == 1 else 15 if s.clip_rank <= LIMIAR_RANK_CLIP else 0
    return Decisao(not motivos, True, int(pontuacao), tuple(motivos))
