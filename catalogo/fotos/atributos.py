"""Atributos que separam peças do mesmo carro: motor, geração, quantidade e o que a descrição exclui.

A mesma tabela de regex lê a descrição da planilha e o título do anúncio; `conflitos` compara os dois.
Conflito nunca reprova sozinho: manda o grupo para a revisão do Agy (erros dos pilotos 1 e 2:
correia 306 2.0 com foto de 1.6, mangote de Uno 85 com foto de Novo Uno, amortecedor avulso com foto do par).

Função pura: nada de rede, banco ou modelo aqui.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from catalogo.fotos.dados.veiculos import VEICULOS

# Cilindrada "1.6"/"1,6"; o que vem colado em X, dígito ou unidade é medida ("40x62x20.5", "1.5 mm").
_CILINDRADA = re.compile(r"(?<![\d.,X])([1-7])[.,](\d)(?![\d.,])(?!\s?(?:MM|CM|M|W|KG|A)\b)")
_MIL = re.compile(r"(?<![\w.])1000(?![\d.])")                      # "GOL 1000" = 1.0; "F1000" é carro
# "8V", "16V", "8/16V". 12V/24V ficam de fora: na elétrica são voltagem.
_VALVULAS = re.compile(r"(?<![\d.])(8|16)(?:/(8|16))?\s?V(?:ALVULAS)?(?![A-Z0-9])")
# Família → padrões. MI (multi-injeção) não entra: é tipo de injeção, convive com AT/EA111.
_FAMILIAS: dict[str, str] = {
    "AP": r"\bAP\b", "CHT": r"\b(?:CHT|AE)\b", "FIRE": r"\b(?:FIRE|EVO)\b", "ZETEC": r"\bZETEC\b",
    "ROCAM": r"\bROCAM\b", "SIGMA": r"\bSIGMA\b", "ETORQ": r"\bE[-.\s]?TORQ\b", "MWM": r"\bMWM\b",
    "PERKINS": r"\bPERKINS\b", "MAXION": r"\bMAXION\b", "CUMMINS": r"\bCUMMINS\b",
}
_ROMANOS = {"I": "1", "II": "2", "III": "3", "IV": "4", "V": "5", "VI": "6", "VII": "7", "VIII": "8"}
_GERACAO = re.compile(r"\bG([1-8]|I{2,3}|IV|VI{0,3})\b")
_CARROS = "|".join(sorted(VEICULOS, key=len, reverse=True))
# "Novo" só é geração colado no carro ("Novo Uno", "UNO NOVO"); solto no anúncio é peça nova.
_NOVO = re.compile(rf"\b(?:NOVO|NOVA|NEW)\s+(?:{_CARROS})\b|\b(?:{_CARROS})\s+(?:NOVO|NOVA|NEW)\b")
_EXCETO = re.compile(r"\bEXC\b")
# Anúncio de mais de uma peça. Kit/combo já têm sinal próprio (titulo_kit) em verificar.py.
_CONJUNTO_ANUNCIO = re.compile(
    r"\b(?:PAR|PARES|JOGO|JOGOS|JG|CONJUNTO)\b"
    r"|\b(?:[2-9]|1\d)\s?(?:X|UN|UNID|UNIDADES|PCS|PECAS)\b"
    r"|^\s*(?:[2-9]|1\d)\s+[A-Z]")
# Na planilha "PAR" é Parati. Conjunto é o que o nome diz ou a peça que só se vende em jogo.
_CONJUNTO_PRODUTO = frozenset({"JG", "JOGO", "KIT", "CJ", "CONJUNTO"})
_VENDIDAS_EM_JOGO = frozenset({"PASTILHA", "PASTILHAS", "SAPATA", "SAPATAS", "LONA", "LONAS", "VELA", "VELAS",
                               "CABOS", "ANEIS", "BRONZINA"})


@dataclass(frozen=True)
class Atributos:
    cilindradas: frozenset[str] = frozenset()   # {"1.0", "1.6"}
    familias: frozenset[str] = frozenset()      # {"AP"}, {"FIRE"}
    valvulas: frozenset[str] = frozenset()      # {"8V", "16V"}
    geracoes: frozenset[str] = frozenset()      # {"G4"}, {"NOVO"}
    em_conjunto: bool = False                   # par, jogo, "2x"...
    excluidos: frozenset[str] = frozenset()     # palavras depois de EXC na planilha: {"ADV"}
    palavras: frozenset[str] = frozenset()      # todas as palavras (só do anúncio, para checar exclusões)

    @property
    def chave(self) -> str:
        """Pedaço da chave do grupo: produtos com motor ou geração diferentes não dividem foto."""
        partes = [*sorted(self.cilindradas), *sorted(self.familias), *sorted(self.valvulas), *sorted(self.geracoes)]
        if self.excluidos:
            partes.append("exc:" + ",".join(sorted(self.excluidos)))
        return " ".join(partes)


def _maiusculo(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto.upper()).encode("ascii", "ignore").decode()


def _palavras(texto: str) -> frozenset[str]:
    return frozenset(re.findall(r"[A-Z0-9]+", texto))


def _ler(texto: str) -> dict:
    cilindradas = {f"{a}.{b}" for a, b in _CILINDRADA.findall(texto)}
    if _MIL.search(texto):
        cilindradas.add("1.0")
    valvulas = {f"{v}V" for par in _VALVULAS.findall(texto) for v in par if v}
    geracoes = {"G" + _ROMANOS.get(g, g) for g in _GERACAO.findall(texto)}
    if _NOVO.search(texto):
        geracoes.add("NOVO")
    return {"cilindradas": frozenset(cilindradas), "valvulas": frozenset(valvulas), "geracoes": frozenset(geracoes),
            "familias": frozenset(f for f, p in _FAMILIAS.items() if re.search(p, texto))}


def do_produto(descricao: str) -> Atributos:
    texto = _maiusculo(descricao)
    m = _EXCETO.search(texto)
    incluido, excluido = (texto[:m.start()], texto[m.end():]) if m else (texto, "")
    palavras_incluidas = _palavras(incluido)
    excluidos = frozenset(p for p in _palavras(excluido) if p.isalpha() and len(p) >= 2) - palavras_incluidas
    toks = [t for t in re.split(r"[\s/]+", incluido) if t]
    em_conjunto = bool(toks) and (toks[0] in _VENDIDAS_EM_JOGO or bool(_CONJUNTO_PRODUTO & set(toks)))
    return Atributos(**_ler(incluido), em_conjunto=em_conjunto, excluidos=excluidos)


def do_anuncio(titulo: str) -> Atributos:
    texto = _maiusculo(titulo)
    return Atributos(**_ler(texto), em_conjunto=bool(_CONJUNTO_ANUNCIO.search(texto)), palavras=_palavras(texto))


def _excluido_citado(excluidos: frozenset[str], palavras: frozenset[str]) -> bool:
    """'ADV' na planilha casa 'ADVENTURE' no anúncio; sigla de 2 letras ('SP') só casa inteira."""
    return any(p == e or (len(e) >= 3 and p.startswith(e)) for e in excluidos for p in palavras)


def conflitos(produto: Atributos, anuncio: Atributos) -> list[str]:
    """Motivos de revisão: o anúncio afirma algo que o produto contradiz. Quem não diz não conflita."""
    motivos = []
    for campo, motivo in (("cilindradas", "cilindrada_diferente"), ("familias", "familia_diferente"),
                          ("valvulas", "valvulas_diferente"), ("geracoes", "geracao_diferente")):
        p, a = getattr(produto, campo), getattr(anuncio, campo)
        if p and a and not (p & a):
            motivos.append(motivo)
    if "NOVO" in anuncio.geracoes and "NOVO" not in produto.geracoes and "geracao_diferente" not in motivos:
        motivos.append("geracao_novo")
    if anuncio.em_conjunto and not produto.em_conjunto:
        motivos.append("quantidade_a_mais")
    if _excluido_citado(produto.excluidos, anuncio.palavras):
        motivos.append("versao_excluida")
    return motivos
