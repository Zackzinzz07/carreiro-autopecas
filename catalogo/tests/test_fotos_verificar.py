import pytest

from catalogo.fotos.normalizar import Chave, normalizar
from catalogo.fotos.verificar import (Sinais, anos_do_titulo, anuncio_na_imagem, decidir, marca_no_ocr,
                                      outra_marca_no_ocr, sinais_de_texto)

PASTILHA = normalizar("PASTILHA FREIO DT AGILE/CELTA/CORSA/PRISMA")
OLEO = normalizar("OLEO MOTOR 15W40 PETRONAS SYNTIUM 800 SE")
BIELETA_LD = normalizar("BIELETA ESTAB DT S10/TRAILBLAZER 12/ LD")
PNEU = normalizar("PNEU 175/75 R13 GOLDEN CROWN 85T PRETO NA")


def test_titulo_bom_de_mercado_livre():
    s = sinais_de_texto(PASTILHA, "Pastilha De Freio Dianteira Agile 2009 2010 Cobreq")
    assert s == {"titulo_peca": True, "titulo_veiculo": True, "titulo_spec": True,
                 "titulo_conflito": False, "titulo_marca": True, "titulo_ano": True, "titulo_kit": False,
                 "titulo_ano_incerto": True, "conflitos": ()}   # PASTILHA não diz o ano; o anúncio diz


def test_carro_alternativo_tambem_vale_e_bomba_dagua_com_apostrofo():
    assert sinais_de_texto(PASTILHA, "Jogo Pastilha Freio Dianteiro Celta 1.0")["titulo_veiculo"]
    bomba = normalizar("BOMBA DAGUA PALIO/UNO/ 1.0/1.5 99/04")
    assert sinais_de_texto(bomba, "Bomba D'água Fiat Palio Fire 1.0 8v")["titulo_peca"]


def test_posicao_e_lado_opostos_sao_conflito():
    assert sinais_de_texto(PASTILHA, "Pastilha Freio Traseira Agile")["titulo_conflito"]
    # anúncio que oferece as duas posições é kit das duas: não serve para produto de uma só
    assert sinais_de_texto(PASTILHA, "Pastilha Freio Dianteira E Traseira Agile")["titulo_conflito"]
    mangote = normalizar("MANGOTE SUP RADIAD UNO 1.0/1.4 8V MT EVO 10/")
    assert sinais_de_texto(mangote, "Mangote Superior Inferior Radiador Uno Elba")["titulo_conflito"]
    assert not sinais_de_texto(mangote, "Mangote Superior Radiador Uno 2012")["titulo_conflito"]
    assert sinais_de_texto(BIELETA_LD, "Bieleta Estabilizadora S10 Lado Esquerdo")["titulo_conflito"]


def test_marca_e_medida_precisam_estar_no_titulo():
    assert not sinais_de_texto(OLEO, "Oleo Motor 15w40 Syntium 800 1 Litro")["titulo_marca"]
    assert sinais_de_texto(OLEO, "Óleo Petronas Syntium 800 15w40 Motor")["titulo_marca"]
    # medida de outro aro: 175/75 R14 não serve para R13
    assert not sinais_de_texto(PNEU, "Kit 2 Pneus 175/75r14 Golden Crown Rp68 87t")["titulo_spec"]
    assert sinais_de_texto(PNEU, "Pneu Golden Crown 175/75 R13 85t Rp26")["titulo_spec"]
    modelo = normalizar("PNEU 195/40R17 81W VI-388 OVATION")
    assert sinais_de_texto(modelo, "Pneu Ovation Vi388 195/40r17 81w")["titulo_spec"]


def test_ocr_de_marca():
    assert marca_no_ocr("MAXON", "@ MXON SW")            # OCR troca letra; semelhança 0,89
    assert not marca_no_ocr("PETRONAS", "ST3OUM 800S2")
    assert marca_no_ocr("GOLDEN CROWN", "GOLDEN CROWN RP68")
    assert outra_marca_no_ocr("CRACHI", "DRLUB MOTORLUB SYNTHETIC PLUS")
    assert outra_marca_no_ocr("MAXON", "MOLLIX 5W30 API SP")
    assert not outra_marca_no_ocr("PETRONAS", "PETRONAS SYNTIUM 800")
    assert not outra_marca_no_ocr("MAGNETI MARELLI", "MARELLI 50")
    assert not outra_marca_no_ocr("BOSCH", "")


TUDO_OK = Sinais(clip_rank=1, titulo_peca=True, titulo_veiculo=True, titulo_spec=True, titulo_marca=True,
                 titulo_ano=True, ocr_marca=True, dominio_loja=True, fundo_branco=True)


def test_aprova_quando_todos_os_sinais_concordam():
    d = decidir(PASTILHA, TUDO_OK)
    assert d.aprovada and d.plausivel and d.motivos == () and d.pontuacao > 0


@pytest.mark.parametrize("mudanca,motivo", [
    ({"clip_rank": 4}, "clip_rank_4"),
    ({"clip_rank": None}, "tipo_sem_rotulo_clip"),
    ({"titulo_peca": False}, "titulo_sem_peca"),
    ({"titulo_veiculo": False}, "titulo_sem_veiculo"),
    ({"titulo_spec": False}, "titulo_sem_medida"),
    ({"titulo_conflito": True}, "titulo_lado_ou_posicao_oposta"),
    ({"titulo_ano": False}, "titulo_ano_fora"),
    ({"titulo_kit": True}, "titulo_kit"),
    ({"imagem_anuncio": True}, "imagem_com_texto_de_vendedor"),
    ({"titulo_ano_incerto": True}, "titulo_ano_produto_sem_ano"),
    ({"conflitos": ("cilindrada_diferente",)}, "cilindrada_diferente"),
])
def test_qualquer_sinal_ruim_manda_para_revisao(mudanca, motivo):
    s = Sinais(**{**TUDO_OK.__dict__, **mudanca})
    d = decidir(PASTILHA, s)
    assert not d.aprovada and d.plausivel and motivo in d.motivos


def test_marca_exige_titulo_e_ocr_sem_outra_marca():
    assert decidir(OLEO, TUDO_OK).aprovada
    sem_marca = decidir(OLEO, Sinais(**{**TUDO_OK.__dict__, "titulo_marca": False}))
    assert not sem_marca.aprovada and "titulo_sem_marca" in sem_marca.motivos
    outra = decidir(OLEO, Sinais(**{**TUDO_OK.__dict__, "ocr_outra_marca": True}))
    assert not outra.aprovada and "ocr_outra_marca" in outra.motivos


def test_tipo_e_marca_incerta_nunca_aprovam_sozinhos():
    assert not decidir(Chave.para_tipo("pastilha freio", "brake pad"), TUDO_OK).aprovada
    lampada = normalizar("LAMPADA FAROL H4 HALOGENA 12V 60/55W")
    d = decidir(lampada, TUDO_OK)
    assert not d.aprovada and "marca_nao_reconhecida" in d.motivos


def test_lixo_e_invalida_nao_sao_nem_plausiveis():
    assert decidir(PASTILHA, Sinais(**{**TUDO_OK.__dict__, "clip_top_lixo": True})).plausivel is False
    assert decidir(PASTILHA, Sinais(valida=False)).plausivel is False


def test_pontuacao_prefere_clip_em_primeiro():
    segundo = decidir(PASTILHA, Sinais(**{**TUDO_OK.__dict__, "clip_rank": 2}))
    assert decidir(PASTILHA, TUDO_OK).pontuacao > segundo.pontuacao


def test_marca_em_embalagem_precisa_ser_lida_no_rotulo():
    """Título com a marca não basta: o anúncio pode citar Petronas e a foto ser de outro frasco."""
    sem_leitura = decidir(OLEO, Sinais(**{**TUDO_OK.__dict__, "ocr_marca": False}))
    assert not sem_leitura.aprovada and sem_leitura.plausivel and "ocr_sem_marca" in sem_leitura.motivos


def test_pneu_dispensa_ocr_porque_a_marca_fica_na_lateral():
    assert decidir(PNEU, Sinais(**{**TUDO_OK.__dict__, "ocr_marca": False})).aprovada


def test_peca_sem_marca_nao_depende_de_ocr():
    assert decidir(PASTILHA, Sinais(**{**TUDO_OK.__dict__, "ocr_marca": False})).aprovada


GRADE = normalizar("GRADE PARACHOQUE DT COROLLA 12/14")


def test_anuncio_de_outra_geracao_do_carro_nao_serve():   # erro R81 do piloto
    assert not sinais_de_texto(GRADE, "Grade Parachoque Dianteiro Corolla 2020 2021 2022")["titulo_ano"]
    assert sinais_de_texto(GRADE, "Grade Parachoque Dianteiro Corolla 2012 2013 2014")["titulo_ano"]
    assert sinais_de_texto(GRADE, "Grade Parachoque Corolla 2009 a 2013")["titulo_ano"]       # faixa que alcança 2012
    assert not sinais_de_texto(GRADE, "Grade Parachoque Corolla 2003 - 2008")["titulo_ano"]
    assert sinais_de_texto(GRADE, "Grade Parachoque Dianteiro Corolla")["titulo_ano"]          # sem ano: não dá para negar
    aberto = normalizar("AMORT DT UNO 10/")
    assert sinais_de_texto(aberto, "Amortecedor Dianteiro Uno 2015")["titulo_ano"]
    assert not sinais_de_texto(aberto, "Amortecedor Dianteiro Uno 1995 a 2004")["titulo_ano"]
    assert sinais_de_texto(PASTILHA, "Pastilha Freio Dianteira Agile 2011")["titulo_ano"]      # produto sem ano
    assert anos_do_titulo("Cabo 2009 2010 e 2015 a 2017 ref 123456") == {2009, 2010, 2015, 2016, 2017}


def test_kit_com_pecas_a_mais_nao_aprova_sozinho():       # erros R33, R52, R70 do piloto
    correia = normalizar("CORREIA ALT 306/405 2.0 16V 93/98")
    assert sinais_de_texto(correia, "Kit Correia Alternador Polias Peugeot 306 1.8 16v")["titulo_kit"]
    assert sinais_de_texto(PASTILHA, "Par Amortecedor + Kit Batente Agile")["titulo_kit"]
    assert not sinais_de_texto(correia, "Correia Alternador Peugeot 306 Dayco 6pk1035")["titulo_kit"]
    assert not sinais_de_texto(correia, "Par Correia Alternador 306")["titulo_kit"]
    embreagem = normalizar("KIT EMBR GOL 1.0 8V 97/")          # o próprio produto é um kit
    assert not sinais_de_texto(embreagem, "Kit Embreagem Gol 1.0 Luk")["titulo_kit"]


def test_telefone_ou_propaganda_de_vendedor_na_imagem():  # erro R14 do piloto
    assert anuncio_na_imagem("VOLKSWAGEN 67 DDD 3416-2172 CARACTERISTICAS MARCA")
    assert anuncio_na_imagem("SD SAO DOMINGOS AUTO PECAS")
    assert anuncio_na_imagem("PECA NO WHATSAPP")
    assert anuncio_na_imagem("WWW.LOJA.COM.BR")
    assert not anuncio_na_imagem("BOSCH 0 986 B01 000 OB 1000")
    assert not anuncio_na_imagem("TOYOTA 17801-21050 DENSO PECA ORIGINAL")
    assert not anuncio_na_imagem("")


def test_produto_sem_ano_e_anuncio_com_ano_vai_para_revisao():   # pastilha Corolla GLi x "2019 a 2023" (piloto 2)
    corolla = normalizar("PASTILHA FREIO TRAS COROLLA 1.8 16V GLI/XLI")
    assert sinais_de_texto(corolla, "Pastilha Freio Cerâmica Traseira Corolla 2019 a 2023")["titulo_ano_incerto"]
    assert not sinais_de_texto(corolla, "Pastilha Freio Traseira Corolla 1.8")["titulo_ano_incerto"]
    assert not sinais_de_texto(GRADE, "Grade Parachoque Dianteiro Corolla 2012 2013 2014")["titulo_ano_incerto"]
    # sem carro, ano no anúncio não diz geração nenhuma
    assert not sinais_de_texto(OLEO, "Oleo Petronas Syntium 800 15w40 2024")["titulo_ano_incerto"]


def test_atributos_do_produto_contra_o_anuncio():   # erros dos pilotos 1 e 2
    correia = normalizar("CORREIA ALT 306/405 2.0 16V 93/98")
    titulo = "Correia Alternador GM Blazer S10 2.2 Hyundai HB20 1.0 Peugeot 306 1.6"
    assert sinais_de_texto(correia, titulo)["conflitos"] == ("cilindrada_diferente",)
    idea = normalizar("AMORT DT IDEA 05/ EXC ADV")
    assert sinais_de_texto(idea, "2 Amortecedor Dianteiro Idea 2005 2006 Par")["conflitos"] == ("quantidade_a_mais",)
