"""Siglas da planilha → palavra por extenso.

Levantadas pela frequência real nas 17.149 descrições ativas (2026-10-05). Só entra
sigla confirmada nos dados. Sigla desconhecida passa como está (em minúsculas).
"""
from __future__ import annotations

# Aplicadas na descrição inteira, antes de quebrar em palavras (a ordem importa).
SIGLAS_COMPOSTAS: tuple[tuple[str, str], ...] = (
    (r"\bCX\.?\s+DIR\b", "CAIXA DIRECAO"),
    (r"\bMTR?\s+PART\b", "MOTOR PARTIDA"),
    (r"\b(?:MT|MTR|MOTOR)\s+VENT\b", "MOTOR VENTOINHA"),
    (r"\bSENSOR\s+TEMP\b", "SENSOR TEMPERATURA"),
    (r"\bAR\s+COND\b", "AR CONDICIONADO"),
    (r"\bREGUL(?:ADOR)?\s+VOLT\b", "REGULADOR VOLTAGEM"),
    (r"\bFREIO\s+MAN\b", "FREIO MANUAL"),
    (r"\bD\.\s?REY\b", "DELREY"),
    (r"\bDEL\s+REY\b", "DELREY"),
    (r"\bGRAND?\s+SIENA\b", "GRANSIENA"),
    (r"\bE-TORQ\b", "ETORQ"),
    (r"\bPICK\s?-?\s?UP\b", "PICKUP"),
    # 2026-10-30: contexto decide o sentido (INJ de bomba é injeção; COL é coluna ou coletor)
    (r"\bBOMBA\s+COMB\s+INJ\b", "BOMBA COMBUSTIVEL INJECAO"),
    (r"\bCOL\s+DIR\b", "COLUNA DIRECAO"),
    (r"\bCOL\s+ADM\b", "COLETOR ADMISSAO"),
    (r"(?<=/)BA\b", "BOMBA DAGUA"),             # CORREIA ALT/DH/BA
    (r"\bDM\b", "DRIVEWAY"),                   # marca de pivôs e suspensão (confirmado com a loja)
    (r"\b(\d+)\s?AMP\b", r"\1 AMPERES"),
    (r"\b(\d)\s?CIL\b", r"\1 CILINDROS"),
    (r"\b(\d)\s?TERM\b", r"\1 TERMINAIS"),
    (r"\b(\d+)\s?POL\b", r"\1 POLEGADAS"),
)

SIGLAS: dict[str, str] = {
    # posição e lado
    "DT": "dianteiro", "DIANT": "dianteiro", "TRAS": "traseiro", "TS": "traseiro",
    "SUP": "superior", "INF": "inferior", "EXT": "externo", "INT": "interno",
    "CENTR": "central", "LAT": "lateral", "INTERM": "intermediario", "AUX": "auxiliar",
    # suspensão, direção, freio
    "AMORT": "amortecedor", "ESTAB": "estabilizadora", "BAND": "bandeja", "DIR": "direcao",
    "HIDR": "hidraulica", "DH": "direcao hidraulica", "ELETR": "eletrica", "ELET": "eletrica",
    "MESTR": "mestre", "SUSP": "suspensao", "TENS": "tensora", "HOMOC": "homocinetica",
    "TRANSM": "transmissao", "DIFER": "diferencial", "DIF": "diferencial", "CARD": "cardan",
    "AGREG": "agregado", "SINCR": "sincronizador", "ALAV": "alavanca", "ENGAT": "engate",
    "EMBR": "embreagem", "CAMB": "cambio", "VENT": "ventilado",
    # motor, arrefecimento, alimentação
    "MT": "motor", "MTR": "motor", "PART": "partida", "ALT": "alternador", "COMB": "combustivel",
    "RADIAD": "radiador", "RAD": "radiador", "VALV": "valvula", "TERMOST": "termostatica",
    "CABEC": "cabecote", "ADM": "admissao", "ESC": "escape", "ESCAP": "escapamento",
    "SILENC": "silencioso", "INJ": "injetor", "BBA": "bomba", "VIRA": "virabrequim",
    "VIRAB": "virabrequim", "DENTAD": "dentada", "CORR": "correia", "CART": "carter",
    "RESERV": "reservatorio", "AQUEC": "aquecimento", "RESP": "respiro", "LIMITAD": "limitador",
    "DISTR": "distribuidor", "IMPUL": "impulsor", "SEG": "segmento", "STD": "standard",
    "TEMP": "temperatura", "DETON": "detonacao", "ROL": "rolamento", "ROLAMEN": "rolamento",
    "INTERC": "intercooler", "DIES": "diesel", "DSL": "diesel",
    # elétrica, cabine, carroceria
    "IGN": "ignicao", "VOLT": "voltagem", "REG": "regulador", "REGUL": "regulador",
    "ACD": "ar condicionado", "COND": "condicionado", "PARAB": "parabrisa", "LIMP": "limpador",
    "LAV": "lavador", "LANT": "lanterna", "PARACH": "parachoque", "P/CHOQ": "parachoque",
    "RETROV": "retrovisor", "VELOC": "velocimetro", "ACEL": "acelerador", "VIDR": "vidro",
    "PROT": "protecao", "POSIC": "posicao", "BORB": "borboleta", "ESCOV": "escova",
    # genéricas
    "CX": "caixa", "JG": "jogo", "CJ": "conjunto", "VED": "vedacao", "PARAF": "parafuso",
    "MANG": "mangueira", "HAST": "haste", "SUPORT": "suporte", "ABRAC": "abracadeira",
    "UNIV": "universal", "INDL": "industrial", "PTA": "ponta", "PEQ": "pequeno",
    "COMPL": "completo", "ALUM": "aluminio", "PLAST": "plastico", "CROM": "cromado",
    "BORR": "borracha", "ENGR": "engrenagem", "REP": "reparo",
    # 2026-10-30: GIR (girabrequim, o virabrequim) e PR (preto) confirmados com a loja
    "GIR": "virabrequim", "PR": "preto", "TDS": "todos", "DENT": "dentada", "MEC": "mecanico",
    "AUT": "automatico", "ALC": "alcool", "TRAMB": "trambulador", "ASP": "aspirado", "LEV": "levantador",
    "CONDIC": "condicionado", "CAMINH": "caminhao", "MASC": "mascara", "TERM": "terminal", "CIL": "cilindro",
    "RET": "retentor",
}
