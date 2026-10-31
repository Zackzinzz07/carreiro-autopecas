import sqlite3
from pathlib import Path

import pytest

from catalogo.fotos.normalizar import Chave, completar_final, normalizar

CASOS = [
    # descrição real da planilha, peca, veiculo, veiculo_alt, lado, marca, tipo_en
    ("PASTILHA FREIO DT AGILE/CELTA/CORSA/PRISMA", "pastilha freio dianteiro", "agile", "celta", "", "", "brake pad"),
    ("COXIM AMORT DT C/ROL CLIO/KANGOO 99/", "coxim amortecedor dianteiro com rolamento", "clio", "kangoo", "", "", "strut mount"),
    ("BIELETA ESTAB DT S10/TRAILBLAZER 12/ LD", "bieleta estabilizadora dianteiro", "s10", "trailblazer", "direito", "", "stabilizer link"),
    ("AMORT DT COROLLA 08/14 L/D", "amortecedor dianteiro", "corolla", "", "direito", "", "shock absorber"),
    ("CABO EMBR PAMPA/D.REY/SCALA 1.8 07.89/ AP", "cabo embreagem", "pampa", "del rey", "", "", "clutch cable"),
    ("IMPULSOR MTR PART PALIO/IDEA/STRADA/UNO NOVO", "impulsor motor partida", "palio", "idea", "", "", "starter drive bendix"),
    ("SENSOR TEMP AGUA GOL/PARATI", "sensor temperatura agua", "gol", "parati", "", "", "temperature sensor"),
    ("BARRA AXIAL ASTRA/ZAFIRA 99/ VECTRA 06/ C/DH", "barra axial", "astra", "zafira", "", "", "inner tie rod"),
    ("BANDEJA DT C/PIVO 206/207 99/ LD", "bandeja dianteiro com pivo", "206", "207", "direito", "", "control arm"),
    ("BOMBA DAGUA GOL/SAVEIRO 1.6/1.8 95/", "bomba dagua", "gol", "saveiro", "", "", "water pump"),
    ("ALAVANCA CAPO GOL/PAR/SAV", "alavanca capo", "gol", "parati", "", "", ""),
    ("AMORT DT UNO 10/ S/BARRA ESTAB L/D", "amortecedor dianteiro", "uno", "", "direito", "", "shock absorber"),
    ("MT VENT GOL/VOYAGE 09/", "motor ventoinha", "gol", "voyage", "", "", "radiator cooling fan motor"),
    ("REGULADOR VOLT GOL/PARATI", "regulador voltagem", "gol", "parati", "", "", "voltage regulator"),
    ("CORREIA ALT/ACD/DH/BA SCANIA R114", "correia alternador ar condicionado direcao hidraulica bomba dagua", "scania", "", "", "", "drive belt"),
    ("ABRACADEIRA 3/4X102X320 CARGO 1313 A 2218 DT", "abracadeira", "cargo", "", "", "", "hose clamp"),
    # descrição cortada no fim: "CELT" é completado para Celta (completar_final)
    ("BOMBA DAGUA (POLIA C/19 DENTES) AGILE 09/CELT", "bomba dagua polia", "agile", "celta", "", "", "water pump"),
    # sem carro: a descrição inteira é a peça (medida e marca identificam o item)
    ("OLEO MOTOR 15W40 PETRONAS SYNTIUM 800 SE", "oleo motor 15w40 petronas syntium 800 se", "", "", "", "PETRONAS", "motor oil bottle"),
    ("LAMPADA FAROL H4 HALOGENA 12V 60/55W", "lampada farol h4 halogena 12v 60 55w", "", "", "", "", "headlight bulb"),
    # Review Focus 2: em pneu, 205 é medida, não Peugeot 205
    ("PNEU 205/65 R15 MAZZINI 94V", "pneu 205 65 r15 mazzini 94v", "", "", "", "MAZZINI", "car tire"),
    ("PNEU 175/75 R13 GOLDEN CROWN 85T PRETO NA", "pneu 175 75 r13 golden crown 85t preto na", "", "", "", "GOLDEN CROWN", "car tire"),
]


@pytest.mark.parametrize("descricao,peca,veiculo,alt,lado,marca,tipo_en", CASOS)
def test_normaliza_descricoes_reais(descricao, peca, veiculo, alt, lado, marca, tipo_en):
    c = normalizar(descricao)
    assert (c.peca, c.veiculo, c.veiculo_alt, c.lado, c.marca, c.tipo_en) == (peca, veiculo, alt, lado, marca, tipo_en)


def test_consultas_e_chave():
    c = normalizar("PASTILHA FREIO DT AGILE/CELTA/CORSA/PRISMA")
    assert c.texto == "pastilha freio dianteiro|agile|||"
    assert c.consulta == "pastilha freio dianteiro agile"
    assert c.consulta_alt == "pastilha freio dianteiro celta"
    lado = normalizar("AMORT DT COROLLA 08/14 L/D")
    assert lado.consulta == "amortecedor dianteiro corolla 2008 lado direito"
    assert lado.consulta_alt == "amortecedor dianteiro lado direito"
    oleo = normalizar("OLEO MOTOR 15W40 PETRONAS SYNTIUM 800 SE")
    assert oleo.consulta == "oleo motor 15w40 petronas syntium 800 se" and oleo.consulta_alt == ""
    assert oleo.texto == "oleo motor 15w40 petronas syntium 800 se|||PETRONAS|"


def test_mesmo_grupo_para_mesma_peca_e_carro():
    assert normalizar("PASTILHA FREIO DT AGILE/CELTA").texto == normalizar("PASTILHA FREIO DT AGILE/CELTA/PRISMA").texto
    assert normalizar("GRADE CENTR PARACH COROLLA 12/14").texto == normalizar("GRADE CENTR PARACH COROLLA 12/14 PRETA").texto
    assert normalizar("PNEU 205/65 R15 MAZZINI 94V").texto != normalizar("PNEU 175/70 R14 MAZZINI 84T").texto


def test_marca_incerta_so_em_consumivel_sem_marca_e_sem_carro():
    assert normalizar("LAMPADA FAROL H4 HALOGENA 12V 60/55W").marca_incerta is True
    assert normalizar("OLEO MOTOR 15W40 PETRONAS SYNTIUM 800 SE").marca_incerta is False
    assert normalizar("PASTILHA FREIO DT AGILE/CELTA").marca_incerta is False


def test_chave_de_tipo_e_descricao_vazia():
    t = Chave.para_tipo("pastilha freio", "brake pad")
    assert (t.texto, t.consulta, t.consulta_alt, t.e_tipo) == ("TIPO:pastilha freio", "pastilha freio", "", True)
    assert normalizar("").peca == "" and normalizar("  /  ").peca == ""


BANCO_REAL = Path(__file__).resolve().parents[1] / "data" / "catalogo.db"


@pytest.mark.skipif(not BANCO_REAL.exists(), reason="banco real ausente")
def test_cobertura_no_catalogo_real():
    conn = sqlite3.connect(f"file:{BANCO_REAL}?mode=ro", uri=True)
    descricoes = [r[0] for r in conn.execute("SELECT descricao FROM produtos WHERE ativo = 1")]
    conn.close()
    chaves = [normalizar(d) for d in descricoes]
    n = len(chaves)
    com_peca = sum(bool(c.peca) for c in chaves) / n
    com_tipo = sum(bool(c.tipo_en) for c in chaves) / n
    grupos = len({c.texto for c in chaves})
    print(f"\n{n} produtos | peça {com_peca:.1%} | rótulo CLIP {com_tipo:.1%} | {grupos} grupos")
    assert com_peca >= 0.99
    assert com_tipo >= 0.83
    assert grupos <= 11_500   # ano na chave (2026-10-11): 10.607; + motor/geração e finais cortados (2026-10-30): 11.124


@pytest.mark.parametrize("descricao,anos", [
    ("GRADE PARACHOQUE DT COROLLA 12/14", "2012-2014"),
    ("GRADE PARACHOQUE DT COROLLA 15/17", "2015-2017"),
    ("AMORT DT UNO 10/ S/BARRA ESTAB L/D", "2010-"),
    ("ALAVANCA CAMBIO UNO MILLE /13 S/CABO/MANOPLA", "-2013"),
    ("BARRA AXIAL ASTRA/ZAFIRA 99/ VECTRA 06/ C/DH", "1999-"),          # o ano do PRIMEIRO carro
    ("PASTILHA FREIO DT PALIO 00/ STRADA 98/ IDEA", "2000-"),
    ("CAPA RETROVISOR MOBI 2017/ LD", "2017-"),
    ("TERMINAL DIR GOL/VOYALE/PARATI/SAVEIRO 80/04", "1980-2004"),
    ("PASTILHA FREIO DT AGILE/CELTA/CORSA/PRISMA", ""),                 # sem ano na descrição
    ("BOMBA DAGUA GOL/SAVEIRO 1.6/1.8 95/", "1995-"),                   # 1.6/1.8 é motor, não ano
    ("JUNTA TAMPA VALV ONIX/PRISMA 1.0/1.4 8V 12/", "2012-"),           # 8V não é ano
    ("BANDEJA DT C/PIVO 206/207 99/ LD", "1999-"),                      # 206/207 são carros
    ("ESCOVA MTR PART C10/14/15 WAPSA", ""),                            # C10/C14/C15 são caminhonetes
    ("CABO EMBR PAMPA/D.REY/SCALA 1.8 07.89/ AP", ""),                  # mês.ano: não arrisca
    ("PNEU 205/65 R15 MAZZINI 94V", ""),                                # medida de pneu
    ("LAMPADA FAROL H4 HALOGENA 12V 60/55W", ""),                       # potência
])
def test_faixa_de_anos_do_primeiro_carro(descricao, anos):
    assert normalizar(descricao).anos == anos


def test_ano_separa_geracoes_e_entra_na_busca():
    a, b = normalizar("GRADE PARACHOQUE DT COROLLA 12/14"), normalizar("GRADE PARACHOQUE DT COROLLA 15/17")
    assert a.texto != b.texto and a.texto == "grade parachoque dianteiro|corolla|||2012-2014"
    assert a.consulta == "grade parachoque dianteiro corolla 2012" and a.faixa == (2012, 2014)
    assert normalizar("ALAVANCA CAMBIO UNO MILLE /13").consulta.endswith("uno 2013")
    assert normalizar("PASTILHA FREIO DT AGILE/CELTA").faixa == (None, None)


def test_carro_colado_no_motor_e_reconhecido():
    c = normalizar("CABOS VELAS CORSA1.0/1.4/1.6 8V MPFI/PALIO/PU")
    assert (c.peca, c.veiculo, c.veiculo_alt) == ("cabos velas", "corsa", "palio")


def test_motor_e_geracao_separam_grupos():   # correia 306 2.0 dividia foto com a 1.6 (piloto 2)
    a, b = normalizar("CORREIA ALT 306/405 2.0 16V 93/98"), normalizar("CORREIA ALT 306/405 1.6 93/98")
    assert a.texto == "correia alternador|306|||1993-1998|2.0 16V"
    assert a.texto != b.texto and a.atributos.cilindradas == {"2.0"}
    assert normalizar("CUBO RODA TRAS GOL GV 08/").texto != normalizar("CUBO RODA TRAS GOL GIV 08/").texto
    # sem motor nem geração: chave de antes, grupos já processados continuam valendo
    assert normalizar("PASTILHA FREIO DT AGILE/CELTA/CORSA/PRISMA").texto == "pastilha freio dianteiro|agile|||"
    # sem carro não há geração a separar: "1.5" num óleo ou lâmpada não é motor
    assert normalizar("LAMPADA FAROL H4 HALOGENA 12V 60/55W").atributos == normalizar("OLEO 1.5").atributos


@pytest.mark.parametrize("descricao,peca", [   # siglas confirmadas com a loja e nos dados (2026-10-30)
    ("CORREIA GIR/ALT/DH/ACD CORSA 94/ 1.0/1.6 8V", "correia virabrequim alternador direcao hidraulica ar condicionado"),
    ("BOMBA COMB INJ FIAT/ GM/ FORD/ VW C/FILT", "bomba combustivel injecao"),
    ("TENSOR CORREIA DENT CORSA 94/ 1.0/1.6 CELTA 0", "tensor correia dentada"),
    ("MACANETA LEV VIDRO PORTA CORSA 94/00", "macaneta levantador vidro porta"),
    ("ROLAMENTO COL DIR SUP D20/10 C10 60/84", "rolamento coluna direcao superior"),
    ("CONEXAO COL ADM DOBLO/PALIO/IDEA 1.8 04/", "conexao coletor admissao"),
    ("SUPORTE TRAMB CAMBIO CX DIR UNO/TEMPRA", "suporte trambulador cambio caixa direcao"),
    ("JG JUNTA MOTOR C/RET FIESTA/KA 1.6 8V 99/12", "jogo junta motor com retentor"),
    ("CAIXA DIR MEC GOL/SAVEIR/PARATI/VOYAGE 85", "caixa direcao mecanico"),
    ("FUSIVEL 20AMP PORCEL", "fusivel 20 amperes porcel"),
    ("PALHETA 14 POL CONV", "palheta 14 polegadas conv"),
    ("GRADE PR UNIVERSAL", "grade preto universal"),
])
def test_siglas_novas(descricao, peca):
    assert normalizar(descricao).peca == peca


def test_marca_de_peca_nao_separa_grupo():   # stakeholders (2026-10-30): foto da peça certa basta, de qualquer marca
    dm, viemar, sem = (normalizar(d) for d in ("PIVO GOL/PARATI 95/97 DM LE/LD RETO",
                                                 "PIVO GOL/PARATI 95/97 VIEMAR LE/LD RETO", "PIVO GOL/PARATI 95/97 LE/LD RETO"))
    assert dm.texto == viemar.texto == sem.texto and dm.marca == "" and "driveway" not in dm.peca
    # consumível é vendido pela marca: ela continua na chave
    assert normalizar("OLEO MOTOR 15W40 PETRONAS SYNTIUM 800 SE").marca == "PETRONAS"


@pytest.mark.parametrize("descricao,veiculo,alt", [   # carros e erros de digitação da planilha (2026-10-30)
    ("CABO VELA ESCORT/VERONA/APOLLO 1.8 AP 92/", "escort", "verona"),
    ("COIFA LADO CAMBIO APOLLO 89/", "apollo", ""),
    ("ROLAMENTO CORR ALT PALIO/BRAVA 00/ 1.6", "palio", "brava"),
    ("TERMINAL DIR GOL/VOYALE 09/", "gol", "voyage"),
    ("CAIXA DIR MEC GOL/SAVEIR/PARATI", "gol", "saveiro"),
    ("BUCHA BAND CORSA/MARIVA 03/", "corsa", "meriva"),
    ("CABO EMBR ESCORTE 1.6 93/", "escort", ""),
    ("FILTRO AR CONSTELATION 24.250", "constellation", ""),
])
def test_carros_novos_e_grafias_erradas(descricao, veiculo, alt):
    c = normalizar(descricao)
    assert (c.veiculo, c.veiculo_alt) == (veiculo, alt)


def test_pneu_nao_tem_carro_nem_quando_o_modelo_do_pneu_e_nome_de_carro():
    c = normalizar("PNEU 185/60R15 84H BLAZER COMPASAL")
    assert (c.veiculo, c.marca) == ("", "COMPASAL")
    assert "primaparts" in normalizar("FILTRO OLEO PSL55 PRIMAPARTIS").peca


@pytest.mark.parametrize("descricao,completa", [   # a planilha corta a descrição no 45º caractere
    ("CORREIA GIR/ALT PALIO 1.0/1.3 8/16V 2000/ FIR", "CORREIA GIR/ALT PALIO 1.0/1.3 8/16V 2000/ FIRE"),
    ("AMORT DT UNO VIVACE 10/ C/BARRA ESTAB L/D NAK", "AMORT DT UNO VIVACE 10/ C/BARRA ESTAB L/D NAKATA"),
    ("ARTICULADOR INF ALAV CAMBIO CORSA/CELTA/PRISM", "ARTICULADOR INF ALAV CAMBIO CORSA/CELTA/PRISMA"),
    ("BOMBA DAGUA HILUX 2.8 SRV 3.0 ASP/TURBO DIESE", "BOMBA DAGUA HILUX 2.8 SRV 3.0 ASP/TURBO DIESEL"),
    ("ROLAMENTO CORREIA ALTERNADOR GOL/PARATI/SAVEI", "ROLAMENTO CORREIA ALTERNADOR GOL/PARATI/SAVEIRO"),
])
def test_completa_final_cortado(descricao, completa):
    assert len(descricao) == 45 and completar_final(descricao) == completa


@pytest.mark.parametrize("descricao", [
    "FILTRO CABINE ACD PALI/SIENA/WEEK/STRADA FIRE",   # já inteiro: não vira FIRESTONE
    "CABO VELA ESCORT/VERONA/APOLLO 1.8 AP 92/ CAR",   # CARAVAN ou CARGO
    "CILINDRO RODA TRAS FIESTA/KA 1.0/1.3 97/ ESCO",   # Escort ou escova
    # falsos positivos medidos pelo Argon: o prefixo também é de palavra comum
    "BOMBA DAGUA S10/BLAZER/MONZA/KADETT 89/95 POL",   # polia, não POLO
    "BOMBA COMB INJ KIT FIT/FORD/VW/GM/GASOL 3 BAR",   # pressão, não BARDAHL
    "CANO COBRE PC C 15.5 MT 4.76X0.790MM UNIV PRE",   # preto, não PREMIO
    "ALAVANCA FREIO MAO GOL/PARATI/SAVEIRO G3 COMP",   # completa, não COMPASS
    "CORREIA ALT/DH/BA FOCUS 1.8 2.0 16V 01/04 VIR",   # virabrequim, não VIRTUS
    "CILINDRO RODA TRAS CELTA 03/ PRISMA 07/12 ATE",   # marca ATE, não ATEGO
    "TENSOR CORREIA DENT L200/L300/PAJERO/L200 SPO",   # L200 Sport, não SPORTAGE
    "BUZINA GRAVE D20 85/96 12V S/RELE 2 TERM (UNI",   # universal, não UNIGRAX
    "CHAVE LIMP PARAB D20 OPALA 81/ P-UP 85/ C/TEM",   # temporizador, não TEMPRA
    "JUNTA CABEC PALIO 1.0 FIR",                       # curta: não foi cortada
    "JUNTA TAMPA VALV GOL/PARATI 1.0 97/ 8V AT SPA",   # Spazio ou Spacefox
    "LAMPADA FAROL H9 12V 65W OMEGA CD 3.6 V6/ SEN",   # sensor? nome de peça também concorre
    "CORPO BORBOLETA CORSA 1.4/1.8 06/ MPFI 8V PAL",   # Palio ou palheta
])
def test_nao_completa_quando_nao_ha_certeza(descricao):
    assert completar_final(descricao) == descricao


def test_final_completado_vale_para_motor_e_marca():
    assert normalizar("CORREIA GIR/ALT PALIO 1.0/1.3 8/16V 2000/ FIR").atributos.familias == {"FIRE"}
    assert normalizar("PALHETA LIMP PARAB UNIVERSAL 16 POLEGADAS WUR").peca.endswith("wurth")
