"""Descrição abreviada da planilha → chave do grupo de foto e consultas de busca.

    "PASTILHA FREIO DT AGILE/CELTA/CORSA/PRISMA"
    → Chave(peca="pastilha freio dianteiro", veiculo="agile", veiculo_alt="celta", tipo_en="brake pad")
    → consulta "pastilha freio dianteiro agile"

Função pura: nada de rede, banco ou modelo aqui.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from catalogo.fotos.dados.marcas import MARCAS, MARCAS_COMPOSTAS
from catalogo.fotos.dados.siglas import SIGLAS, SIGLAS_COMPOSTAS
from catalogo.fotos.dados.tipos_en import TIPOS_EN
from catalogo.fotos.dados.veiculos import MODELOS_NUMERICOS, MONTADORAS, VEICULOS, VEICULOS_ABREV

# Vendidos pela marca, não pelo carro: sem marca reconhecida, nunca há aprovação automática.
CONSUMIVEIS = frozenset({
    "oleo", "aditivo", "graxa", "tinta", "aromatizante", "silicone", "cola", "adesivo", "limpa",
    "descarbonizante", "desengripante", "thinner", "cera", "lubrificante", "fluido", "bateria", "pneu",
    "camara", "lampada", "fita", "lixa", "massa", "spray", "removex", "agua", "catalisador", "anti",
    "difusor", "estopa", "grafite", "verniz", "primer", "polidor",
})
# Nesses tipos número de 3 dígitos é medida ("PNEU 205/65 R15"), não Peugeot 205.
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

    @classmethod
    def para_tipo(cls, tipo_pt: str, tipo_en: str) -> "Chave":
        return cls(peca=tipo_pt, tipo_pt=tipo_pt, tipo_en=tipo_en, e_tipo=True)

    @property
    def texto(self) -> str:
        if self.e_tipo:
            return f"TIPO:{self.peca}"
        return f"{self.peca}|{self.veiculo}|{self.lado}|{self.marca}"

    def _montar(self, veiculo: str) -> str:
        partes = [self.peca, veiculo]
        if self.marca and self.marca.lower() not in self.peca:
            partes.append(self.marca.lower())
        if self.lado:
            partes.append(f"lado {self.lado}")
        return " ".join(p for p in partes if p)

    @property
    def consulta(self) -> str:
        return self.peca if self.e_tipo else self._montar(self.veiculo)

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
    for padrao, troca in SIGLAS_COMPOSTAS:
        d = re.sub(padrao, troca, d)
    for nome in MARCAS_COMPOSTAS:
        d = d.replace(nome, nome.replace(" ", "_"))
    return d


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
    if t in VEICULOS_ABREV:
        return VEICULOS_ABREV[t]
    if t in VEICULOS:
        return t.lower()
    if not sem_veiculo and t in MODELOS_NUMERICOS:
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


def normalizar(descricao: str) -> Chave:
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
    fim: int | None = None
    for i, t in enumerate(toks[1:], start=1):
        modelo = _modelo(t, sem_veiculo)
        if modelo and modelo not in modelos:
            modelos.append(modelo)
        elif not modelo and t in MONTADORAS and MONTADORAS[t] not in montadoras:
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
    marca_incerta = not veiculo and not marca and primeira in CONSUMIVEIS
    return Chave(peca, veiculo, veiculo_alt, lado, marca, tipo_pt, tipo_en, marca_incerta)
