from catalogo.fotos.atributos import Atributos, conflitos, do_anuncio, do_produto


def test_motor_do_produto():
    a = do_produto("CORREIA ALT 306/405 2.0 16V 93/98")
    assert a.cilindradas == {"2.0"} and a.valvulas == {"16V"}
    b = do_produto("BOBINA IGNICAO GOL 1.0 MI 8/16V 97/ ALC/GAS 3")
    assert b.cilindradas == {"1.0"} and b.valvulas == {"8V", "16V"}
    assert do_produto("BRONZINA BIELA STD GOL 1000 MI AT 16 /07").cilindradas == {"1.0"}
    assert do_produto("BOMBA DAGUA GOL/SAVEIRO 1.6/1.8 95/").cilindradas == {"1.6", "1.8"}


def test_familia_do_motor():
    assert do_produto("JUNTA CARTER GOL/CORCEL/ESCORT CHT AE 1.3/1.6").familias == {"CHT"}
    assert do_produto("MANGOTE SUP RADIAD UNO 1.0/1.4 8V MT EVO 10/").familias == {"FIRE"}
    assert do_produto("CORREIA GIR/ALT/ACD PUNTO 1.6 E-TORQ 10").familias == {"ETORQ"}
    assert do_produto("FILTRO OLEO F1000 92/ MWM D229/4 92/ ASP").familias == {"MWM"}
    # MI é tipo de injeção, não família: não pode brigar com "AT/EA111" do anúncio (tensor #42 do piloto 2)
    assert do_produto("TENSOR CORREIA DENT GOL/PARATI 1.0 8V MI 97/").familias == frozenset()


def test_voltagem_nao_e_valvula():
    assert do_produto("BUZINA GRAVE D20 85/96 12V S/RELE 2 TERM").valvulas == frozenset()


def test_geracao():
    assert do_produto("CUBO RODA TRAS GOL/SAV GV 08/VOYAGE GVI 13/ S").geracoes == {"G5", "G6"}
    assert do_produto("CABO CAPO GOL 08/ GOL/PARATI/SAVEIRO GIII/GIV").geracoes == {"G3", "G4"}
    assert do_produto("IMPULSOR MTR PART PALIO/IDEA/STRADA/UNO NOVO").geracoes == {"NOVO"}
    assert do_anuncio("Mangote Superior Do Radiador Fiat Novo Uno/mobi").geracoes == {"NOVO"}
    # "Novo" longe do carro é peça nova, não geração (grade #27 do piloto 2)
    assert do_anuncio("Grade Parachoque Dianteiro Corolla 2012 2013 2014 Novo").geracoes == frozenset()


def test_exceto_nao_vira_atributo_do_produto():
    a = do_produto("PARABRISA DIANT UNO 99/14 UNO EXC UNO NOVO")
    assert a.geracoes == frozenset() and "NOVO" in a.excluidos
    assert do_produto("AMORT DT IDEA 05/ EXC ADV").excluidos == {"ADV"}


def test_par_na_planilha_e_parati_no_anuncio_e_quantidade():
    assert not do_produto("ALAVANCA CAPO GOL/PAR/SAV").em_conjunto
    assert do_anuncio("2 Amortecedor Dianteiro Idea 1.6 16v 2005 Par").em_conjunto
    assert do_anuncio("5x Parafusos Roda Gol G1 G2").em_conjunto
    assert do_anuncio("Jogo De Vela Ignição Gol G4 1.0 8v").em_conjunto
    assert not do_anuncio("Amortecedor Dianteiro Idea Cofap").em_conjunto
    assert not do_anuncio("Rolamento Cardan Hilux 4x4").em_conjunto
    assert do_produto("PASTILHA FREIO DT PALIO 11/ DOBLO/PUNTO/STRAD").em_conjunto   # vendida em jogo
    assert do_produto("VELAS IGN GOL G5/VOY/FOX 1.0/1.6 8V PAR/SAV/P").em_conjunto


def test_medidas_nao_viram_cilindrada():
    assert do_anuncio("Rolamento Compressor 40x62x20.5 Palio").cilindradas == frozenset()
    assert do_anuncio("Pneu 31x10.50 R15").cilindradas == frozenset()
    assert do_anuncio("Correia Alternador Fiat Ducato 2.8 Diesel").cilindradas == {"2.8"}
    assert do_anuncio("Kit Correia Tucson 2,7 V6").cilindradas == {"2.7"}


def _motivos(descricao: str, titulo: str) -> list[str]:
    return conflitos(do_produto(descricao), do_anuncio(titulo))


def test_conflitos_dos_erros_dos_pilotos():
    assert "cilindrada_diferente" in _motivos(
        "CORREIA ALT 306/405 2.0 16V 93/98",
        "Correia Alternador GM Blazer S10 2.2 Hyundai HB20 1.0 Peugeot 306 1.6")
    assert "cilindrada_diferente" in _motivos(
        "KIT CORR DENTAD/TENS TUCSON/I30 2.0 16V 06/", "Kit Correia Dentada Tucson 2.7 24v V6 2006 2007 2008")
    assert "cilindrada_diferente" in _motivos(
        "SAPATA FREIO FRONTIER 2.5 02/", "Sapata Lona Freio Frontier 2.8 Tdi 2002 A 2008")
    assert "geracao_novo" in _motivos(
        "MANGOTE SUP RADIAD UNO/PREMIO/ELBA 1.3/1.5 85", "Mangote Superior Do Radiador Fiat Novo Uno/mobi")
    assert "quantidade_a_mais" in _motivos(
        "AMORT DT IDEA 05/ EXC ADV", "2 Amortecedor Dianteiro Idea 1.6 16v 2005 2006 2007 2008 Par")
    assert "versao_excluida" in _motivos("AMORT DT IDEA 05/ EXC ADV", "Amortecedor Dianteiro Idea Adventure")


def test_sem_conflito_quando_bate_ou_o_anuncio_nao_diz():
    assert _motivos("FILTRO AR COROLLA 1.6 1.8 FLEX 08/", "Filtro De Ar Corolla 2008 A 2023 Jfa0285 Wega") == []
    assert _motivos("BOMBA DAGUA GOL/SAVEIRO 1.6/1.8 95/", "Bomba D'água Gol 1.8 Ap") == []
    assert _motivos("CABO CAPO GOL 08/ GOL/PARATI/SAVEIRO GIII/GIV",
                    "Cabo Abertura Capô Com Alavanca Gol G4 2006/2014") == []
    assert _motivos("PASTILHA FREIO DT PALIO 11/ DOBLO/PUNTO/STRAD",
                    "Jogo Pastilha Freio Dianteira 500 - Palio 2011 A 2015") == []
    assert _motivos("JUNTA CARTER GOL CHT 1.6", "Junta Carter Gol AP 1.6") == ["familia_diferente"]
    assert conflitos(Atributos(), do_anuncio("Qualquer Coisa 2.0 16v Par")) == ["quantidade_a_mais"]


def test_chave_compacta_para_o_grupo():
    assert do_produto("CORREIA ALT 306/405 2.0 16V 93/98").chave == "2.0 16V"
    assert do_produto("AMORT DT IDEA 05/ EXC ADV").chave == "exc:ADV"
    assert do_produto("ALAVANCA CAPO GOL/PAR/SAV").chave == ""


def test_exc_dentro_de_outra_palavra_nao_e_exceto():
    a = do_produto("POLIA EXCENTRICA GOL 1.6 EXC SAVEIRO")
    assert a.cilindradas == {"1.6"} and a.excluidos == {"SAVEIRO"}
