import pytest

from catalogo.fotos.normalizar import Chave, normalizar
from catalogo.fotos.verificar import Sinais, decidir, marca_no_ocr, outra_marca_no_ocr, sinais_de_texto

PASTILHA = normalizar("PASTILHA FREIO DT AGILE/CELTA/CORSA/PRISMA")
OLEO = normalizar("OLEO MOTOR 15W40 PETRONAS SYNTIUM 800 SE")
BIELETA_LD = normalizar("BIELETA ESTAB DT S10/TRAILBLAZER 12/ LD")
PNEU = normalizar("PNEU 175/75 R13 GOLDEN CROWN 85T PRETO NA")


def test_titulo_bom_de_mercado_livre():
    s = sinais_de_texto(PASTILHA, "Pastilha De Freio Dianteira Agile 2009 2010 Cobreq")
    assert s == {"titulo_peca": True, "titulo_veiculo": True, "titulo_spec": True,
                 "titulo_conflito": False, "titulo_marca": True}


def test_carro_alternativo_tambem_vale_e_bomba_dagua_com_apostrofo():
    assert sinais_de_texto(PASTILHA, "Jogo Pastilha Freio Dianteiro Celta 1.0")["titulo_veiculo"]
    bomba = normalizar("BOMBA DAGUA PALIO/UNO/ 1.0/1.5 99/04")
    assert sinais_de_texto(bomba, "Bomba D'água Fiat Palio Fire 1.0 8v")["titulo_peca"]


def test_posicao_e_lado_opostos_sao_conflito():
    assert sinais_de_texto(PASTILHA, "Pastilha Freio Traseira Agile")["titulo_conflito"]
    assert not sinais_de_texto(PASTILHA, "Pastilha Freio Dianteira E Traseira Agile")["titulo_conflito"]
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
                 ocr_marca=True, dominio_loja=True, fundo_branco=True)


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
