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
    # --- refinamentos (só pegam o que as regras acima deixavam em "Variados") ---
    # Ficam por último de propósito: não mexem em quem já tinha categoria. Dentro do
    # bloco a ordem importa (exceções de duas palavras antes das genéricas).
    ("Motor", _r(
        r"^ROLAMENTO AGULH\w* VIRAB", r"^ROLAMENTO (VOL|MOTOR)\b", r"^BOIA\b", r"^CORPO BORBOLETA", r"^ARRUELA (ENCOSTO VIRAB|VED BICO)",
        r"^CONEXAO COL ADM", r"^PARAF\w* (CABEC|COLET)", r"^BORRACHA SILENC", r"^CABO ESTRANG", r"^REP PEDAL ACEL",
        r"^AGULHA CARBURADOR", r"^PESCADOR\b", r"^COBERTURA TAMPA VALV", r"^ESCORA BALANCIM", r"^PISTOES", r"^(DE|DO) (BRONZINA|JUNTAS?|PISTAO)\b",
        r"^PENEIRA OLEO", r"^TURBINA\b", r"^INJETOR OLEO", r"^(KIT )?VEDAC TUBO ESCAP", r"^SILENC INTERM", r"^CINTA ESCAPAMENTO",
        r"^SUPORTE TRAS ESCAP", r"^ABRACADEIRA ESCAPAMENTO", r"^CREMALHEIRA VOL", r"^MEDIDOR FLUXO AR", r"^FLANGE MODE?L?U? ?COMB", r"^FLANGE MODUL COMB", r"^TAQUE COMB", r"^GARGALO BOCAL",
    )),
    ("Filtros", _r(
        r"^SUPORTE FILT\b", r"^RABICHO MANG FILT", r"^PRE FILTRO", r"^COPO FILTRO", r"^CONJUNTO FILTRO", r"^DUTO FILTRO",
        r"^CINTA DE FIXACAO DO FILTRO", r"^BORRACHA FILTRO", r"^BASE FILTRO",
    )),
    ("Pneus e Rodas", _r(
        r"^CONTRA PESO", r"^PITO\b", r"^REMENDO\b", r"^(PARAFUSO|PARAF|PORCA|ARRUELA)[ /]+(PARAF |PORCA )?RODA", r"^PARAFUSO/PORCA RODA", r"^PARAF/PORC\w* (TS |TRAS )?RODA", r"^PARAF(/PORCA)? (TRAS )?RECART",
        r"^PORCA PARAF RODA", r"^ARRUELA PARAF RODA",
    )),
    ("Câmbio e Embreagem", _r(
        r"^ROLAMENTO (PINHAO|DIANT PINHAO|GRANDE PINHAO|DIFERENCIAL|CENTRO|SEMI|CX|EIXO PILOTO|EIXO ENTAL|AGULH)", r"^ROL (PINHAO|ALOJAMENTO)",
        r"^ROLAMENT SEMI", r"^ROLAMENTO LAT\b", r"^ROLETES EIXO PILOTO", r"^CABO SELECAO", r"^ALAVANCA (ENGAT|GARFO)", r"^REP (ALAV|SERV EMBR|CX)",
        r"^LUVA\b", r"^PONTEIRA TRANSM", r"^DISCO EMBR", r"^BALANCA EMBR", r"^HASTE (ACION EMBR|PEDAL EMBR)", r"^COTOVELO CIL EMBR",
        r"^CAIXA SATELITE", r"^PLANETARIA", r"^ARRUEL\w* (BIPARTIDA CALCO|CALCO|DIF|SATELITE|TRAVA EMBR)", r"^ESPACADOR PINHAO",
        r"^PLACA DO DIFERENCIAL", r"^TULIPA\b", r"^SUPORTE (TRAMB|ROL)", r"^PARAFUSO (CARDAN|ABRAC CARD)",
        r"^PORCA (FLANGE TRANSM|PONTEIRA CARD|CARCACA DIFER|EIXO ENTALHADO)", r"^FLANGE (CX MARCHA|ROL SEMI)", r"^JUNCAO TRAMB",
    )),
    ("Distribuição e Correias", _r(r"^SUPORTE TAMPA CORR")),
    ("Freios", _r(
        r"^REGULAGEM (SAPATA )?FREIO", r"^ALAVANCA (REG SAP|SAP)", r"^CABO LIBERACAO FREIO", r"^JUNCAO CABO FREIO", r"^EQUALIZADOR CABO",
        r"^HASTE ACION FREIO", r"^SANGRIA FREIO", r"^REBITE ALUM LONA", r"^FIXAR EIXO EXPANSOR", r"^ARRUELA EIXO EXPANSOR",
        r"^MANICOTO FREIO", r"^MANETE FREIO", r"^LAT MANCAL FREIO", r"^ARRUELA TRAVA PONT CAPA .*FREIO", r"^CONEXAO (FREIO|REDUCAO .*FREIO)", r"^PORCA (FREIO|PONTA CAPA)", r"^PARAFUSO CINTA CUIC FREIO",
        r"^SILENCIADOR PARA FREIOS", r"^ROLAMENTO PINCA", r"^MANOMETRO AR", r"^DRENO TANQUE AR", r"^CONEXAO ADAP .*FRE",
    )),
    ("Suspensão e Direção", _r(
        r"^ROLAMENT?O? (INF )?(COL DIR|CX DIR|CUBO)", r"^ROL\w* RODA", r"^ROL\w* EIXO (TS|TRAS)", r"^ROLAMENTO (DIANT|DT|TS|TRAS)\b",
        r"^ABRACADADEIRA FEIXE", r"^ABRACADEIRA (TORCAL|FEIXE)", r"^BORRACHA[ /](ABRAC|OLHAL|JUMELO)", r"^JUMELO\b",
        r"^PRATO (COXIM|MOLA)", r"^APOIO BARRA ESTAB", r"^CHAPA ESTAB", r"^BOR ESTAB", r"^PONTA EIXO", r"^LAMEIRA", r"^COLUNA DIR",
        r"^SUPORTE (INF|TRAS) FEIXE", r"^AMORTECEDOR\b", r"^RET ROD", r"^ARRUELA (PONTA EIXO|TRAVA (CUBO|PONT|PORC)|BRONZE MANGA|PINO MOLA)",
        r"^(PARAFUSO|PARAF|PORCA) (AMORT|CAMBAG|MANGA|GRAMP|PONTA EIXO|ABRACADEIRA FEIXE)", r"^PARAF\w* (DE )?CENT",
    )),
    ("Arrefecimento", _r(
        r"^ROLAMENTO (AR COND|COMPRES)", r"^CONEXAO (DAGUA|BOMBA DAGUA)", r"^FLANGE (CONEX|COTOVELO|FLUX|CABEC)", r"^COTOVELO (CAVAL|VALV)",
        r"^SUPORTE (RADIAD|SUP RADIAD|VENT)", r"^BASE (INF )?RADIAD", r"^CONEXAO (VALV TERMOST|MANGUEIRA|SUP RAD|TEMP DAGUA)", r"^COLMEIA", r"^DEFLETOR RADIAD", r"^TAMPAO RADIAD", r"^TRAVESSA RAD",
        r"^DEDAL BOMBA DAGUA", r"^UNIAO BOMBA DAGUA", r"^SELANTE (BIODEGRADAVEL P/ )?RADIADOR", r"^BOCAL ESCOAMENTO AGUA",
        r"^PRESSOSTATO", r"^EVAPORADOR", r"^MAGNETICO COMPRES",
    )),
    ("Cabine e Carroceria", _r(
        r"^PISCA RETROV", r"^CABO (FECH|BANCO|CONTAGIRO)", r"^BORRACHA (VIDR|VIGIA|ALARG)", r"^LIMITADOR PORT", r"^BASE (MACANETA|VIDRO)", r"^CONEXAO T (MANG|LAVADOR)",
        r"^SUPORTE (GUIA PARACH|MAC|PARALAMA|RETROV|VIDRO)", r"^FAIXA (ADESIVA|DECORAT)", r"^ALAVANCA CAPO", r"^REP TAMPA TRAS",
        r"^PONTEIRA PARACH", r"^ESGUICHO", r"^QUEBRA[ -]SOL", r"^CALHAS", r"^FORRO PORTA", r"^GANCHO (CACAMBA|CARROCERIA)", r"^INGADEIRA",
        r"^PUXADOR", r"^TRINCO", r"^DISPOSITIVO FECHADURA", r"^MOLD P/CHOQUE", r"^ARO FAROL", r"^PORTINHOLA", r"^RETROV\b",
        r"^TELA PARACH", r"^CINTO SEGURANCA", r"^ENGATE REBOQ", r"^BOLA ENGATE", r"^COMPLE\.GRADE", r"^VID\b", r"^PALH LIMP",
    )),
    ("Elétrica e Iluminação", _r(
        r"^ROLAMENTO (ALT|ALTERNADOR|GERADOR|ARRANQUE|DIANT ALT)", r"^ROL CORR ALT", r"^MANCAL (ALT|MTR PART)", r"^ESCOVAS", r"^DIODO", r"^TRIO DIODO", r"^TRIODO",
        r"^PONTE RETIFIC", r"^CARREGADOR BAT", r"^CORDOALHA P/BATERIA", r"^GARRA BATERIA", r"^FIO\b", r"^CABO (INSTALACAO|PP)",
        r"^ACENDEDOR", r"^SIRENE", r"^BREAK LIGHT", r"^PENDENTE EMERG", r"^PLAFON", r"^PISCA\b", r"^CHICOETE FAROL", r"^SUPORTE FAROL",
        r"^LAMPAD", r"^CONJUNTO INTERRUPTOR", r"^SOLENOIDE", r"^RADIO\b", r"^VENTILADOR CABINE", r"^ALAVANCA CHAVE SETA", r"^CINTA AIRBAG",
        r"^SELO BOBINA", r"^EXTENSOR PROLONGADOR", r"^CONECT SOND", r"^QUEBRA VENTO",
    )),
    ("Lubrificantes e Químicos", _r(
        r"^(ALUMAX|DARKER|DELET|INTENSE|IZER|PRIZM|RESTAURAX|SINTRA|TRYON|V-FLOC|V-MOL|V-PLASTIC|REJUVEX|REMOVEX|STRIKE|SINERGY|BLEND|"
        r"CARNAUBA|TROPICAL|SANITIZANTE|ODORIZANTE|EMBORRACHAMENTO|QUEROSENE|VASELINA|ARALDITE|DUREPOXI|CONDICIONADOR|LIMPADOR|"
        r"VERNIZ|ESMALTE|RESINA|SELANTE|VEDA|PRETINHO|ESPUMA|OLE)\b",
        r"^SUPER CERA", r"^LAVA AUTOS", r"^SOLUCAO BATERIA", r"^GEL MISTO", r"^AUTO FRESH", r"^BATIDA PEDRA", r"^V[12]0 ", r"^PAPEL MASCARAMENTO",
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
