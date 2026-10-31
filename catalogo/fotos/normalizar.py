"""Descrição abreviada da planilha → chave do grupo de foto e consultas de busca.

    "PASTILHA FREIO DT AGILE/CELTA/CORSA/PRISMA"
    → Chave(peca="pastilha freio dianteiro", veiculo="agile", veiculo_alt="celta", tipo_en="brake pad")
    → consulta "pastilha freio dianteiro agile"

Função pura: nada de rede, banco ou modelo aqui.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from catalogo.fotos.atributos import FAMILIAS, Atributos, do_produto
from catalogo.fotos.dados.marcas import MARCAS, MARCAS_COMPOSTAS, MARCAS_PNEU
from catalogo.fotos.dados.siglas import SIGLAS, SIGLAS_COMPOSTAS
from catalogo.fotos.dados.tipos_en import TIPOS_EN
from catalogo.fotos.dados.veiculos import MODELOS_NUMERICOS, MONTADORAS, VEICULOS, VEICULOS_ABREV

# Vendidos pela marca, não pelo carro: só neles a marca entra na chave; sem marca reconhecida, nunca há
# aprovação automática. Nas outras peças a marca é ignorada.
CONSUMIVEIS = frozenset({
    "oleo", "aditivo", "graxa", "tinta", "aromatizante", "silicone", "cola", "adesivo", "limpa",
    "descarbonizante", "desengripante", "thinner", "cera", "lubrificante", "fluido", "bateria", "pneu",
    "camara", "lampada", "fita", "lixa", "massa", "spray", "removex", "agua", "catalisador", "anti",
    "difusor", "estopa", "grafite", "verniz", "primer", "polidor",
})
# Nesses tipos não há carro: "205" é medida ("PNEU 205/65 R15") e "BLAZER" é modelo do pneu.
TIPOS_SEM_VEICULO = frozenset({"PNEU", "CAMARA"})
_DESCARTAR = frozenset({"C", "S", "P", "E", "DE", "DO", "DA", "PARA", "LD", "LE"})


@dataclass(frozen=True)
class Chave:
    peca: str
    veiculo: str = ""
    veiculo_alt: str = ""
    lado: str = ""          # "direito" | "esquerdo" | ""
    marca: str = ""         # como na lista de marcas, com espaço: "GOLDEN CROWN"
    tipo_pt: str = ""       # prefixo da peça que casou em TIPOS_EN: "pastilha freio"
    tipo_en: str = ""       # rótulo do CLIP: "brake pad"
    marca_incerta: bool = False
    e_tipo: bool = False    # grupo de foto genérica por tipo de peça
    anos: str = ""          # faixa do 1º carro: "2012-2014", "2008-" (em diante), "-2013" (até); "" = sem ano
    atributos: Atributos = Atributos()   # motor, geração, exclusões (só com carro: sem carro "1.5" não é motor)

    @classmethod
    def para_tipo(cls, tipo_pt: str, tipo_en: str) -> "Chave":
        return cls(peca=tipo_pt, tipo_pt=tipo_pt, tipo_en=tipo_en, e_tipo=True)

    @property
    def texto(self) -> str:
        if self.e_tipo:
            return f"TIPO:{self.peca}"
        base = f"{self.peca}|{self.veiculo}|{self.lado}|{self.marca}|{self.anos}"
        return f"{base}|{self.atributos.chave}" if self.atributos.chave else base

    @property
    def faixa(self) -> tuple[int | None, int | None]:
        """(ano inicial, ano final); None = aberto. Sem ano na descrição: (None, None)."""
        if not self.anos:
            return None, None
        ini, _, fim = self.anos.partition("-")
        return (int(ini) if ini else None), (int(fim) if fim else None)

    def _montar(self, veiculo: str, com_ano: bool = False) -> str:
        partes = [self.peca, veiculo]
        if com_ano and self.anos:
            ini, fim = self.faixa
            partes.append(str(ini or fim))   # geração do carro: o anúncio certo costuma citar o ano
        if self.marca and self.marca.lower() not in self.peca:
            partes.append(self.marca.lower())
        if self.lado:
            partes.append(f"lado {self.lado}")
        return " ".join(p for p in partes if p)

    @property
    def consulta(self) -> str:
        return self.peca if self.e_tipo else self._montar(self.veiculo, com_ano=True)

    @property
    def consulta_alt(self) -> str:
        """2ª tentativa: o segundo carro citado, ou a peça sem carro. Vazio quando não há alternativa."""
        if self.e_tipo or not self.veiculo:
            return ""
        return self._montar(self.veiculo_alt)


def _preparar(descricao: str) -> str:
    d = f" {descricao.upper()} "
    d = re.sub(r"[()\[\]\"'|]", " ", d)
    d = re.sub(r"\bL/D\b", " LD ", d)
    d = re.sub(r"\bL/E\b", " LE ", d)
    d = re.sub(r"\bD/E\b", " ", d)
    d = re.sub(r"\b([CS])/", r" \1_ ", d)
    d = re.sub(r"([A-Z]{3,})(\d\.\d)", r"\1 \2", d)   # "CORSA1.0" → "CORSA 1.0"
    for padrao, troca in SIGLAS_COMPOSTAS:
        d = re.sub(padrao, troca, d)
    for nome in MARCAS_COMPOSTAS:
        d = d.replace(nome, nome.replace(" ", "_"))
    return d


# "12/14", "08/" (em diante), "/13" (até), "2017/". O que vem colado em dígito, ponto, X ou barra não é ano:
# "1.6/1.8" e "8/16V" são motor, "206/207" e "C10/14/15" são carros, "07.89/" é mês.ano, "60/55W" é potência.
_ANO = re.compile(
    r"(?<![\d.,X/])((?:19|20)\d{2})/((?:19|20)?\d{2})?(?![\d.])"
    r"|(?<![\d.,X/])(\d{2})/(\d{2})?(?![\d.VW])"
    r"|(?<![\d.\w])/(\d{2})(?![\d.])"
)


def _ano(texto: str | None) -> int | None:
    if not texto:
        return None
    n = int(texto)
    if n < 100:
        n += 1900 if n >= 50 else 2000
    return n


def _faixa_de_anos(preparada: str, token_do_veiculo: str) -> str:
    """Faixa de anos que vem logo depois do primeiro carro citado ('' se não houver ou não fizer sentido)."""
    onde = re.search(r"(?<![A-Z0-9])" + re.escape(token_do_veiculo) + r"(?![A-Z0-9])", preparada)
    m = _ANO.search(preparada, onde.end()) if onde else None
    if not m:
        return ""
    if m.group(5):
        ini, fim = None, _ano(m.group(5))
    else:
        ini, fim = _ano(m.group(1) or m.group(3)), _ano(m.group(2) or m.group(4))
    validos = [a for a in (ini, fim) if a is not None]
    if any(not 1950 <= a <= 2035 for a in validos) or (ini and fim and fim < ini):
        return ""
    return f"{ini or ''}-{fim or ''}"


def tokens(descricao: str) -> list[str]:
    return [t for t in re.split(r"[\s/,]+", _preparar(descricao)) if re.search(r"[A-Z0-9]", t)]


def _expandir(t: str) -> str:
    if t == "C_":
        return "com"
    if t == "S_":
        return "sem"
    if t in MARCAS:
        return t.replace("_", " ").lower()
    return SIGLAS.get(t, t.lower())


def _modelo(t: str, sem_veiculo: bool) -> str:
    if sem_veiculo:
        return ""   # pneu "BLAZER COMPASAL": Blazer é o modelo do pneu, não o carro
    if t in VEICULOS_ABREV:
        return VEICULOS_ABREV[t]
    if t in VEICULOS:
        return t.lower()
    if t in MODELOS_NUMERICOS:
        return t.lower()
    return ""


def _juntar(palavras) -> str:
    lista = [p for p in palavras if p]
    while lista and lista[-1] in ("com", "sem"):
        lista.pop()
    return " ".join(" ".join(lista).split())


def _tipo(peca: str) -> tuple[str, str]:
    palavras = peca.split()
    for n in (3, 2, 1):
        prefixo = " ".join(palavras[:n])
        if len(palavras) >= n and prefixo in TIPOS_EN:
            return prefixo, TIPOS_EN[prefixo]
    return "", ""


LIMITE_PLANILHA = 45   # o ERP corta a descrição no 45º caractere
_COMBUSTIVEIS = frozenset({"DIESEL", "GASOLINA", "FLEX", "ALCOOL", "TURBO"})
# Palavras comuns que também começam como carro ou marca: "POL" é polia (não POLO), "3 BAR" é pressão.
_PALAVRAS_COMUNS = frozenset({"POLIA", "SPORT", "BAR", "ATE", "PRETA", "OVAL", "SPAAL"})
# Siglas por extenso e nomes de peça também concorrem: "SEN" pode ser sensor, "PAL" pode ser palheta.
_SIGLAS_POR_EXTENSO = (frozenset(w.upper() for v in SIGLAS.values() for w in v.split())
                       | frozenset(w.upper() for tipo in TIPOS_EN for w in tipo.split()))
_CONHECIDAS = (frozenset(SIGLAS) | frozenset(VEICULOS_ABREV) | frozenset(MONTADORAS) | MARCAS | VEICULOS
               | frozenset(FAMILIAS) | _COMBUSTIVEIS | _SIGLAS_POR_EXTENSO | _PALAVRAS_COMUNS)


def _alvos(pneu: bool) -> frozenset[str]:
    """O que um final cortado pode virar. Em pneu só marca de pneu; no resto, marca de pneu nem concorre."""
    if pneu:
        return MARCAS_PNEU
    return (MARCAS - MARCAS_PNEU) | VEICULOS | frozenset(FAMILIAS) | _COMBUSTIVEIS


_ALVOS = {True: _alvos(True), False: _alvos(False)}
# Abreviações de VEICULOS_ABREV (SAVEIR, ESCORTE) ficam fora dos concorrentes: senão "SAVEI" empata
# entre SAVEIR e SAVEIRO e o completamento certo nunca acontece.
_CONCORRENTES = {pneu: alvos | _SIGLAS_POR_EXTENSO | _PALAVRAS_COMUNS for pneu, alvos in _ALVOS.items()}


def completar_final(descricao: str) -> str:
    """Completa a última palavra cortada pelo ERP ("...16V FIR" → "...16V FIRE") só quando não há dúvida:
    a palavra não é conhecida e exatamente uma palavra do vocabulário começa com ela, e essa palavra é carro,
    marca, família de motor ou combustível. Na dúvida, devolve a descrição como veio."""
    if len(descricao) < LIMITE_PLANILHA:
        return descricao
    m = re.search(r"(?<![A-Z0-9])([A-Z]{3,})$", descricao.upper())
    if not m or m.group(1) in _CONHECIDAS:
        return descricao
    pneu = descricao.upper().split()[0] in TIPOS_SEM_VEICULO
    candidatos = [w for w in _CONCORRENTES[pneu] if w.startswith(m.group(1))]
    if len(candidatos) != 1 or candidatos[0] not in _ALVOS[pneu]:
        return descricao
    return descricao[:m.start(1)] + candidatos[0].replace("_", " ")


def normalizar(descricao: str) -> Chave:
    descricao = completar_final(descricao)
    toks = tokens(descricao)
    if not toks:
        return Chave(peca="")
    sem_veiculo = toks[0] in TIPOS_SEM_VEICULO
    marca = next((t.replace("_", " ") for t in toks if t in MARCAS), "")
    lado = ""
    for t in toks:
        if t == "LD":
            lado = "direito"
        elif t == "LE":
            lado = "esquerdo"

    modelos: list[str] = []
    montadoras: list[str] = []
    cru_modelo = cru_montadora = ""   # como o 1º carro está escrito na descrição (para achar o ano dele)
    fim: int | None = None
    for i, t in enumerate(toks[1:], start=1):
        modelo = _modelo(t, sem_veiculo)
        if modelo and modelo not in modelos:
            cru_modelo = cru_modelo or t
            modelos.append(modelo)
        elif not modelo and t in MONTADORAS and MONTADORAS[t] not in montadoras:
            cru_montadora = cru_montadora or t
            montadoras.append(MONTADORAS[t])
        if fim is None and (modelo or t in MONTADORAS or re.search(r"\d", t)):
            fim = i

    veiculo = modelos[0] if modelos else (montadoras[0] if montadoras else "")
    veiculo_alt = modelos[1] if len(modelos) > 1 else ""
    if veiculo:
        peca = _juntar(_expandir(t) for t in toks[:fim] if t not in _DESCARTAR and t not in MARCAS)
    else:
        # Sem carro (óleo, pneu, lâmpada): medida e marca são o que identifica o item.
        peca = _juntar(_expandir(t) for t in toks if t not in _DESCARTAR)
    tipo_pt, tipo_en = _tipo(peca)
    primeira = peca.split()[0] if peca else ""
    if primeira not in CONSUMIVEIS:
        marca = ""   # peça: foto da peça certa serve, de qualquer marca (stakeholders, 2026-10-30)
    marca_incerta = not veiculo and not marca and primeira in CONSUMIVEIS
    anos = _faixa_de_anos(_preparar(descricao), cru_modelo or cru_montadora) if veiculo else ""
    atributos = do_produto(descricao) if veiculo else Atributos()
    return Chave(peca, veiculo, veiculo_alt, lado, marca, tipo_pt, tipo_en, marca_incerta, anos=anos,
                 atributos=atributos)
