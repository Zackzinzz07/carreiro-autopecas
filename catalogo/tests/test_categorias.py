import pytest

from catalogo.categorias import CATEGORIAS, categoria_para_descricao, slug, tipo_da_peca


@pytest.mark.parametrize("desc,esperada", [
    ("AMORT DT GOL G5 08/", "Suspensão e Direção"),
    ("FILTRO OLEO GOL/PARATI AP 1.6", "Filtros"),
    ("PASTILHA FREIO DT UNO 10/", "Freios"),
    ("PNEU 205/65 R15 MAZZINI 94V", "Pneus e Rodas"),
    ("JG JUNTA MOTOR CORSA 1.0 MPFI", "Motor"),          # prefixo JG é ignorado
    ("JUNTA HOMOC DUSTER 1.6", "Câmbio e Embreagem"),    # exceção de duas palavras vence a regra genérica de JUNTA
    ("TAMPA RESERV GASOL PALIO", "Motor"),               # não é arrefecimento
    ("BOMBA DAGUA CORSA 1.0", "Arrefecimento"),
    ("ROLAMENTO INDUSTRIAL 629", "Variados"),
    ("ABRACADEIRA 12MM", "Variados"),
])
def test_categoria(desc, esperada):
    assert categoria_para_descricao(desc) == esperada


@pytest.mark.parametrize("desc,esperada", [
    # --- Câmbio e Embreagem ---
    ("ROLAMENTO PINHAO DIFER F1000", "Câmbio e Embreagem"),
    ("ROLAMENTO CENTRO HILUX 4X4 2.8 97/04", "Câmbio e Embreagem"),
    ("ROLAMENT SEMI EIXO PALIO/SIENA/STRADA 1.8 04/", "Câmbio e Embreagem"),
    ("ROLAMENTO AGULHA 2A F4000/D20/D40 93/", "Câmbio e Embreagem"),
    ("CABO SELECAO MARCHA UNO 1.0 FLEX 06/", "Câmbio e Embreagem"),
    ("ALAVANCA ENGAT CAMBIO CELTA 01/ CORSA 06/", "Câmbio e Embreagem"),
    ("KIT REP ALAV CAMBIO CELTA/CORSA/ASTRA", "Câmbio e Embreagem"),
    ("LUVA SINCR 1A/RE D20 91/ F1000 93/98", "Câmbio e Embreagem"),
    ("PONTEIRA TRANSM D20/D10 85/96 ASPIRADA CURTA", "Câmbio e Embreagem"),
    ("DISCO EMBR C10 VERANEIO", "Câmbio e Embreagem"),
    ("TULIPA TRIPODE PALIO/SIENA 1.6 E-TORQ 11/ L/", "Câmbio e Embreagem"),
    ("ARRUELA DIF D20 82/ F1000 85/96 5M BRASEIXO", "Câmbio e Embreagem"),
    ("PARAFUSO CARDAN MBB L1113/1513 C/10", "Câmbio e Embreagem"),
    ("PLANETARIA DIFER A/C/D20 82/ F1000 85/ 5M BRA", "Câmbio e Embreagem"),
    # --- Motor ---
    ("ROLAMENTO AGULHA VIRAB CORCEL/D.REY/PAMPA 1.6", "Motor"),
    ("BOIA TANQUE COMB CORCEL 2 78/82", "Motor"),
    ("CORPO BORBOLETA CORSA 1.4/1.8 06/ MPFI 8V", "Motor"),
    ("ARRUELA ENCOSTO VIRAB STD UNO R/PREMIO", "Motor"),
    ("BORRACHA SILENC CENTRAL GOL 80/95", "Motor"),
    ("CABO ESTRANG MBB LP321 TDS 2150MM", "Motor"),
    ("PESCADOR PALIO FIRE 01/", "Motor"),
    ("ABRACADEIRA ESCAPAMENTO 2.1/4", "Motor"),
    ("CONEXAO COL ADM DOBLO/PALIO/IDEA 1.8 04/", "Motor"),
    ("PARAFUSO CABEC PALIO/DOBLO/1.0/1.3/1.4 8V", "Motor"),
    # --- Elétrica e Iluminação ---
    ("ROLAMENTO ALT GOL 95/", "Elétrica e Iluminação"),
    ("ROLAMENTO ARRANQUE L/MOTRIZ (15.8X20.6X19)", "Elétrica e Iluminação"),
    ("MANCAL ALT D20 PERKINS 85/91", "Elétrica e Iluminação"),
    ("DIODO RETIFICADOR", "Elétrica e Iluminação"),
    ("GARRA BATERIA PEQUENA", "Elétrica e Iluminação"),
    ("CABO PP 2 CONDUT 25MT", "Elétrica e Iluminação"),
    ("CINTA AIRBAG COROLLA 03/08", "Elétrica e Iluminação"),
    ("SIRENE UNIVERSAL 12V 6 TOQUE", "Elétrica e Iluminação"),
    # --- Arrefecimento ---
    ("ROLAMENTO AR COND CORSA/MERIVA/MONTANA DELPHI", "Arrefecimento"),
    ("CONEXAO DAGUA BLOCO MT AP 1.8 PAMPA/DREY", "Arrefecimento"),
    ("FLANGE FLUXO DAGUA HB20 12/ S/SENSOR", "Arrefecimento"),
    ("SUPORTE RADIAD PALIO/SIENA 98/00 - 324K", "Arrefecimento"),
    ("COLMEIA RAD D20/40/C20/D40 85/ 3TUB", "Arrefecimento"),
    ("TAMPAO RADIAD PALIO/SIENA/STRAD 96/02 UNO 90/", "Arrefecimento"),
    ("PRESSOSTATO AR CONDICIONADO PUNTO/ASTRA/CELTA", "Arrefecimento"),
    # --- Suspensão e Direção ---
    ("ABRACADEIRA TORCAL SIMPLES UNIV 10-12MM", "Suspensão e Direção"),
    ("ABRACADEIRA FEIXE MOLA TRAS", "Suspensão e Direção"),
    ("BORRACHA/ABRAC ESTAB DT GOL", "Suspensão e Direção"),
    ("BORRACHA JUMELO TRASEIRA SUPERIOR H100/L200/H", "Suspensão e Direção"),
    ("ROLAMENTO COL DIR GOL/VOY/ TDS", "Suspensão e Direção"),
    ("KIT ROL RODA TS CORSA 94/ CELTA/PRISMA 01/", "Suspensão e Direção"),
    ("PRATO COXIM AMORT DIANT GOL G5/VOY 08/", "Suspensão e Direção"),
    ("PONTA EIXO TRAS CORSA 94/ CELTA 00/ PRISMA 06", "Suspensão e Direção"),
    ("AMORTECEDOR CG125/150 COFAP", "Suspensão e Direção"),
    ("RET ROD DIANT CORCEL/D.REY/BELINA/PAMPA", "Suspensão e Direção"),
    ("PORCA MANGA EIXO DT HILUX 4X4 92/04", "Suspensão e Direção"),
    # --- Freios ---
    ("REGULAGEM FREIO TRAS HILUX 05/ LD", "Freios"),
    ("CABO LIBERACAO FREIO D20 BONANZA 93/96 590MM", "Freios"),
    ("SANGRIA FREIO D10/D20/F1000 (UNIDADE)", "Freios"),
    ("REBITE ALUM LONA FREIO D20", "Freios"),
    ("ALAVANCA SAPATA FREIO MAO D20/SILVERADO 93/", "Freios"),
    ("HASTE ACION FREIO TRAS D20/S10/F1000/RANGER 0", "Freios"),
    # --- Cabine e Carroceria ---
    ("CABO FECH PORTA DT CELTA 07/ 2 PORTA LD", "Cabine e Carroceria"),
    ("LIMITADOR PORTA DT FOX 03/ LD/LE 4 PORTA", "Cabine e Carroceria"),
    ("ALAVANCA CAPO GOL BOLA 95/", "Cabine e Carroceria"),
    ("BASE VIDRO RETROV CORSA MAX 03/ LE", "Cabine e Carroceria"),
    ("PONTEIRA PARACH DIANT D20 85/96 LD", "Cabine e Carroceria"),
    ("FAIXA ADESIVA LATERAL D20 93 CABINE SIMPLES", "Cabine e Carroceria"),
    ("ESGUICHO PARABRISA CORSA", "Cabine e Carroceria"),
    ("QUEBRA SOL UNO 04/ LD CINZ C/ESPELHO", "Cabine e Carroceria"),
    ("REGULAGEM SAPATA FREIO PALIO 12/ LD/LE", "Freios"),
    ("CONEXAO FREIO F100/F1000/A/C/D10/20", "Freios"),
    ("CONEXAO VALV TERMOST COROLLA 1.8 02/08", "Arrefecimento"),
    ("CONEXAO T LAVADOR PARABRISA MENOR", "Cabine e Carroceria"),
    ("FLANGE MODUL COMB DUSTER 12/ MARWA", "Motor"),
    ("ROLAMENTO LAT DIFERENCIAL D20/10 85/96 F1000", "Câmbio e Embreagem"),
    ("ROLAMENTO INF COL DIR D20 93/", "Suspensão e Direção"),
    ("CJ PARAF/PORCA TS RODA CARGO M22 1.5X11", "Pneus e Rodas"),
    ("SUPORTE TAMPA CORR DENTAD PALIO 1.4 8V 06/12", "Distribuição e Correias"),
    ("ARRUELA TRAVA PONT CAPA TS FREIO OLEO MBB", "Freios"),
    # --- Filtros ---
    ("SUPORTE FILT OLEO MBB 1620/PM366LA DIES", "Filtros"),
    ("RABICHO MANG FILTRO AR CORSA 1.0 05/08", "Filtros"),
    ("PRE FILTRO BOMBA COMB INJECAO GOL/PARATI 1.0/", "Filtros"),
    # --- Pneus e Rodas ---
    ("CONTRA PESO BALANCEAMENTO CHUMBO 10G", "Pneus e Rodas"),
    ("PITO PNEU S/CAMARA ARO 13 42MM", "Pneus e Rodas"),
    ("PORCA PARAF RODA HILUX 04/", "Pneus e Rodas"),
    ("REMENDO P/PNEU S/CAMARA DE AUTOMOVEIS VULCAN", "Pneus e Rodas"),
    # --- Lubrificantes e Químicos ---
    ("RESTAURAX 500ML", "Lubrificantes e Químicos"),
    ("SUPER CERA 1.5L", "Lubrificantes e Químicos"),
    ("OLE ATF DEXROON III 24X1L", "Lubrificantes e Químicos"),
    ("SANITIZANTE CARRO NOVO 1.5L", "Lubrificantes e Químicos"),
])
def test_refinamentos_variados(desc, esperada):
    assert categoria_para_descricao(desc) == esperada


@pytest.mark.parametrize("desc,esperada", [
    # não podem mudar: continuam onde já estavam (ou em Variados, se não cabem)
    ("ROLAMENTO INDUSTRIAL 6003 SKF", "Variados"),
    ("ROLAMENTO RODA DT GOL", "Suspensão e Direção"),
    ("ROLAMENTO CORREIA ALT S10", "Distribuição e Correias"),
    ("ABRACADEIRA MANG 1/2", "Variados"),
    ("CHAVE RODA 33X27MM 400MM C/CABO", "Variados"),
    ("DISCO ABRASIVO WURTH 115X1.0X22.23", "Variados"),
    ("DISCO FREIO DT GOL", "Freios"),
    ("GRAXEIRO RETO 1/4 UNIV", "Variados"),
    ("PARAFUSO ACO ROSCA GROSSA", "Variados"),
    ("REBITE 10X14 ALUM M UNIT", "Variados"),
    ("CABO ACEL GOL G5", "Motor"),
    ("CABO EMBR GOL", "Câmbio e Embreagem"),
    ("CABO FREIO MAO GOL", "Freios"),
    ("BORRACHA PORTA DT GOL", "Cabine e Carroceria"),
    ("PASTILHA FREIO REGULAGEM", "Freios"),
])
def test_refinamentos_nao_mudam_o_resto(desc, esperada):
    assert categoria_para_descricao(desc) == esperada


def test_toda_categoria_devolvida_esta_na_lista():
    assert categoria_para_descricao("QUALQUER COISA ESTRANHA") in CATEGORIAS


def test_tipo_ignora_prefixo_e_barra():
    assert tipo_da_peca("JG JUNTA MOTOR") == "JUNTA"
    assert tipo_da_peca("BORRACHA/ABRAC 12") == "BORRACHA"


def test_slug():
    assert slug("Suspensão e Direção") == "suspensao-e-direcao"
