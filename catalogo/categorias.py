# catalogo/categorias.py
"""Classificação de peças em categorias a partir da descrição.

A planilha do cliente não tem coluna de categoria. Ela é INFERIDA aqui pela
descrição (normalizada, sem acento, maiúscula). As regras rodam em ordem e a
primeira que casa vence; o que não casa cai em "Variados".

Para ajustar: edite `_REGRAS` (regras específicas primeiro, genéricas depois) e
rode `python -m catalogo.sync.importar` para ver o efeito antes de gravar.
"""
from __future__ import annotations

import re
import unicodedata

CATEGORIAS = [
    "Motor",
    "Câmbio e Embreagem",
    "Suspensão e Direção",
    "Freios",
    "Elétrica e Iluminação",
    "Distribuição e Correias",
    "Arrefecimento",
    "Filtros",
    "Cabine e Carroceria",
    "Pneus e Rodas",
    "Lubrificantes e Químicos",
    "Variados",
]

# Prefixos que apenas agrupam ("JG JUNTA MOTOR...") e não dizem o tipo da peça.
_PREFIXOS_NEUTROS = {"JG", "KIT", "CJ", "CONJ", "JOGO", "KT", "INATIVO"}


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento.upper()).strip()


def tipo_da_peca(descricao: str) -> str:
    """Primeira palavra significativa da descrição (ex.: 'FILTRO', 'AMORT')."""
    palavras = re.split(r"[\s/]+", normalizar(descricao))
    palavras = [p for p in palavras if p]
    while len(palavras) > 1 and palavras[0] in _PREFIXOS_NEUTROS:
        palavras = palavras[1:]
    return palavras[0] if palavras else ""


def _r(*padroes: str) -> re.Pattern[str]:
    return re.compile("|".join(padroes))


# (categoria, regex sobre a descrição normalizada). Ordem importa.
_REGRAS: list[tuple[str, re.Pattern[str]]] = [
    # --- exceções de várias palavras que precisam vencer as regras genéricas ---
    ("Motor", _r(
        r"^TAMPA RESERV (GASOL|COMB)", r"^MANGOTE (FILTRO|AR|ADM)", r"^CABO ACEL", r"^BOMBA (COMB|OLEO)", r"^COXIM MT",
        r"^BUCHA (MT|TUCHO)", r"^INTERRUPTOR OLEO",
    )),
    ("Pneus e Rodas", _r(r"^(PNEU|CALOTA|CALOTINHA|CAMARA)\b", r"^(PARAFUSO|PARAF|PORCA|ARRUELA) RODA")),
    ("Filtros", _r(r"^FILTRO\b", r"^SUPORTE FILTRO", r"^MANGUEIRA FILT")),
    ("Lubrificantes e Químicos", _r(
        r"^(OLEO|ADITIVO|GRAXA|TINTA|SILICONE|DESCARBONIZANTE|LUBRIFICANTE|THINNER|COLA|CERA|ANTIFERRUGEM|DESENGRIPANTE|"
        r"AROMATIZANTE|MASSA|ADESIVO|LIXA|FITA|ESTOPA|GRAFITE|LIQUIDO|PRIMER|PASTA)\b", r"^ANTI ",
    )),
    ("Freios", _r(
        r"^(PASTILHA|SAPATA|TAMBOR|LONA|PINCA|SERVO|CALCO)\b", r"^DISCO FREIO", r"^CILINDRO (RODA|MESTRE|MESTR)\b",
        r"^(CABO|MANGUEIRA|FLEXIVEL) FREIO", r"^MOLA (PASTILHA|SAP|PATIM)", r"^REPARO (PINCA|CIL|CX FREIO)",
        r"^ALAVANCA FREIO", r"^BORRACHA (CIL|PINCA)",
    )),
    ("Câmbio e Embreagem", _r(
        r"^(EMBR|EMBREAGEM|TRIZETA|SEMI|COIFA|CRUZETA|GARFO|CATRACA|PINHAO|COROA|ENGR|ENGRENAGEM|ACOPLAMENTO|TRAMBULADOR)\b",
        r"^ATUADOR (MARCHA|HIDR|GARFO)", r"^CILINDRO (AUX|EMBR|ACION)", r"^CABO (EMBR|ENGAT)", r"^COXIM CAMBIO",
        r"^JUNTA (HOMOC|DESLIZANTE)", r"^FLANGE (CAMBIO|MODULO|MOD)\b", r"^RETENTOR (SAIDA|TRANSM|CAMBIO|CAIXA)",
        r"^ROLAMENTO (CARD|EMBR)", r"^REPARO (ALAV|CX)", r"^BUCHA (ALAV|TRAMB)", r"^ALAVANCA (CAMBIO|MARCHA)",
    )),
    ("Distribuição e Correias", _r(
        r"^(CORREIA|CORR|TENSOR|POLIA|CORRENTE|ROLETE)\b", r"^ROLAMENTO (CORREIA|CORR|TENSOR)", r"^TAMPA (DISTR|CORREIA)",
    )),
    ("Arrefecimento", _r(
        r"^(RADIADOR|MANGOTE|RESERV|RESERVATORIO|CAVALETE|CONDENSADOR|HELICE|ELETROVENT|CARCACA|TANQUE|MANGUEIRA|AGUA)\b",
        r"^BOMBA (DAGUA|D AGUA)", r"^VALVULA (TERMOST|RADIAD)", r"^TAMPA (RESERV|RADIAD|TANQUE)",
        r"^MOTOR VENT", r"^INTERRUPTOR (VENT|TEMP)",
    )),
    ("Suspensão e Direção", _r(
        r"^(AMORT|BIELETA|PIVO|BANDEJA|BATEDOR|BRACO|TIRANTE|TORCAL|ARTICULADOR|FEIXE|CUBO|INFORCA|GRAMPO|TERMINAL|MOLA)\b",
        r"^COXIM (AMORT|LIMITAD|INF|DT|FEIXE)", r"^BARRA (AXIAL|DIR|ESTAB)", r"^CAIXA DIR", r"^BOMBA DIR",
        r"^BORRACHA (ESTAB|AMORT|SUP)", r"^BUCHA (BAND|EIXO|AMORT|FEIXE|JUMELO|AGREG|BARRA|BRACO)",
        r"^ROLAMENTO RODA", r"^PARAF(USO)? CENTRO", r"^REPARO BUCHA", r"^SUPORTE (AMORT|BRACO|ARTIC|BANDEJA|MOLA)",
    )),
    ("Elétrica e Iluminação", _r(
        r"^(SENSOR|VELAS|VELA|BOBINA|BATERIA|LAMPADA|LANTERNA|FAROL|INTERRUPTOR|RELE|FUSIVEL|INDUZIDO|REGULADOR|COMUTADOR|"
        r"RETIFICADOR|ALTERNADOR|BUZINA|CHICOTE|CONECTOR|SOQUETE|LENTE|REFLETOR|CABOS|TOMADA|RESISTENCIA|IMPULSOR|SONDA|"
        r"CIRCUITO|ESTATOR|ROTOR|AUTOMATICO|ESCOVA|DISTRIBUIDOR|PLATINADO|CAPACITOR|MODULO|COMANDO|BOTAO|CAMPO)\b",
        r"^PORTA (ESCOVA|ESCOV|FUSIVEL)", r"^CHAVE (SETA|LUZ|LIMP|PISCA|IGNICAO)", r"^MOTOR (PARTIDA|PART|LIMP)",
        r"^CILINDRO IGN", r"^CABO (VELA|BATERIA|BAT)", r"^INTERRUP", r"^CONTATO",
    )),
    ("Cabine e Carroceria", _r(
        r"^(MACANETA|FECHADURA|RETROVISOR|PARACHOQUE|GRADE|PARABRISA|PALHETA|LIMPA|VIDRO|ELEVADOR|ELEVADO|ASA|CAPO|PARALAMA|"
        r"MOLDURA|TAPETE|GUARNICAO|PINGADEIRA|DOBRADICA|ASSENTO|CALHA|PESTANA|TRAVA|BATENTE|PORTA|CORTINA|ESPELHO|CAPA|"
        r"COLAR|PROTETOR|CUPULA|DIFUSOR|ARANHA|PLATAFORMA|MACACO|MANIVELA|ANTENA|EMBLEMA|FRISO|PAINEL|FECHO)\b",
        r"^BORRACHA (PORTA|PARAB|TAMPA|CX)", r"^MOTOR (VIDRO|TRAVA)", r"^CILINDRO PORTA", r"^CABO (CAPO|PORTA|TAMPA|VELOC)",
    )),
    ("Motor", _r(
        r"^(JUNTA|BRONZINA|ANEIS|ANEL|PISTAO|CARTER|VALVULA|TUCHO|BALANCIM|RETENTOR|BICO|CABECA|CABECOTE|BIELA|SILENCIOSO|"
        r"CANO|CATALIZADOR|CATALISADOR|COLETOR|FLAUTA|CARBURADOR|EIXO|VARETA|BUJAO|TAMPA|CILINDRO|MOTOR|VOLANTE|COMPRESSOR|"
        r"TUBO|GUIA|CAME|PINO|LIAME|DIAFRAGMA|VIRABREQUIM|COXIM|BUCHA|REPARO|BOMBA)\b",
    )),
]

_CACHE: dict[str, str] = {}


def categoria_para_descricao(descricao: str) -> str:
    desc = normalizar(descricao)
    if desc in _CACHE:
        return _CACHE[desc]
    resultado = "Variados"
    # regras miram a palavra de tipo, então tira prefixos neutros ("JG JUNTA ...")
    sem_prefixo = re.sub(r"^((JG|KIT|CJ|CONJ|JOGO|KT|INATIVO) )+", "", desc)
    for categoria, regex in _REGRAS:
        if regex.search(sem_prefixo):
            resultado = categoria
            break
    _CACHE[desc] = resultado
    return resultado


def slug(categoria: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalizar(categoria).lower()).strip("-")
