import sqlite3
from pathlib import Path

import pytest

from catalogo.fotos.normalizar import Chave, normalizar

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
    ("CORREIA ALT/ACD/DH/BA SCANIA R114", "correia alternador ar condicionado direcao hidraulica ba", "scania", "", "", "", "drive belt"),
    ("ABRACADEIRA 3/4X102X320 CARGO 1313 A 2218 DT", "abracadeira", "cargo", "", "", "", "hose clamp"),
    # Review Focus 1: descrição cortada no fim ("CELT") não atrapalha
    ("BOMBA DAGUA (POLIA C/19 DENTES) AGILE 09/CELT", "bomba dagua polia", "agile", "", "", "", "water pump"),
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
    assert c.texto == "pastilha freio dianteiro|agile||"
    assert c.consulta == "pastilha freio dianteiro agile"
    assert c.consulta_alt == "pastilha freio dianteiro celta"
    lado = normalizar("AMORT DT COROLLA 08/14 L/D")
    assert lado.consulta == "amortecedor dianteiro corolla lado direito"
    assert lado.consulta_alt == "amortecedor dianteiro lado direito"
    oleo = normalizar("OLEO MOTOR 15W40 PETRONAS SYNTIUM 800 SE")
    assert oleo.consulta == "oleo motor 15w40 petronas syntium 800 se" and oleo.consulta_alt == ""
    assert oleo.texto == "oleo motor 15w40 petronas syntium 800 se|||PETRONAS"


def test_mesmo_grupo_para_mesma_peca_e_carro():
    assert normalizar("PASTILHA FREIO DT AGILE/CELTA").texto == normalizar("PASTILHA FREIO DT AGILE 09/ CELTA").texto
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
    assert grupos <= 9_000
