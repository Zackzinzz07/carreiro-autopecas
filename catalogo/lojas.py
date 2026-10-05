"""As 5 filiais. Fonte: array LOJAS do protótipo; telefones conferem com a landing (index.html)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Loja:
    slug: str
    cidade: str
    uf: str
    endereco: str
    fone: str
    whatsapp: str  # só dígitos, com DDI (55) + DDD
    matriz: bool = False
    papel: str = "Loja"


LOJAS: list[Loja] = [
    Loja("poranga", "Poranga", "CE", "Tv. Dr. Epitácio de Pinho, 537 — Centro, Poranga/CE · CEP 62220-000",
         "(88) 99727-0713", "5588997270713", matriz=True, papel="Matriz e centro de distribuição"),
    Loja("pedro-ii", "Pedro II", "PI", "Av. Dr. José Lourenço Mourão, 66 — Chapadinha, Pedro II/PI · CEP 64255-000",
         "(86) 99533-7823", "5586995337823"),
    Loja("piripiri", "Piripiri", "PI", "Av. Aderson Alves Ferreira, 1877 — Paciência, Piripiri/PI · CEP 64260-000",
         "(86) 99443-2802", "5586994432802"),
    Loja("campo-maior", "Campo Maior", "PI", "Av. Heróis do Jenipapo, 1977 — Matadouro, Campo Maior/PI · CEP 64280-000",
         "(86) 99478-4497", "5586994784497"),
    Loja("jose-de-freitas", "José de Freitas", "PI", "Av. Gov. Petrônio Portela, s/n — Centro, José de Freitas/PI · CEP 64110-000",
         "(86) 99835-8408", "5586998358408"),
]

MATRIZ = next(loja for loja in LOJAS if loja.matriz)
