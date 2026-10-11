"""Modelos e montadoras: marcam onde termina o nome da peça e começa a aplicação.

Extraídos dos tokens frequentes da planilha (2026-10-05) e conferidos à mão.
"""
from __future__ import annotations

VEICULOS: frozenset[str] = frozenset("""
GOL PALIO UNO CORSA SIENA CELTA FIESTA PARATI FOX STRADA HILUX PRISMA KA SAVEIRO VOYAGE POLO ONIX
PREMIO ECOSPORT ELBA FIORINO COROLLA DOBLO ASTRA MONTANA PUNTO VECTRA COBALT GOLF BLAZER MONZA PAMPA
SANTANA MERIVA IDEA CLIO LOGAN AGILE ESCORT SANDERO COURIER MILLE RANGER PAJERO FRONTIER MOBI SPIN
DUCATO LINEA CIVIC OPALA KADETT UP PASSAT TRITON DUSTER TORO KOMBI BELINA ARGO SONIC CROSSFOX FOCUS
ETIOS FIT KWID AMAROK STILO CRONOS JUMPER BOXER VOLARE TEMPRA BESTA TRAILBLAZER SPACEFOX CITY JETTA
TIGRA CAPTUR MARCH VERSA RENEGADE COMPASS FUSCA CORCEL CHEVETTE SPRINTER CARGO SILVERADO ZAFIRA
KANGOO HR TUCSON WEEKEND OROCH CRUZE TIGUAN FUSION BRASILIA VIVACE SW4 HB20 HB20S I30 IX35 CHEVY
CARAVAN OMEGA MASTER BANDEIRANTE QUANTUM LOGUS IPANEMA RAV4 KICKS TRACKER PICANTO VERANEIO VIRTUS
MEGANE SYMBOL BRAVO EXPLORER SPORTAGE VERONA SCENIC SENTRA CRV HRV TOPIC DAILY LIVINA FLUENCE PICASSO
ACCELO ATEGO PANORAMA TIIDA BONGO CRETA FIELDER XSARA CERATO MARAJO MAREA TRANSIT ACCORD CAMRY
STEPWAY YARIS SOUL SCALA BONANZA CONSTELLATION CONSTELATION BORA SAMARA DELIVERY VERSAILLES C3 C4
S10 D10 D20 D40 D60 C10 C14 C15 C20 C40 A10 A20 A40 F100 F250 F350 F400 F600 F1000 F2000 F4000
F11000 F12000 L200 L300 H100 A3
""".split())

# Abreviações de modelo usadas na planilha → nome por extenso.
VEICULOS_ABREV: dict[str, str] = {
    "SAV": "saveiro", "VOY": "voyage", "PAR": "parati", "PARAT": "parati", "WEEK": "weekend",
    "MONT": "montana", "STRA": "strada", "STRAD": "strada", "FIO": "fiorino", "SANT": "santana",
    "SANTAN": "santana", "KADET": "kadett", "VECTR": "vectra", "VECT": "vectra", "PALI": "palio",
    "SIEN": "siena", "SIE": "siena", "MERI": "meriva", "DOBL": "doblo", "VIRTU": "virtus",
    "BELIN": "belina", "ECOSPORTE": "ecosport", "DELREY": "del rey", "GRANSIENA": "grand siena",
}

# Modelos que são só número. Ignorados em pneu/câmara, onde "205" é medida.
MODELOS_NUMERICOS: frozenset[str] = frozenset(
    {"106", "147", "205", "206", "207", "208", "306", "307", "308", "405", "406", "408", "2008", "3008"}
)

# Montadora só vira "veículo" quando a descrição não cita nenhum modelo.
MONTADORAS: dict[str, str] = {
    "VW": "volkswagen", "FORD": "ford", "FIAT": "fiat", "GM": "chevrolet", "CHEVROLET": "chevrolet",
    "PEUGEOT": "peugeot", "PEUGEOUT": "peugeot", "CITROEN": "citroen", "AUDI": "audi", "HONDA": "honda",
    "HYUNDAI": "hyundai", "KIA": "kia", "NISSAN": "nissan", "JEEP": "jeep", "VOLVO": "volvo",
    "IVECO": "iveco", "SCANIA": "scania", "MBB": "mercedes", "MB": "mercedes", "TOYOTA": "toyota",
    "RENAULT": "renault", "MITSUBISHI": "mitsubishi", "AGRALE": "agrale", "TROLLER": "troller",
}
