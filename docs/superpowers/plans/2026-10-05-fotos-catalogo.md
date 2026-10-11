# Fotos do Catálogo Carreiro — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dar foto ilustrativa aos 17.149 produtos do catálogo sem publicar foto errada. Na dúvida, o produto fica sem foto.

**Architecture:** Novo pacote `catalogo/fotos/`. A descrição abreviada vira uma chave (peça+carro+lado+marca). Produtos com a mesma chave dividem a foto (~8,5 mil grupos). Cada grupo busca imagens no DuckDuckGo. Cada candidata recebe sinais de texto (título do anúncio), CLIP zero-shot (tipo de peça / lixo) e OCR (marca no rótulo). A aprovação automática só acontece quando todos os sinais concordam; o resto vai para a fila do Agy (folhas de contato + script de decisão). Aprovar um grupo propaga `produtos.imagem_url` e o card mostra a foto com o selo "Imagem ilustrativa".

**Tech Stack:** Python 3.12 em venv separado (`catalogo/.venv-fotos`), SQLite, `ddgs` 9.16, Pillow, `open_clip_torch` (ViT-B-32-quickgelu), `easyocr`, `httpx`, FastAPI/Jinja2 (site já existente), pytest.

**Spec:** `docs/superpowers/specs/2026-10-05-fotos-catalogo-design.md`

## Global Constraints

- Todos os comandos rodam na raiz do repo: `cd "/home/salati/Documentos/projetos/carreiro autopeças/carreiro-autopecas"`.
- O pipeline de fotos e os testes rodam em `catalogo/.venv-fotos/bin/python` (Python 3.12). O venv do site (`catalogo/.venv`, Python 3.14) não ganha torch.
- Pesos dos modelos ficam em `/mnt/dados/cache` (já baixados). Nunca baixar para o disco principal.
- OCR com `quantize=False` (a CPU só tem AVX; a versão quantizada morre com SIGILL).
- "Correto" = tipo de peça + carro (se houver) + lado (se houver) + marca (se houver). **Na dúvida, sem foto.**
- Foto exibida sempre com o selo **"Imagem ilustrativa"**.
- Foto de tipo de peça nunca é aprovada automaticamente e nunca vai para produto com marca.
- Não mexer na landing (`index.html` da raiz). Não fazer deploy. Não dar `git push`.
- Arquivos gerados ficam fora do git: `catalogo/.venv-fotos/`, `catalogo/data/fotos/`, `catalogo/data/fotos_candidatas/`, `catalogo/data/backups/`, `catalogo/revisao/folhas/`.
- Commits terminam com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- **Depois do piloto (Task 11), parar e reportar ao Isac. A execução completa só começa com o aval dele.**

## Review Focus

1. **Descrição cortada no meio de um carro** (`... AGILE 09/CELT`): o pedaço cortado não pode virar peça nem quebrar a chave. Teste em Task 2 (`BOMBA DAGUA (POLIA C/19 DENTES) AGILE 09/CELT`).
2. **Medida de pneu confundida com carro** (`PNEU 205/65 R15` ≠ Peugeot 205), o que juntaria pneus diferentes num grupo só. Teste em Task 2.
3. **Erro de digitação do Agy no comando de decisão** (ID inexistente, índice de candidata fora da faixa, auditoria com número): nada pode ser aplicado pela metade. Teste em Task 8.
4. **Busca interrompida no meio de um grupo** (DuckDuckGo bloqueando, Ctrl+C): o grupo continua `pendente` e é refeito na próxima rodada. Teste em Task 7.
5. **Reimportar a planilha** não pode apagar fotos já aprovadas. Teste em Task 4.

## Desvios em relação ao spec (detalhes de implementação, mesma intenção)

- `fotos/auditar.py` não existe como arquivo: o sorteio da auditoria fica em `executar.py` (no momento da aprovação) e a decisão fica em `revisar.py`.
- As instruções do Agy são dois arquivos (`CONTEXTO_AGY.md` + `PROMPT_AGY.md`) em vez de um `INSTRUCOES_AGY.md` (pedido do Isac em 2026-10-11).
- As folhas do Agy são PNG com 5 grupos cada (mais um `.txt` e um `index.html`), não HTML com 20: é a "folha de contato" que funcionou no Agrocarreiro.
- `foto_grupos` ganhou `descricao_ref`, `e_tipo`, `tipo_pt` e `n_produtos`; `produtos` ganhou também `foto_tipo` (necessário para a foto por tipo de peça).
- Regra extra, mais rígida que o spec: produto sem carro precisa ter as **medidas** no título (`175/75 R13`, `15W40`, `H4`); consumível sem marca reconhecida nunca aprova sozinho.

Código deste plano já validado numa cópia descartável do catálogo (113 testes passando, 29 antigos + 84 novos): normalizador contra os 17.149 produtos reais (100% com peça, 85,7% com rótulo CLIP, 8.539 grupos) e regra de texto contra os títulos reais do spike (nenhuma das 15 imagens ruins passa em texto + CLIP).

---

### Task 1: Ambiente de fotos e padronização de imagem

**Files:**
- Create: `catalogo/requirements-fotos.txt`
- Create: `catalogo/fotos/__init__.py`
- Create: `catalogo/fotos/imagem.py`
- Modify: `.gitignore` (fim do arquivo)
- Test: `catalogo/tests/test_fotos_imagem.py`

**Interfaces:**
- Produces: `imagem.LADO: int = 400`; `imagem.Processada(webp: bytes, fundo_branco: bool)`; `imagem.processar(dados: bytes) -> tuple[Processada | None, str]` (o `str` é o motivo/detalhe); `imagem.termo_placeholder(texto: str) -> bool`; `imagem.sha1(dados: bytes) -> str`.

- [ ] **Step 1: Criar requirements e venv**

`catalogo/requirements-fotos.txt`:

```text
# Pipeline de fotos (catalogo/fotos/). Venv separado (.venv-fotos, Python 3.12): o site não carrega torch.
# Versões iguais às do Agrocarreiro, já testadas nesta máquina (CPU só com AVX).
-r requirements.txt
ddgs==9.16.0
pillow==12.3.0
numpy==2.5.2
torch==2.14.0+cpu
open_clip_torch==3.3.0
easyocr==1.7.2
```

Run:

```bash
uv venv --python 3.12 catalogo/.venv-fotos
uv pip install --python catalogo/.venv-fotos/bin/python -r catalogo/requirements-fotos.txt \
  --index-url https://pypi.org/simple --extra-index-url https://download.pytorch.org/whl/cpu \
  --index-strategy unsafe-best-match
catalogo/.venv-fotos/bin/python -c "import ddgs, PIL, torch, open_clip, easyocr, fastapi; print('ok', torch.__version__)"
```

Expected: `ok 2.14.0+cpu`

- [ ] **Step 2: Ignorar arquivos gerados**

Acrescentar ao fim de `.gitignore`:

```gitignore
# Pipeline de fotos: venv pesado, fotos baixadas, backups e folhas de revisão geradas
catalogo/.venv-fotos/
catalogo/data/fotos/
catalogo/data/fotos_candidatas/
catalogo/data/backups/
catalogo/data/hashes_bloqueados.txt
catalogo/revisao/folhas/
```

- [ ] **Step 3: Escrever o teste que falha**

`catalogo/tests/test_fotos_imagem.py`:

```python
import io

import pytest

pytest.importorskip("PIL")
from PIL import Image, ImageDraw  # noqa: E402

from catalogo.fotos import imagem  # noqa: E402


def _png(tamanho=(300, 300), cor="white", desenho=True, modo="RGB") -> bytes:
    im = Image.new(modo, tamanho, cor)
    if desenho:
        ImageDraw.Draw(im).ellipse((60, 60, tamanho[0] - 60, tamanho[1] - 60), fill="red")
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


def test_packshot_vira_webp_quadrado_com_fundo_branco():
    proc, motivo = imagem.processar(_png())
    assert proc is not None, motivo
    assert proc.webp[:4] == b"RIFF" and proc.webp[8:12] == b"WEBP"
    assert proc.fundo_branco is True
    assert Image.open(io.BytesIO(proc.webp)).size == (imagem.LADO, imagem.LADO)


def test_png_transparente_fica_com_fundo_branco_e_nao_preto():
    proc, _ = imagem.processar(_png(cor=(0, 0, 0, 0), modo="RGBA"))
    assert proc is not None and proc.fundo_branco is True
    # (60, 60) na tela = (10, 10) na imagem original, que era transparente
    fora_da_peca = Image.open(io.BytesIO(proc.webp)).convert("RGB").getpixel((60, 60))
    assert min(fora_da_peca) > 240


def test_cena_com_cantos_diferentes_nao_e_fundo_branco():
    im = Image.new("RGB", (300, 300), "white")
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 150, 150), fill="black")
    d.rectangle((150, 150, 300, 300), fill="blue")
    buf = io.BytesIO()
    im.save(buf, "PNG")
    proc, _ = imagem.processar(buf.getvalue())
    assert proc is not None and proc.fundo_branco is False


@pytest.mark.parametrize("dados,trecho", [(b"", "insuficientes"), (b"isto nao e imagem" * 100, "inválida")])
def test_rejeita_bytes_ruins(dados, trecho):
    proc, motivo = imagem.processar(dados)
    assert proc is None and trecho in motivo


def test_rejeita_pequena_e_proporcao_absurda():
    assert imagem.processar(_png((100, 100), desenho=False))[0] is None
    assert imagem.processar(_png((900, 300)))[0] is None


def test_termo_placeholder_e_sha1():
    assert imagem.termo_placeholder("Imagem indisponível")
    assert imagem.termo_placeholder("https://x.com/no_image.png")
    assert not imagem.termo_placeholder("Pastilha Freio Dianteira Agile")
    assert imagem.sha1(b"abc") == "a9993e364706816aba3e25717850c26c9cd0d89d"
```

- [ ] **Step 4: Rodar e ver falhar**

Run: `catalogo/.venv-fotos/bin/python -m pytest catalogo/tests/test_fotos_imagem.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'catalogo.fotos'`

- [ ] **Step 5: Implementar**

`catalogo/fotos/__init__.py`:

```python
"""Pipeline de fotos do catálogo (ver docs/superpowers/specs/2026-10-05-fotos-catalogo-design.md)."""
```

`catalogo/fotos/imagem.py`:

```python
"""Validação e padronização das fotos candidatas (WebP 400x400 sobre fundo branco).

Adaptado de Agrocarreiro/catalogo/imagens.py. Aqui só se barra defeito técnico;
quem decide se a foto é da peça certa é `verificar.decidir`.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from io import BytesIO

LADO = 400
QUALIDADE = 80
PESO_ALVO = 38_000  # bytes
LADO_MINIMO = 140
PROPORCAO_MAXIMA = 2.1
VARIACAO_MAXIMA_CANTOS = 45

_PLACEHOLDER = re.compile(
    r"sem[\s_-]*imagem|indispon[ií]vel|no[\s_-]*image|not[\s_-]*available"
    r"|imagem[\s_-]*n[ãa]o[\s_-]*dispon|placeholder",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Processada:
    webp: bytes
    fundo_branco: bool  # a ORIGINAL tinha fundo uniforme (packshot)


def termo_placeholder(texto: str) -> bool:
    """Título/URL que denuncia imagem de 'indisponível' antes de baixar."""
    return bool(_PLACEHOLDER.search(texto or ""))


def sha1(dados: bytes) -> str:
    return hashlib.sha1(dados).hexdigest()


def _fundo_uniforme(imagem) -> bool:
    """Os quatro cantos (blocos 4x4, ~5% para dentro) têm a mesma cor?"""
    largura, altura = imagem.size
    inset = max(6, min(largura, altura) // 20)
    bloco = 4
    rgb = imagem.convert("RGB")
    cantos = ((inset, inset), (largura - inset - bloco, inset),
              (inset, altura - inset - bloco), (largura - inset - bloco, altura - inset - bloco))
    amostras = []
    for x, y in cantos:
        x = max(0, min(x, largura - bloco))
        y = max(0, min(y, altura - bloco))
        pixels = [rgb.getpixel((x + dx, y + dy)) for dx in range(bloco) for dy in range(bloco)]
        amostras.append(tuple(sum(canal) // len(pixels) for canal in zip(*pixels)))
    return all(
        max(a[c] for a in amostras) - min(a[c] for a in amostras) <= VARIACAO_MAXIMA_CANTOS for c in range(3)
    )


def processar(dados: bytes) -> tuple[Processada | None, str]:
    if not dados or len(dados) < 500:
        return None, "dados insuficientes (< 500 bytes)"
    from PIL import Image

    try:
        imagem = Image.open(BytesIO(dados))
        imagem.load()
    except Exception as erro:
        return None, f"imagem inválida ({type(erro).__name__})"

    largura, altura = imagem.size
    if min(largura, altura) < LADO_MINIMO:
        return None, f"pequena demais ({largura}x{altura})"
    if max(largura, altura) / min(largura, altura) > PROPORCAO_MAXIMA:
        return None, f"proporção inadequada ({largura}x{altura})"

    if imagem.mode in ("RGBA", "LA") or (imagem.mode == "P" and "transparency" in imagem.info):
        # PNG transparente: convert("RGB") direto deixaria o fundo PRETO
        fundo = Image.new("RGBA", imagem.size, (255, 255, 255, 255))
        fundo.alpha_composite(imagem.convert("RGBA"))
        imagem = fundo

    fundo_branco = _fundo_uniforme(imagem)
    imagem = imagem.convert("RGB")
    imagem.thumbnail((LADO, LADO), Image.LANCZOS)
    tela = Image.new("RGB", (LADO, LADO), (255, 255, 255))
    tela.paste(imagem, ((LADO - imagem.width) // 2, (LADO - imagem.height) // 2))

    for qualidade in (QUALIDADE, 70, 60):
        buffer = BytesIO()
        tela.save(buffer, "WEBP", quality=qualidade, method=6)
        if buffer.tell() <= PESO_ALVO or qualidade == 60:
            return Processada(buffer.getvalue(), fundo_branco), f"webp q{qualidade} {buffer.tell() // 1024}KB"
    return None, "falha na compressão"
```

- [ ] **Step 6: Rodar e ver passar**

Run: `catalogo/.venv-fotos/bin/python -m pytest catalogo/tests/test_fotos_imagem.py -v`
Expected: 7 passed

- [ ] **Step 7: Commit**

```bash
git add .gitignore catalogo/requirements-fotos.txt catalogo/fotos/__init__.py catalogo/fotos/imagem.py catalogo/tests/test_fotos_imagem.py
git commit -m "feat(fotos): venv do pipeline e padronizacao de imagem em WebP 400px

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Dicionários e normalizador

**Files:**
- Create: `catalogo/fotos/dados/__init__.py` (vazio)
- Create: `catalogo/fotos/dados/siglas.py`
- Create: `catalogo/fotos/dados/veiculos.py`
- Create: `catalogo/fotos/dados/marcas.py`
- Create: `catalogo/fotos/dados/tipos_en.py`
- Create: `catalogo/fotos/normalizar.py`
- Test: `catalogo/tests/test_fotos_normalizar.py`

**Interfaces:**
- Produces:
  - `dados.marcas.MARCAS: frozenset[str]` (marca de duas palavras com `_`: `GOLDEN_CROWN`), `MARCAS_COMPOSTAS: tuple[str, ...]`
  - `dados.tipos_en.TIPOS_EN: dict[str, str]`
  - `normalizar.Chave` (frozen dataclass): campos `peca, veiculo, veiculo_alt, lado, marca, tipo_pt, tipo_en: str`, `marca_incerta, e_tipo: bool`; `Chave.para_tipo(tipo_pt: str, tipo_en: str) -> Chave`; propriedades `texto`, `consulta`, `consulta_alt` (todas `str`).
  - `normalizar.normalizar(descricao: str) -> Chave`; `normalizar.tokens(descricao: str) -> list[str]`.

- [ ] **Step 1: Escrever o teste que falha**

`catalogo/tests/test_fotos_normalizar.py`:

```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `catalogo/.venv-fotos/bin/python -m pytest catalogo/tests/test_fotos_normalizar.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'catalogo.fotos.normalizar'`

- [ ] **Step 3: Criar os dicionários**

`catalogo/fotos/dados/__init__.py`: arquivo vazio.

`catalogo/fotos/dados/siglas.py`:

```python
"""Siglas da planilha → palavra por extenso.

Levantadas pela frequência real nas 17.149 descrições ativas (2026-10-05). Só entra
sigla confirmada nos dados. Sigla desconhecida passa como está (em minúsculas).
"""
from __future__ import annotations

# Aplicadas na descrição inteira, antes de quebrar em palavras (a ordem importa).
SIGLAS_COMPOSTAS: tuple[tuple[str, str], ...] = (
    (r"\bCX\.?\s+DIR\b", "CAIXA DIRECAO"),
    (r"\bMTR?\s+PART\b", "MOTOR PARTIDA"),
    (r"\b(?:MT|MTR|MOTOR)\s+VENT\b", "MOTOR VENTOINHA"),
    (r"\bSENSOR\s+TEMP\b", "SENSOR TEMPERATURA"),
    (r"\bAR\s+COND\b", "AR CONDICIONADO"),
    (r"\bREGUL(?:ADOR)?\s+VOLT\b", "REGULADOR VOLTAGEM"),
    (r"\bFREIO\s+MAN\b", "FREIO MANUAL"),
    (r"\bD\.\s?REY\b", "DELREY"),
    (r"\bDEL\s+REY\b", "DELREY"),
    (r"\bGRAND?\s+SIENA\b", "GRANSIENA"),
    (r"\bE-TORQ\b", "ETORQ"),
    (r"\bPICK\s?-?\s?UP\b", "PICKUP"),
)

SIGLAS: dict[str, str] = {
    # posição e lado
    "DT": "dianteiro", "DIANT": "dianteiro", "TRAS": "traseiro", "TS": "traseiro",
    "SUP": "superior", "INF": "inferior", "EXT": "externo", "INT": "interno",
    "CENTR": "central", "LAT": "lateral", "INTERM": "intermediario", "AUX": "auxiliar",
    # suspensão, direção, freio
    "AMORT": "amortecedor", "ESTAB": "estabilizadora", "BAND": "bandeja", "DIR": "direcao",
    "HIDR": "hidraulica", "DH": "direcao hidraulica", "ELETR": "eletrica", "ELET": "eletrica",
    "MESTR": "mestre", "SUSP": "suspensao", "TENS": "tensora", "HOMOC": "homocinetica",
    "TRANSM": "transmissao", "DIFER": "diferencial", "DIF": "diferencial", "CARD": "cardan",
    "AGREG": "agregado", "SINCR": "sincronizador", "ALAV": "alavanca", "ENGAT": "engate",
    "EMBR": "embreagem", "CAMB": "cambio", "VENT": "ventilado",
    # motor, arrefecimento, alimentação
    "MT": "motor", "MTR": "motor", "PART": "partida", "ALT": "alternador", "COMB": "combustivel",
    "RADIAD": "radiador", "RAD": "radiador", "VALV": "valvula", "TERMOST": "termostatica",
    "CABEC": "cabecote", "ADM": "admissao", "ESC": "escape", "ESCAP": "escapamento",
    "SILENC": "silencioso", "INJ": "injetor", "BBA": "bomba", "VIRA": "virabrequim",
    "VIRAB": "virabrequim", "DENTAD": "dentada", "CORR": "correia", "CART": "carter",
    "RESERV": "reservatorio", "AQUEC": "aquecimento", "RESP": "respiro", "LIMITAD": "limitador",
    "DISTR": "distribuidor", "IMPUL": "impulsor", "SEG": "segmento", "STD": "standard",
    "TEMP": "temperatura", "DETON": "detonacao", "ROL": "rolamento", "ROLAMEN": "rolamento",
    "INTERC": "intercooler", "DIES": "diesel", "DSL": "diesel",
    # elétrica, cabine, carroceria
    "IGN": "ignicao", "VOLT": "voltagem", "REG": "regulador", "REGUL": "regulador",
    "ACD": "ar condicionado", "COND": "condicionado", "PARAB": "parabrisa", "LIMP": "limpador",
    "LAV": "lavador", "LANT": "lanterna", "PARACH": "parachoque", "P/CHOQ": "parachoque",
    "RETROV": "retrovisor", "VELOC": "velocimetro", "ACEL": "acelerador", "VIDR": "vidro",
    "PROT": "protecao", "POSIC": "posicao", "BORB": "borboleta", "ESCOV": "escova",
    # genéricas
    "CX": "caixa", "JG": "jogo", "CJ": "conjunto", "VED": "vedacao", "PARAF": "parafuso",
    "MANG": "mangueira", "HAST": "haste", "SUPORT": "suporte", "ABRAC": "abracadeira",
    "UNIV": "universal", "INDL": "industrial", "PTA": "ponta", "PEQ": "pequeno",
    "COMPL": "completo", "ALUM": "aluminio", "PLAST": "plastico", "CROM": "cromado",
    "BORR": "borracha", "ENGR": "engrenagem", "REP": "reparo",
}
```

`catalogo/fotos/dados/veiculos.py`:

```python
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
```

`catalogo/fotos/dados/marcas.py`:

```python
"""Marcas de peças, lubrificantes e pneus que aparecem nas descrições ou nos rótulos.

Uso duplo: (1) a marca citada na descrição precisa estar no título do anúncio;
(2) o OCR lendo OUTRA marca desta lista no rótulo reprova a foto.
Marca de duas palavras é guardada com "_" (o normalizador junta as palavras antes de quebrar).
"""
from __future__ import annotations

MARCAS_COMPOSTAS: tuple[str, ...] = ("GOLDEN CROWN", "MAGNETI MARELLI", "METAL LEVE", "FRAS LE")

MARCAS: frozenset[str] = frozenset("""
BOSCH NGK COFAP MONROE NAKATA TRW FRAS-LE FRASLE FRAS_LE COBREQ SYL VARGA MAHLE METAL_LEVE TECFIL FRAM
WEGA VOX DAYCO GATES CONTINENTAL CONTITECH SKF FAG INA NSK TIMKEN SABO CORTECO VALEO LUK SACHS
MAGNETI_MARELLI MARELLI DELPHI DENSO WAPSA MTE GAUSS SUNFULL VIEMAR FIASA MOTRIO URBA INDISA SCHADEK
VETOR OSRAM PHILIPS NEOLUX MOURA HELIAR BATERAX ZETTA
MOBIL PETRONAS LUBRAX SHELL CASTROL IPIRANGA HAVOLINE ACDELCO MAXON CRACHI MOTUL ELF MOTORCRAFT
MOTORLUB MOLLIX BARDAHL WURTH W-MAX LOCTITE 3M TECBRIL ORBI RADNAQ DULUB UNIGRAX INGRAX LAZZURIL
LAZZUDUR TORCAL
MAZZINI DEWOSTONE OVATION GOLDEN_CROWN XBRI APTANY LANVIGATOR WANLI HIFLY AUSTONE MILEVER DELMAX
ATLANDER PIRELLI GOODYEAR MICHELIN BRIDGESTONE FIRESTONE DUNLOP KUMHO
""".split())
```

`catalogo/fotos/dados/tipos_en.py`:

```python
"""Tipo de peça (como sai do normalizador) → nome em inglês para o CLIP.

O CLIP foi treinado em inglês. A chave é o começo da peça expandida e vale o prefixo
mais longo (3, depois 2, depois 1 palavra). Tipo ambíguo demais ("kit", "reparo",
"bomba", "tampa") fica SEM rótulo de propósito: sem rótulo não há aprovação automática.
"""
from __future__ import annotations

TIPOS_EN: dict[str, str] = {
    # freios
    "pastilha freio": "brake pad", "pastilha": "brake pad", "disco freio": "brake disc rotor",
    "tambor freio": "brake drum", "tambor": "brake drum", "sapata freio": "brake shoe", "sapata": "brake shoe",
    "lona freio": "brake lining", "lona": "brake lining", "cilindro roda": "wheel brake cylinder",
    "cilindro mestre": "brake master cylinder", "cilindro auxiliar": "clutch slave cylinder",
    "cabo freio": "handbrake cable", "mangueira freio": "brake hose", "servo freio": "brake booster",
    "oleo freio": "brake fluid bottle", "mola pastilha": "brake pad spring clip",
    "regulagem freio": "brake shoe adjuster", "pinca freio": "brake caliper", "sensor abs": "abs wheel speed sensor",
    "catraca freio": "brake slack adjuster",
    # suspensão e direção
    "amortecedor tampa": "gas spring lift support", "amortecedor capo": "gas spring lift support",
    "amortecedor": "shock absorber", "batedor amortecedor": "shock absorber bump stop", "batedor": "rubber bump stop",
    "coxim amortecedor": "strut mount", "bucha amortecedor": "shock absorber bushing",
    "bieleta estabilizadora": "stabilizer link", "bieleta": "stabilizer link",
    "borracha estabilizadora": "stabilizer bar bushing", "borracha abracadeira": "stabilizer bar bushing",
    "bucha bandeja": "control arm bushing", "bandeja": "control arm", "pivo": "ball joint",
    "terminal direcao": "tie rod end", "barra axial": "inner tie rod", "barra direcao": "steering tie rod",
    "caixa direcao": "steering rack", "coifa caixa": "steering rack boot", "bomba direcao": "power steering pump",
    "braco pitman": "pitman arm", "braco auxiliar": "idler arm", "mola": "coil spring",
    "bucha feixe": "leaf spring bushing", "bucha jumelo": "leaf spring shackle bushing",
    "cubo roda": "wheel hub", "cubo": "wheel hub", "rolamento roda": "wheel bearing",
    "parafuso roda": "wheel bolt", "porca roda": "wheel lug nut", "asa": "control arm",
    "bucha eixo": "axle bushing", "bucha": "rubber bushing",
    "coxim motor": "engine mount", "coxim cambio": "transmission mount", "coxim": "rubber mount",
    # transmissão e embreagem
    "junta homocinetica": "cv joint", "coifa lado": "cv joint boot", "coifa": "rubber boot",
    "trizeta": "cv joint tripod", "cruzeta": "universal joint cross", "rolamento cardan": "driveshaft center bearing",
    "kit embreagem": "clutch kit", "colar embreagem": "clutch release bearing", "cabo embreagem": "clutch cable",
    "garfo embreagem": "clutch fork", "alavanca cambio": "gear shift lever", "cabo engate": "gear shift cable",
    "anel sincronizador": "synchronizer ring", "oleo diferencial": "gear oil bottle",
    # distribuição e correias
    "correia dentada": "timing belt", "correia lisa": "v belt", "correia": "drive belt",
    "kit correia": "timing belt kit", "tensor correia": "belt tensioner pulley", "tensor": "belt tensioner pulley",
    "rolamento correia": "belt idler pulley", "polia alternador": "alternator pulley", "polia": "pulley",
    "comando valvula": "camshaft",
    # arrefecimento e ar
    "bomba dagua": "water pump", "radiador": "radiator", "reservatorio agua": "coolant expansion tank",
    "reservatorio radiador": "coolant expansion tank", "reservatorio": "plastic fluid reservoir tank",
    "tampa reservatorio": "radiator expansion tank cap", "tampa radiador": "radiator cap",
    "valvula termostatica": "thermostat", "mangote": "radiator hose", "motor ventoinha": "radiator cooling fan motor",
    "aditivo radiador": "coolant bottle", "condensador ar": "ac condenser",
    "filtro cabine": "cabin air filter", "filtro ar": "air filter", "filtro oleo": "oil filter",
    "filtro combustivel": "fuel filter", "filtro": "car filter",
    # motor
    "junta cabecote": "cylinder head gasket", "junta tampa": "valve cover gasket", "jogo junta": "engine gasket set",
    "junta coletor": "exhaust manifold gasket", "junta carter": "oil pan gasket", "junta": "engine gasket",
    "retentor valvula": "valve stem seal", "retentor": "oil seal ring",
    "bronzina biela": "connecting rod bearing", "bronzina mancal": "crankshaft main bearing", "bronzina": "engine bearing",
    "aneis segmento": "piston rings", "aneis": "piston rings", "pistao": "piston",
    "valvula admissao": "engine valve", "valvula escape": "engine valve", "guia valvula": "valve guide",
    "tucho": "hydraulic valve lifter", "bomba oleo": "oil pump", "bujao carter": "oil drain plug",
    "bujao": "oil drain plug", "tampa oleo": "oil filler cap", "vareta oleo": "oil dipstick",
    "protetor carter": "engine skid plate", "oleo motor": "motor oil bottle", "oleo": "motor oil bottle",
    "bico injetor": "fuel injector", "bico": "fuel injector", "bomba combustivel": "fuel pump",
    "flange modulo": "fuel pump module flange", "boia tanque": "fuel level sender float",
    "tampa tanque": "fuel tank cap", "atuador marcha": "idle air control valve",
    "sensor nivel": "fuel level sensor", "sensor temperatura": "temperature sensor",
    "sensor rotacao": "crankshaft position sensor", "sensor map": "map sensor", "sonda lambda": "oxygen sensor",
    "sonda": "oxygen sensor", "sensor posicao": "throttle position sensor", "sensor velocimetro": "speed sensor",
    "sensor fase": "camshaft position sensor", "sensor detonacao": "knock sensor", "sensor": "automotive sensor",
    "silencioso": "exhaust muffler", "abracadeira": "hose clamp", "inforca": "nylon cable ties",
    "mangueira": "rubber hose", "rolamento": "ball bearing", "parafuso": "bolt", "porca": "nut",
    "arruela": "washer",
    # elétrica e ignição
    "velas ignicao": "spark plugs", "velas": "spark plugs", "cabos velas": "spark plug wires",
    "cabos": "spark plug wires", "cabo vela": "spark plug wire", "bobina ignicao": "ignition coil",
    "bobina campo": "starter motor field coil", "bobina": "ignition coil",
    "tampa distribuidor": "distributor cap", "rotor distribuidor": "distributor rotor", "alternador": "alternator",
    "regulador voltagem": "voltage regulator", "porta escova": "alternator brush holder",
    "retificador alternador": "alternator rectifier", "motor partida": "starter motor",
    "impulsor motor": "starter drive bendix", "impulsor": "starter drive bendix",
    "automatico motor": "starter solenoid", "automatico": "starter solenoid",
    "induzido motor": "starter motor armature", "induzido": "starter motor armature", "bateria": "car battery",
    "lampada farol": "headlight bulb", "lampada": "car light bulb", "farol auxiliar": "fog light",
    "farol": "car headlight", "lanterna pisca": "turn signal light", "lanterna placa": "license plate light",
    "lanterna": "car tail light", "lente lanterna": "tail light lens", "lente": "tail light lens",
    "interruptor vidro": "power window switch", "interruptor oleo": "oil pressure switch",
    "interruptor luz": "light switch", "interruptor": "car switch", "chave seta": "turn signal switch stalk",
    "comutador ignicao": "ignition switch", "comutador": "ignition switch", "cilindro ignicao": "ignition lock cylinder",
    "rele": "automotive relay", "fusivel": "automotive fuse", "buzina": "car horn", "chicote": "wiring harness connector",
    "conector": "electrical connector",
    # cabine e carroceria
    "palheta limpador": "wiper blade", "palheta": "wiper blade", "jogo palheta": "wiper blades",
    "bomba lavador": "windshield washer pump", "cabo acelerador": "throttle cable",
    "cabo velocimetro": "speedometer cable", "cabo capo": "hood release cable", "elevador porta": "window regulator",
    "elevador": "window regulator", "macaneta externo": "exterior door handle", "macaneta interno": "interior door handle",
    "macaneta": "door handle", "fechadura porta": "door lock", "fechadura tampa": "trunk lid latch",
    "fechadura": "car door lock", "retrovisor": "car side mirror", "parachoque": "car bumper",
    "grade radiador": "front grille", "grade": "car grille", "parabrisa": "windshield glass",
    "vidro porta": "car door glass", "borracha porta": "door weatherstrip seal", "pestana": "window weatherstrip",
    "calha chuva": "window rain deflector", "calha": "window rain deflector", "calota": "wheel cover hubcap",
    # pneus e consumíveis
    "pneu": "car tire", "camara ar": "tire inner tube", "aditivo": "automotive additive bottle",
    "graxa": "grease can", "tinta": "automotive paint can", "aromatizante": "car air freshener",
    "silicone": "silicone spray can",
}
```

- [ ] **Step 4: Implementar o normalizador**

`catalogo/fotos/normalizar.py`:

```python
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
```

- [ ] **Step 5: Rodar e ver passar**

Run: `catalogo/.venv-fotos/bin/python -m pytest catalogo/tests/test_fotos_normalizar.py -v -s`
Expected: 26 passed. A linha impressa por `test_cobertura_no_catalogo_real` deve mostrar rótulo CLIP ≥ 83% e ≤ 9.000 grupos (medido: 85,7%, 8.539 grupos). Se a cobertura ficar abaixo, acrescentar em `TIPOS_EN` os tipos sem rótulo mais frequentes que não sejam ambíguos e rodar de novo.

- [ ] **Step 6: Commit**

```bash
git add catalogo/fotos/dados catalogo/fotos/normalizar.py catalogo/tests/test_fotos_normalizar.py
git commit -m "feat(fotos): normalizador de descricao abreviada em chave peca+carro+lado+marca

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Sinais de texto e regra de decisão

**Files:**
- Create: `catalogo/fotos/verificar.py`
- Test: `catalogo/tests/test_fotos_verificar.py`

**Interfaces:**
- Consumes: `normalizar.Chave`, `normalizar.normalizar`, `dados.marcas.MARCAS`.
- Produces:
  - `verificar.LIMIAR_RANK_CLIP: int = 3`
  - `verificar.sinais_de_texto(chave: Chave, titulo: str) -> dict[str, bool]` com as chaves `titulo_peca, titulo_veiculo, titulo_spec, titulo_conflito, titulo_marca`
  - `verificar.marca_no_ocr(marca: str, texto_ocr: str) -> bool`; `verificar.outra_marca_no_ocr(marca: str, texto_ocr: str) -> bool`
  - `verificar.Sinais` (frozen dataclass, todos com default): `valida=True, clip_rank: int | None=None, clip_top_lixo=False, titulo_peca=False, titulo_veiculo=False, titulo_spec=False, titulo_conflito=False, titulo_marca=False, ocr_marca=False, ocr_outra_marca=False, dominio_loja=False, fundo_branco=False`
  - `verificar.Decisao(aprovada: bool, plausivel: bool, pontuacao: int, motivos: tuple[str, ...])`
  - `verificar.decidir(chave: Chave, s: Sinais) -> Decisao`

- [ ] **Step 1: Escrever o teste que falha**

`catalogo/tests/test_fotos_verificar.py`:

```python
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
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `catalogo/.venv-fotos/bin/python -m pytest catalogo/tests/test_fotos_verificar.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'catalogo.fotos.verificar'`

- [ ] **Step 3: Implementar**

`catalogo/fotos/verificar.py`:

```python
"""Sinais por candidata e a regra de decisão (funções puras, testáveis sem modelos).

Regra (spec, seção 4.3): aprovação automática só quando TODOS os sinais concordam.
Qualquer dúvida vira revisão; imagem inválida ou lixo (CLIP) nem chega à revisão.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from catalogo.fotos.dados.marcas import MARCAS
from catalogo.fotos.normalizar import Chave

LIMIAR_RANK_CLIP = 3        # tipo esperado precisa estar entre os 3 primeiros do CLIP
LIMIAR_OCR_MARCA = 0.72     # semelhança mínima entre marca esperada e palavra lida no rótulo
_QUALIFICADORES = frozenset({
    "dianteiro", "traseiro", "superior", "inferior", "externo", "interno", "lado", "direito", "esquerdo",
    "com", "sem", "central", "jogo", "kit", "par", "intermediario", "auxiliar", "lateral",
})
# (presente na peça, oposto no título): título com o oposto e sem o próprio = conflito
_OPOSTOS = (("diant", "trase"), ("trase", "diant"), ("direit", "esquerd"), ("esquerd", "direit"),
            ("superior", "inferior"), ("inferior", "superior"))


def _norm(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", sem_acento).strip()


def _radical(palavra: str) -> str:
    """'dianteira'/'dianteiros' → 'dianteir': tolera plural e gênero."""
    for sufixo in ("es", "s"):
        if len(palavra) > 4 and palavra.endswith(sufixo):
            palavra = palavra[: -len(sufixo)]
            break
    if len(palavra) > 4 and palavra[-1] in "ao":
        palavra = palavra[:-1]
    return palavra


def nucleo_da_peca(peca: str) -> list[str]:
    """As duas primeiras palavras que dizem O QUE é a peça (sem posição, lado ou medida)."""
    return [w for w in peca.split()
            if len(w) >= 3 and w not in _QUALIFICADORES and not re.search(r"\d", w)][:2]


def sinais_de_texto(chave: Chave, titulo: str) -> dict[str, bool]:
    t = _norm(titulo)
    radicais = {_radical(p) for p in t.split()}
    compacto = t.replace(" ", "")

    def contem(palavra: str) -> bool:
        p = _norm(palavra).replace(" ", "")
        return bool(p) and (_radical(p) in radicais or (len(p) >= 4 and p in compacto))

    nucleo = nucleo_da_peca(chave.peca)
    titulo_peca = bool(nucleo) and all(contem(p) for p in nucleo)
    titulo_veiculo = (not chave.veiculo or contem(chave.veiculo)
                      or (bool(chave.veiculo_alt) and contem(chave.veiculo_alt)))
    if chave.veiculo:
        titulo_spec = True
    else:
        medidas = [_norm(w).replace(" ", "") for w in chave.peca.split() if re.search(r"\d", w)][:4]
        titulo_spec = all(m in compacto for m in medidas)
    alvo = _norm(f"{chave.peca} {chave.lado}")
    titulo_conflito = any(a in alvo and b in t and a not in t for a, b in _OPOSTOS)
    titulo_marca = not chave.marca or contem(chave.marca)
    return {"titulo_peca": titulo_peca, "titulo_veiculo": titulo_veiculo, "titulo_spec": titulo_spec,
            "titulo_conflito": titulo_conflito, "titulo_marca": titulo_marca}


def _so_alnum(texto: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", texto.upper())


def marca_no_ocr(marca: str, texto_ocr: str) -> bool:
    """Cada palavra da marca aparece no rótulo, aceitando letra trocada pelo OCR."""
    if not marca or not texto_ocr:
        return False
    palavras_ocr = [t for t in re.findall(r"[A-Z0-9]+", texto_ocr.upper()) if len(t) >= 3]
    compacto = _so_alnum(texto_ocr)
    for parte in re.findall(r"[A-Z0-9]+", marca.upper()):
        if parte in compacto:
            continue
        if not any(SequenceMatcher(None, parte, p).ratio() >= LIMIAR_OCR_MARCA for p in palavras_ocr):
            return False
    return True


def outra_marca_no_ocr(marca: str, texto_ocr: str) -> bool:
    """O rótulo mostra, por extenso, outra marca conhecida (ex.: MOTORLUB num produto CRACHI)."""
    if not texto_ocr:
        return False
    palavras = set(re.findall(r"[A-Z0-9-]+", texto_ocr.upper()))
    compacto = _so_alnum(texto_ocr)
    propria = _so_alnum(marca or "")
    for m in MARCAS:
        nome = _so_alnum(m)
        if len(nome) < 4:
            continue  # VOX, ELF, 3M...: curtas demais, o OCR forma por acaso
        if propria and (nome == propria or nome in propria or propria in nome):
            continue
        if m in palavras or ("_" in m and nome in compacto):
            return True
    return False


@dataclass(frozen=True)
class Sinais:
    valida: bool = True
    clip_rank: int | None = None
    clip_top_lixo: bool = False
    titulo_peca: bool = False
    titulo_veiculo: bool = False
    titulo_spec: bool = False
    titulo_conflito: bool = False
    titulo_marca: bool = False
    ocr_marca: bool = False
    ocr_outra_marca: bool = False
    dominio_loja: bool = False
    fundo_branco: bool = False


@dataclass(frozen=True)
class Decisao:
    aprovada: bool
    plausivel: bool
    pontuacao: int
    motivos: tuple[str, ...]


def decidir(chave: Chave, s: Sinais) -> Decisao:
    if not s.valida:
        return Decisao(False, False, 0, ("imagem_invalida",))
    if s.clip_top_lixo:
        return Decisao(False, False, 0, ("clip_lixo",))
    motivos: list[str] = []
    if chave.e_tipo:
        motivos.append("foto_de_tipo_exige_revisao")
    if chave.marca_incerta:
        motivos.append("marca_nao_reconhecida")
    if s.clip_rank is None:
        motivos.append("tipo_sem_rotulo_clip")
    elif s.clip_rank > LIMIAR_RANK_CLIP:
        motivos.append(f"clip_rank_{s.clip_rank}")
    if not s.titulo_peca:
        motivos.append("titulo_sem_peca")
    if not s.titulo_veiculo:
        motivos.append("titulo_sem_veiculo")
    if not s.titulo_spec:
        motivos.append("titulo_sem_medida")
    if s.titulo_conflito:
        motivos.append("titulo_lado_ou_posicao_oposta")
    if chave.marca and not s.titulo_marca:
        motivos.append("titulo_sem_marca")
    if chave.marca and s.ocr_outra_marca:
        motivos.append("ocr_outra_marca")

    pontuacao = (20 * s.titulo_peca + 15 * s.titulo_veiculo + 10 * s.titulo_spec
                 + 15 * (bool(chave.marca) and s.titulo_marca) + 10 * s.ocr_marca
                 + 5 * s.dominio_loja + 5 * s.fundo_branco - 30 * s.titulo_conflito - 30 * s.ocr_outra_marca)
    if s.clip_rank is not None:
        pontuacao += 25 if s.clip_rank == 1 else 15 if s.clip_rank <= LIMIAR_RANK_CLIP else 0
    return Decisao(not motivos, True, int(pontuacao), tuple(motivos))
```

- [ ] **Step 4: Rodar e ver passar**

Run: `catalogo/.venv-fotos/bin/python -m pytest catalogo/tests/test_fotos_verificar.py -v`
Expected: 16 passed

- [ ] **Step 5: Commit**

```bash
git add catalogo/fotos/verificar.py catalogo/tests/test_fotos_verificar.py
git commit -m "feat(fotos): sinais de texto/OCR e regra conjuntiva de aprovacao

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Banco do pipeline (grupos, candidatas, revisão, propagação)

**Files:**
- Create: `catalogo/fotos/banco.py`
- Test: `catalogo/tests/test_fotos_banco.py`

**Interfaces:**
- Consumes: `catalogo.db.conectar/criar_schema/upsert_produto` (já existem; `conectar` define `row_factory = sqlite3.Row`), `normalizar.Chave/normalizar`.
- Produces (todas recebem `conn: sqlite3.Connection`):
  - `agora() -> str` (ISO, segundos)
  - `criar_schema_fotos(conn) -> None` (cria tabelas; adiciona `produtos.foto_grupo` e `produtos.foto_tipo`)
  - `sincronizar_grupos(conn, quando: str) -> int` (nº de grupos novos)
  - `foto_tipo_de(ch: Chave) -> str`
  - `chave_de(row) -> Chave` (`row` precisa de `e_tipo, tipo_pt, tipo_en, descricao_ref`)
  - `garantir_grupo_tipo(conn, ch: Chave, quando: str) -> str | None`
  - `grupos_pendentes(conn, limite: int, chaves: list[str] | None = None) -> list[sqlite3.Row]`
  - `NovaCandidata(arquivo, url, titulo, dominio: str, clip_rank: int | None, clip_top, ocr_texto: str, pontuacao: int, aprovada_auto: bool, motivo: str)`
  - `registrar_candidatas(conn, chave: str, candidatas: list[NovaCandidata]) -> list[int]`
  - `candidatas_de(conn, chave: str) -> list[sqlite3.Row]` (ordem: `pontuacao DESC, id`; é a numeração 0..3 das folhas)
  - `limpar_candidatas(conn, chave: str, dir_candidatas: Path) -> None`
  - `marcar_status(conn, chave: str, status: str, quando: str, *, tentativa: bool = False) -> None`
  - `aprovar(conn, chave: str, candidata_id: int, *, origem: str, quando: str, dir_candidatas: Path, dir_fotos: Path) -> str` (nome do arquivo em `dir_fotos`)
  - `rejeitar_grupo(conn, chave: str, *, origem: str, quando: str) -> None`
  - `propagar(conn, chave: str | None = None) -> None`
  - `registrar_revisao(conn, chave: str, tipo: str, quando: str) -> int` (`tipo` = `"revisao"` ou `"auditoria"`)
  - `decidir_revisao(conn, revisao_id: int, status: str, *, candidata_id: int | None, por: str, quando: str) -> None`
  - `resetar_grupos(conn, chaves: list[str], dir_candidatas: Path) -> int`
  - `backup(db_path: Path | str, dir_backups: Path | str) -> Path`
  - `relatorio(conn) -> dict`

- [ ] **Step 1: Escrever o teste que falha**

`catalogo/tests/test_fotos_banco.py`:

```python
import sqlite3

import pytest

from catalogo.db import conectar, criar_schema, upsert_produto
from catalogo.fotos import banco
from catalogo.fotos.normalizar import normalizar
from catalogo.models import Produto

Q = "2026-10-05T12:00:00"
PRODUTOS = [
    ("1", "PASTILHA FREIO DT AGILE/CELTA"),
    ("2", "PASTILHA FREIO DT AGILE 09/ CELTA"),
    ("3", "PASTILHA FREIO DT UNO 10/"),
    ("4", "OLEO MOTOR 15W40 PETRONAS SYNTIUM 800 SE"),
]


def _carregar(conn):
    for codigo, desc in PRODUTOS:
        upsert_produto(conn, Produto(id=0, codigo=codigo, descricao=desc, categoria="Freios"))
    conn.commit()


@pytest.fixture
def conn():
    c = conectar(":memory:")
    criar_schema(c)
    _carregar(c)
    banco.criar_schema_fotos(c)
    banco.sincronizar_grupos(c, Q)
    yield c
    c.close()


def _grupo(conn, codigo):
    return conn.execute("SELECT foto_grupo FROM produtos WHERE codigo = ?", (codigo,)).fetchone()[0]


def _imagem(conn, codigo):
    return conn.execute("SELECT imagem_url FROM produtos WHERE codigo = ?", (codigo,)).fetchone()[0]


def _candidata(conn, dir_c, chave, conteudo):
    dir_c.mkdir(exist_ok=True)
    nome = f"c{len(list(dir_c.iterdir()))}.webp"
    (dir_c / nome).write_bytes(conteudo)
    [cid] = banco.registrar_candidatas(conn, chave, [banco.NovaCandidata(
        arquivo=nome, url="https://loja/x", titulo="Pastilha Freio", dominio="loja", clip_rank=1,
        clip_top="brake pad", ocr_texto="", pontuacao=50, aprovada_auto=True, motivo="")])
    return cid


def test_schema_idempotente_cria_colunas(conn):
    banco.criar_schema_fotos(conn)
    colunas = {r[1] for r in conn.execute("PRAGMA table_info(produtos)")}
    assert {"foto_grupo", "foto_tipo"} <= colunas


def test_sincronizar_agrupa_mesma_peca_e_carro(conn):
    assert _grupo(conn, "1") == _grupo(conn, "2") == "pastilha freio dianteiro|agile||"
    assert _grupo(conn, "3") != _grupo(conn, "1")
    g = conn.execute("SELECT * FROM foto_grupos WHERE chave = ?", (_grupo(conn, "1"),)).fetchone()
    assert g["n_produtos"] == 2 and g["status"] == "pendente" and g["consulta"] == "pastilha freio dianteiro agile"
    tipos = {r["codigo"]: r["foto_tipo"] for r in conn.execute("SELECT codigo, foto_tipo FROM produtos")}
    assert tipos["1"] == "pastilha freio" and tipos["4"] == ""  # óleo tem marca: nunca usa foto de tipo
    assert banco.sincronizar_grupos(conn, Q) == 0


def test_aprovar_propaga_para_o_grupo_inteiro(conn, tmp_path):
    chave = _grupo(conn, "1")
    cid = _candidata(conn, tmp_path / "cand", chave, b"foto-agile")
    nome = banco.aprovar(conn, chave, cid, origem="auto", quando=Q,
                         dir_candidatas=tmp_path / "cand", dir_fotos=tmp_path / "fotos")
    assert (tmp_path / "fotos" / nome).read_bytes() == b"foto-agile"
    assert _imagem(conn, "1") == _imagem(conn, "2") == f"/fotos/{nome}"
    assert _imagem(conn, "3") == ""


def test_foto_de_tipo_cobre_quem_nao_tem_foto_propria_e_nunca_produto_com_marca(conn, tmp_path):
    tipo = banco.garantir_grupo_tipo(conn, normalizar("PASTILHA FREIO DT UNO 10/"), Q)
    assert tipo == "TIPO:pastilha freio"
    assert banco.garantir_grupo_tipo(conn, normalizar(PRODUTOS[3][1]), Q) is None
    cid = _candidata(conn, tmp_path / "cand", tipo, b"foto-generica")
    generica = banco.aprovar(conn, tipo, cid, origem="agy", quando=Q,
                             dir_candidatas=tmp_path / "cand", dir_fotos=tmp_path / "fotos")
    assert _imagem(conn, "3") == _imagem(conn, "1") == f"/fotos/{generica}"
    assert _imagem(conn, "4") == ""
    chave = _grupo(conn, "1")
    cid = _candidata(conn, tmp_path / "cand", chave, b"foto-agile")
    propria = banco.aprovar(conn, chave, cid, origem="auto", quando=Q,
                            dir_candidatas=tmp_path / "cand", dir_fotos=tmp_path / "fotos")
    assert _imagem(conn, "1") == f"/fotos/{propria}" and _imagem(conn, "3") == f"/fotos/{generica}"


def test_rejeitar_remove_a_foto(conn, tmp_path):
    chave = _grupo(conn, "1")
    cid = _candidata(conn, tmp_path / "cand", chave, b"x")
    banco.aprovar(conn, chave, cid, origem="auto", quando=Q, dir_candidatas=tmp_path / "cand", dir_fotos=tmp_path / "f")
    banco.rejeitar_grupo(conn, chave, origem="auditoria:agy", quando=Q)
    assert _imagem(conn, "1") == ""
    assert conn.execute("SELECT status FROM foto_grupos WHERE chave = ?", (chave,)).fetchone()[0] == "rejeitada"


def test_reimportar_planilha_preserva_foto_aprovada(conn, tmp_path):  # Review Focus 5
    chave = _grupo(conn, "1")
    cid = _candidata(conn, tmp_path / "cand", chave, b"x")
    banco.aprovar(conn, chave, cid, origem="auto", quando=Q, dir_candidatas=tmp_path / "cand", dir_fotos=tmp_path / "f")
    antes = _imagem(conn, "1")
    _carregar(conn)  # reimportação: upsert com imagem_url vazio
    banco.sincronizar_grupos(conn, Q)
    assert _imagem(conn, "1") == antes != ""


def test_candidata_de_outro_grupo_nao_aprova(conn, tmp_path):
    cid = _candidata(conn, tmp_path / "cand", _grupo(conn, "1"), b"x")
    with pytest.raises(ValueError):
        banco.aprovar(conn, _grupo(conn, "3"), cid, origem="agy", quando=Q,
                      dir_candidatas=tmp_path / "cand", dir_fotos=tmp_path / "f")


def test_revisao_nova_torna_a_antiga_obsoleta_e_decisao_registra(conn):
    chave = _grupo(conn, "1")
    r1 = banco.registrar_revisao(conn, chave, "revisao", Q)
    r2 = banco.registrar_revisao(conn, chave, "revisao", Q)
    status = {r["id"]: r["status"] for r in conn.execute("SELECT id, status FROM foto_revisao")}
    assert status == {r1: "obsoleta", r2: "pendente"}
    banco.decidir_revisao(conn, r2, "rejeitada", candidata_id=None, por="agy", quando=Q)
    r = conn.execute("SELECT * FROM foto_revisao WHERE id = ?", (r2,)).fetchone()
    assert (r["status"], r["decidido_por"], r["decidido_em"]) == ("rejeitada", "agy", Q)


def test_resetar_volta_para_pendente_e_limpa(conn, tmp_path):
    chave = _grupo(conn, "1")
    cid = _candidata(conn, tmp_path / "cand", chave, b"x")
    banco.aprovar(conn, chave, cid, origem="auto", quando=Q, dir_candidatas=tmp_path / "cand", dir_fotos=tmp_path / "f")
    banco.registrar_revisao(conn, chave, "auditoria", Q)
    assert banco.resetar_grupos(conn, [chave], tmp_path / "cand") == 1
    g = conn.execute("SELECT * FROM foto_grupos WHERE chave = ?", (chave,)).fetchone()
    assert (g["status"], g["arquivo"]) == ("pendente", "") and _imagem(conn, "1") == ""
    assert conn.execute("SELECT count(*) FROM foto_revisao WHERE status = 'pendente'").fetchone()[0] == 0
    assert list((tmp_path / "cand").iterdir()) == []


def test_grupos_pendentes_ordem_e_filtro(conn):
    fila = banco.grupos_pendentes(conn, 10)
    assert fila[0]["chave"] == _grupo(conn, "1")  # 2 produtos: vem primeiro
    assert [r["chave"] for r in banco.grupos_pendentes(conn, 10, [_grupo(conn, "3")])] == [_grupo(conn, "3")]
    assert banco.grupos_pendentes(conn, 10, []) == []


def test_backup_gera_copia_legivel(tmp_path):
    db = tmp_path / "c.db"
    c = conectar(str(db))
    criar_schema(c)
    _carregar(c)
    c.close()
    copia = banco.backup(db, tmp_path / "bk")
    assert sqlite3.connect(copia).execute("SELECT count(*) FROM produtos").fetchone()[0] == 4


def test_relatorio(conn):
    r = banco.relatorio(conn)
    assert r["grupos"] == {"pendente": 3} and r["produtos_ativos"] == 4 and r["produtos_com_foto"] == 0
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `catalogo/.venv-fotos/bin/python -m pytest catalogo/tests/test_fotos_banco.py -v`
Expected: FAIL, `ImportError: cannot import name 'banco'`

- [ ] **Step 3: Implementar**

`catalogo/fotos/banco.py`:

```python
"""Tabelas do pipeline de fotos e as operações sobre elas.

Toda aprovação/rejeição termina em `propagar`, que recalcula `produtos.imagem_url`:
foto do próprio grupo aprovada > foto do tipo (só produto sem marca) > nenhuma.
"""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from catalogo.fotos.normalizar import Chave, normalizar

_SCHEMA = """
CREATE TABLE IF NOT EXISTS foto_grupos (
    chave TEXT PRIMARY KEY,
    descricao_ref TEXT NOT NULL DEFAULT '',
    e_tipo INTEGER NOT NULL DEFAULT 0,
    tipo_pt TEXT NOT NULL DEFAULT '',
    consulta TEXT NOT NULL,
    consulta_alt TEXT NOT NULL DEFAULT '',
    tipo_en TEXT NOT NULL DEFAULT '',
    marca TEXT NOT NULL DEFAULT '',
    lado TEXT NOT NULL DEFAULT '',
    n_produtos INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pendente',   -- pendente|aprovada|revisao|sem_foto|rejeitada
    origem TEXT NOT NULL DEFAULT '',           -- auto|agy|auditoria:agy
    arquivo TEXT NOT NULL DEFAULT '',          -- <sha1>.webp em data/fotos/
    url_origem TEXT NOT NULL DEFAULT '',
    titulo_origem TEXT NOT NULL DEFAULT '',
    tentativas INTEGER NOT NULL DEFAULT 0,
    atualizado_em TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_foto_grupos_fila ON foto_grupos(status, e_tipo, n_produtos);

CREATE TABLE IF NOT EXISTS foto_candidatas (
    id INTEGER PRIMARY KEY,
    chave TEXT NOT NULL REFERENCES foto_grupos(chave),
    arquivo TEXT NOT NULL,
    url TEXT NOT NULL,
    titulo TEXT NOT NULL,
    dominio TEXT NOT NULL,
    clip_rank INTEGER,
    clip_top TEXT NOT NULL DEFAULT '',
    ocr_texto TEXT NOT NULL DEFAULT '',
    pontuacao INTEGER NOT NULL,
    aprovada_auto INTEGER NOT NULL,
    motivo TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_foto_candidatas_chave ON foto_candidatas(chave);

CREATE TABLE IF NOT EXISTS foto_revisao (
    id INTEGER PRIMARY KEY,
    chave TEXT NOT NULL REFERENCES foto_grupos(chave),
    tipo TEXT NOT NULL,                         -- revisao|auditoria
    status TEXT NOT NULL DEFAULT 'pendente',    -- pendente|aprovada|rejeitada|obsoleta
    candidata_escolhida INTEGER,
    decidido_por TEXT,
    criado_em TEXT NOT NULL,
    decidido_em TEXT
);
CREATE INDEX IF NOT EXISTS idx_foto_revisao_status ON foto_revisao(status, tipo);
"""

_PROPAGAR = """
UPDATE produtos SET imagem_url = COALESCE(
    (SELECT '/fotos/' || g.arquivo FROM foto_grupos g
      WHERE g.chave = produtos.foto_grupo AND g.status = 'aprovada' AND g.arquivo != ''),
    (SELECT '/fotos/' || t.arquivo FROM foto_grupos t
      WHERE produtos.foto_tipo != '' AND t.chave = 'TIPO:' || produtos.foto_tipo
        AND t.status = 'aprovada' AND t.arquivo != ''),
    '')
WHERE foto_grupo != '' {filtro}
"""


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def criar_schema_fotos(conn: sqlite3.Connection) -> None:
    conn.executescript(_SCHEMA)
    colunas = {r[1] for r in conn.execute("PRAGMA table_info(produtos)")}
    for coluna in ("foto_grupo", "foto_tipo"):
        if coluna not in colunas:
            conn.execute(f"ALTER TABLE produtos ADD COLUMN {coluna} TEXT NOT NULL DEFAULT ''")
    conn.commit()


def _inserir_grupo(conn: sqlite3.Connection, ch: Chave, descricao_ref: str, quando: str) -> bool:
    cur = conn.execute(
        "INSERT OR IGNORE INTO foto_grupos (chave, descricao_ref, e_tipo, tipo_pt, consulta, consulta_alt,"
        " tipo_en, marca, lado, atualizado_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (ch.texto, descricao_ref, int(ch.e_tipo), ch.tipo_pt, ch.consulta, ch.consulta_alt,
         ch.tipo_en, ch.marca, ch.lado, quando),
    )
    return cur.rowcount == 1


def foto_tipo_de(ch: Chave) -> str:
    """Tipo cuja foto genérica pode cobrir este produto ('' se tiver marca ou marca incerta)."""
    return ch.tipo_pt if ch.tipo_pt and not ch.marca and not ch.marca_incerta and not ch.e_tipo else ""


def sincronizar_grupos(conn: sqlite3.Connection, quando: str) -> int:
    """Calcula o grupo de cada produto ativo e cria os grupos que faltam. Idempotente."""
    novos = 0
    vistos: set[str] = set()
    atualizacoes = []
    for r in conn.execute("SELECT id, descricao FROM produtos WHERE ativo = 1").fetchall():
        ch = normalizar(r["descricao"])
        if not ch.peca:
            continue
        atualizacoes.append((ch.texto, foto_tipo_de(ch), r["id"]))
        if ch.texto not in vistos:
            vistos.add(ch.texto)
            novos += _inserir_grupo(conn, ch, r["descricao"], quando)
    conn.executemany(
        "UPDATE produtos SET foto_grupo = ?, foto_tipo = ? WHERE id = ? AND (foto_grupo != ? OR foto_tipo != ?)",
        [(g, t, i, g, t) for g, t, i in atualizacoes],
    )
    conn.execute("UPDATE foto_grupos SET n_produtos = (SELECT count(*) FROM produtos p"
                 " WHERE p.ativo = 1 AND p.foto_grupo = foto_grupos.chave) WHERE e_tipo = 0")
    conn.execute("UPDATE foto_grupos SET n_produtos = (SELECT count(*) FROM produtos p"
                 " WHERE p.ativo = 1 AND 'TIPO:' || p.foto_tipo = foto_grupos.chave) WHERE e_tipo = 1")
    conn.commit()
    return novos


def chave_de(row) -> Chave:
    if row["e_tipo"]:
        return Chave.para_tipo(row["tipo_pt"], row["tipo_en"])
    return normalizar(row["descricao_ref"])


def garantir_grupo_tipo(conn: sqlite3.Connection, ch: Chave, quando: str) -> str | None:
    tipo = foto_tipo_de(ch)
    if not tipo:
        return None
    t = Chave.para_tipo(tipo, ch.tipo_en)
    _inserir_grupo(conn, t, "", quando)
    conn.execute("UPDATE foto_grupos SET n_produtos = (SELECT count(*) FROM produtos p"
                 " WHERE p.ativo = 1 AND p.foto_tipo = ?) WHERE chave = ?", (tipo, t.texto))
    conn.commit()
    return t.texto


def grupos_pendentes(conn: sqlite3.Connection, limite: int, chaves: list[str] | None = None) -> list[sqlite3.Row]:
    ordem = "ORDER BY e_tipo, n_produtos DESC, chave LIMIT ?"
    if chaves is None:
        return conn.execute(f"SELECT * FROM foto_grupos WHERE status = 'pendente' {ordem}", (limite,)).fetchall()
    if not chaves:
        return []
    marcadores = ",".join("?" * len(chaves))
    return conn.execute(
        f"SELECT * FROM foto_grupos WHERE status = 'pendente' AND chave IN ({marcadores}) {ordem}",
        [*chaves, limite],
    ).fetchall()


@dataclass(frozen=True)
class NovaCandidata:
    arquivo: str
    url: str
    titulo: str
    dominio: str
    clip_rank: int | None
    clip_top: str
    ocr_texto: str
    pontuacao: int
    aprovada_auto: bool
    motivo: str


def registrar_candidatas(conn: sqlite3.Connection, chave: str, candidatas: list[NovaCandidata]) -> list[int]:
    ids = []
    for c in candidatas:
        cur = conn.execute(
            "INSERT INTO foto_candidatas (chave, arquivo, url, titulo, dominio, clip_rank, clip_top, ocr_texto,"
            " pontuacao, aprovada_auto, motivo) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (chave, c.arquivo, c.url, c.titulo, c.dominio, c.clip_rank, c.clip_top, c.ocr_texto,
             c.pontuacao, int(c.aprovada_auto), c.motivo),
        )
        ids.append(cur.lastrowid)
    conn.commit()
    return ids


def candidatas_de(conn: sqlite3.Connection, chave: str) -> list[sqlite3.Row]:
    """Ordem fixa (pontuação, id): é a numeração 0..3 mostrada nas folhas de revisão."""
    return conn.execute("SELECT * FROM foto_candidatas WHERE chave = ? ORDER BY pontuacao DESC, id",
                        (chave,)).fetchall()


def limpar_candidatas(conn: sqlite3.Connection, chave: str, dir_candidatas: Path) -> None:
    for r in conn.execute("SELECT arquivo FROM foto_candidatas WHERE chave = ?", (chave,)).fetchall():
        (Path(dir_candidatas) / r["arquivo"]).unlink(missing_ok=True)
    conn.execute("DELETE FROM foto_candidatas WHERE chave = ?", (chave,))
    conn.commit()


def marcar_status(conn: sqlite3.Connection, chave: str, status: str, quando: str, *, tentativa: bool = False) -> None:
    conn.execute("UPDATE foto_grupos SET status = ?, atualizado_em = ?, tentativas = tentativas + ? WHERE chave = ?",
                 (status, quando, int(tentativa), chave))
    conn.commit()


def propagar(conn: sqlite3.Connection, chave: str | None = None) -> None:
    if chave is None:
        conn.execute(_PROPAGAR.format(filtro=""))
    elif chave.startswith("TIPO:"):
        conn.execute(_PROPAGAR.format(filtro="AND foto_tipo = ?"), (chave[len("TIPO:"):],))
    else:
        conn.execute(_PROPAGAR.format(filtro="AND foto_grupo = ?"), (chave,))
    conn.commit()


def aprovar(conn: sqlite3.Connection, chave: str, candidata_id: int, *, origem: str, quando: str,
            dir_candidatas: Path, dir_fotos: Path) -> str:
    c = conn.execute("SELECT * FROM foto_candidatas WHERE id = ? AND chave = ?", (candidata_id, chave)).fetchone()
    if c is None:
        raise ValueError(f"candidata {candidata_id} não pertence ao grupo {chave!r}")
    dados = (Path(dir_candidatas) / c["arquivo"]).read_bytes()
    nome = hashlib.sha1(dados).hexdigest() + ".webp"
    Path(dir_fotos).mkdir(parents=True, exist_ok=True)
    (Path(dir_fotos) / nome).write_bytes(dados)
    conn.execute("UPDATE foto_grupos SET status = 'aprovada', origem = ?, arquivo = ?, url_origem = ?,"
                 " titulo_origem = ?, atualizado_em = ? WHERE chave = ?",
                 (origem, nome, c["url"], c["titulo"], quando, chave))
    propagar(conn, chave)
    return nome


def rejeitar_grupo(conn: sqlite3.Connection, chave: str, *, origem: str, quando: str) -> None:
    conn.execute("UPDATE foto_grupos SET status = 'rejeitada', origem = ?, arquivo = '', atualizado_em = ?"
                 " WHERE chave = ?", (origem, quando, chave))
    propagar(conn, chave)


def registrar_revisao(conn: sqlite3.Connection, chave: str, tipo: str, quando: str) -> int:
    conn.execute("UPDATE foto_revisao SET status = 'obsoleta' WHERE chave = ? AND tipo = ? AND status = 'pendente'",
                 (chave, tipo))
    cur = conn.execute("INSERT INTO foto_revisao (chave, tipo, criado_em) VALUES (?, ?, ?)", (chave, tipo, quando))
    conn.commit()
    return cur.lastrowid


def decidir_revisao(conn: sqlite3.Connection, revisao_id: int, status: str, *, candidata_id: int | None,
                    por: str, quando: str) -> None:
    conn.execute("UPDATE foto_revisao SET status = ?, candidata_escolhida = ?, decidido_por = ?, decidido_em = ?"
                 " WHERE id = ?", (status, candidata_id, por, quando, revisao_id))
    conn.commit()


def resetar_grupos(conn: sqlite3.Connection, chaves: list[str], dir_candidatas: Path) -> int:
    if not chaves:
        return 0
    for chave in chaves:
        limpar_candidatas(conn, chave, dir_candidatas)
    marcadores = ",".join("?" * len(chaves))
    cur = conn.execute(f"UPDATE foto_grupos SET status = 'pendente', origem = '', arquivo = '', url_origem = '',"
                       f" titulo_origem = '', tentativas = 0 WHERE chave IN ({marcadores})", chaves)
    n = cur.rowcount
    conn.execute(f"UPDATE foto_revisao SET status = 'obsoleta' WHERE status = 'pendente'"
                 f" AND chave IN ({marcadores})", chaves)
    propagar(conn)
    return n


def backup(db_path: Path | str, dir_backups: Path | str) -> Path:
    Path(dir_backups).mkdir(parents=True, exist_ok=True)
    destino = Path(dir_backups) / f"catalogo_{datetime.now():%Y%m%d_%H%M%S_%f}.db"
    origem = sqlite3.connect(str(db_path))
    copia = sqlite3.connect(str(destino))
    try:
        origem.backup(copia)
    finally:
        copia.close()
        origem.close()
    return destino


def relatorio(conn: sqlite3.Connection) -> dict:
    def contar(sql: str) -> dict[str, int]:
        return {r[0]: r[1] for r in conn.execute(sql)}

    return {
        "grupos": contar("SELECT status, count(*) FROM foto_grupos WHERE e_tipo = 0 GROUP BY status"),
        "grupos_tipo": contar("SELECT status, count(*) FROM foto_grupos WHERE e_tipo = 1 GROUP BY status"),
        "aprovadas_por": contar("SELECT origem, count(*) FROM foto_grupos WHERE status = 'aprovada' GROUP BY origem"),
        "fila_pendente": contar("SELECT tipo, count(*) FROM foto_revisao WHERE status = 'pendente' GROUP BY tipo"),
        "produtos_com_foto": conn.execute(
            "SELECT count(*) FROM produtos WHERE ativo = 1 AND imagem_url != ''").fetchone()[0],
        "produtos_ativos": conn.execute("SELECT count(*) FROM produtos WHERE ativo = 1").fetchone()[0],
    }
```

- [ ] **Step 4: Rodar e ver passar**

Run: `catalogo/.venv-fotos/bin/python -m pytest catalogo/tests/test_fotos_banco.py -v`
Expected: 12 passed

- [ ] **Step 5: Rodar a suíte inteira (o ALTER TABLE não pode quebrar o site)**

Run: `catalogo/.venv-fotos/bin/python -m pytest catalogo/tests -q`
Expected: tudo passa (29 testes antigos + novos)

- [ ] **Step 6: Commit**

```bash
git add catalogo/fotos/banco.py catalogo/tests/test_fotos_banco.py
git commit -m "feat(fotos): tabelas de grupos/candidatas/revisao e propagacao para produtos

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Busca de imagens e download

**Files:**
- Create: `catalogo/fotos/busca.py`
- Test: `catalogo/tests/test_fotos_busca.py`

**Interfaces:**
- Produces: `busca.BuscaBloqueada(Exception)`; `busca.Resultado(url_imagem: str, url_pagina: str, titulo: str)` (frozen); `busca.buscar_imagens(consulta: str, *, max_resultados: int = 12, cliente=None) -> list[Resultado]`; `busca.dominio(url: str) -> str`; `busca.bloqueado(r: Resultado) -> bool`; `busca.eh_loja(r: Resultado) -> bool`; `busca.baixar(url: str, *, timeout: float = 12.0, cliente=None) -> bytes | None`.

- [ ] **Step 1: Escrever o teste que falha**

`catalogo/tests/test_fotos_busca.py`:

```python
import pytest

pytest.importorskip("ddgs")
import httpx  # noqa: E402
from ddgs.exceptions import DDGSException, RatelimitException  # noqa: E402

from catalogo.fotos import busca  # noqa: E402


class Cliente:
    def __init__(self, resposta=None, erro=None):
        self.resposta, self.erro, self.chamadas = resposta or [], erro, []

    def images(self, consulta, **kwargs):
        self.chamadas.append((consulta, kwargs))
        if self.erro:
            raise self.erro
        return self.resposta


def test_converte_resultados_e_busca_no_brasil():
    c = Cliente([
        {"title": "Pastilha Freio Agile", "image": "https://http2.mlstatic.com/a.jpg",
         "url": "https://produto.mercadolivre.com.br/MLB-1"},
        {"title": "sem url de imagem", "image": "", "url": "https://x"},
    ])
    assert busca.buscar_imagens("pastilha freio agile", cliente=c) == [busca.Resultado(
        "https://http2.mlstatic.com/a.jpg", "https://produto.mercadolivre.com.br/MLB-1", "Pastilha Freio Agile")]
    consulta, kwargs = c.chamadas[0]
    assert consulta == "pastilha freio agile" and kwargs["region"] == "br-pt" and kwargs["max_results"] == 12


def test_sem_resultado_vira_lista_vazia_e_bloqueio_vira_excecao():
    assert busca.buscar_imagens("x", cliente=Cliente(erro=DDGSException("No results found."))) == []
    with pytest.raises(busca.BuscaBloqueada):
        busca.buscar_imagens("x", cliente=Cliente(erro=RatelimitException("202 Ratelimit")))


def test_dominios_de_loja_e_bloqueados():
    ml = busca.Resultado("https://http2.mlstatic.com/D_1.jpg", "https://produto.mercadolivre.com.br/x", "t")
    pin = busca.Resultado("https://i.pinimg.com/a.jpg", "https://br.pinterest.com/pin/1", "t")
    assert busca.eh_loja(ml) and not busca.bloqueado(ml)
    assert busca.bloqueado(pin) and not busca.eh_loja(pin)
    assert busca.dominio("https://Http2.MLSTATIC.com/x") == "http2.mlstatic.com"


def test_baixar_aceita_so_imagem_de_tamanho_razoavel():
    def responder(req):
        caminho = req.url.path
        if caminho == "/foto.jpg":
            return httpx.Response(200, content=b"\xff" * 5000, headers={"content-type": "image/jpeg"})
        if caminho == "/pagina":
            return httpx.Response(200, content=b"<html>" * 1000, headers={"content-type": "text/html"})
        if caminho == "/pequena.jpg":
            return httpx.Response(200, content=b"\xff" * 100, headers={"content-type": "image/jpeg"})
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(responder)) as cliente:
        assert busca.baixar("https://x/foto.jpg", cliente=cliente) == b"\xff" * 5000
        for url in ("https://x/pagina", "https://x/pequena.jpg", "https://x/nada.jpg"):
            assert busca.baixar(url, cliente=cliente) is None
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `catalogo/.venv-fotos/bin/python -m pytest catalogo/tests/test_fotos_busca.py -v`
Expected: FAIL, `ImportError: cannot import name 'busca'`

- [ ] **Step 3: Implementar**

`catalogo/fotos/busca.py`:

```python
"""Busca de imagens no DuckDuckGo (ddgs) e download das candidatas.

O domínio NÃO decide se a foto serve (lição do Agrocarreiro: CDN ≠ site, e filtro
eliminatório por fonte jogava fora foto certa). Só bloqueamos fontes que nunca são foto
de produto; 'loja' é apenas um pequeno bônus na pontuação.
"""
from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

DOMINIOS_BLOQUEADOS = (
    "pinterest.", "pinimg.com", "facebook.", "fbsbx.com", "instagram.", "youtube.", "ytimg.com", "tiktok.",
    "blogspot.", "wordpress.", "shutterstock.", "istockphoto.", "alamy.", "dreamstime.", "freepik.",
    "123rf.", "gettyimages.", "vecteezy.", "pngtree.", "pngwing.", "wallpaper", "clipart",
)
DOMINIOS_LOJA = (
    "mlstatic.com", "mercadolivre.com.br", "mercadolibre.", "magazineluiza.", "mlcdn.com.br", "amazon.com.br",
    "media-amazon.com", "shopee.", "americanas.", "casasbahia.", "canaldapeca.", "hipervarejo.", "autozone.",
    "dpaschoal.", "pecaagora.", "connectparts.", "jocar.", "rodaparts.",
)
_CABECALHOS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                             "Chrome/126.0 Safari/537.36"}


class BuscaBloqueada(Exception):
    """DuckDuckGo recusou/limitou a busca. O grupo deve continuar pendente."""


@dataclass(frozen=True)
class Resultado:
    url_imagem: str
    url_pagina: str
    titulo: str


def buscar_imagens(consulta: str, *, max_resultados: int = 12, cliente=None) -> list[Resultado]:
    from ddgs.exceptions import DDGSException, RatelimitException, TimeoutException

    if cliente is None:
        from ddgs import DDGS

        cliente = DDGS()
    try:
        brutos = cliente.images(consulta, region="br-pt", safesearch="moderate", max_results=max_resultados)
    except (RatelimitException, TimeoutException) as erro:
        raise BuscaBloqueada(str(erro)) from erro
    except DDGSException as erro:
        if "no results" in str(erro).lower():
            return []
        raise BuscaBloqueada(str(erro)) from erro
    return [Resultado(b.get("image", ""), b.get("url", ""), b.get("title", "")) for b in brutos if b.get("image")]


def dominio(url: str) -> str:
    return urlparse(url or "").netloc.lower()


def _dominios(r: Resultado) -> str:
    return f"{dominio(r.url_imagem)} {dominio(r.url_pagina)}"


def bloqueado(r: Resultado) -> bool:
    return any(b in _dominios(r) for b in DOMINIOS_BLOQUEADOS)


def eh_loja(r: Resultado) -> bool:
    return any(d in _dominios(r) for d in DOMINIOS_LOJA)


def baixar(url: str, *, timeout: float = 12.0, cliente=None) -> bytes | None:
    import httpx

    try:
        if cliente is None:
            with httpx.Client(headers=_CABECALHOS, follow_redirects=True, timeout=timeout) as c:
                resposta = c.get(url)
        else:
            resposta = cliente.get(url)
    except httpx.HTTPError:
        return None
    tipo = resposta.headers.get("content-type", "").lower()
    if resposta.status_code != 200 or "html" in tipo or "text" in tipo:
        return None
    if not 3_000 <= len(resposta.content) <= 12_000_000:
        return None
    return resposta.content
```

- [ ] **Step 4: Rodar e ver passar**

Run: `catalogo/.venv-fotos/bin/python -m pytest catalogo/tests/test_fotos_busca.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add catalogo/fotos/busca.py catalogo/tests/test_fotos_busca.py
git commit -m "feat(fotos): busca DuckDuckGo Imagens e download das candidatas

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Modelos locais (CLIP zero-shot e OCR)

**Files:**
- Create: `catalogo/fotos/modelos.py`
- Test: `catalogo/tests/test_fotos_modelos.py`

**Interfaces:**
- Produces: `modelos.CACHE_MODELOS: Path = Path("/mnt/dados/cache")`; `modelos.LIXO: dict[str, str]` (rótulos `"LIXO:..."` → prompt); `modelos.Visao(rotulos: list[str], cache_dir: Path = CACHE_MODELOS)` com `.nomes: list[str]` e `.ranking(dados: bytes, tipo_en: str) -> tuple[int | None, bool, str]` = (posição do tipo esperado começando em 1, ou `None` se o tipo não está entre os rótulos; se o 1º lugar é lixo; nome do 1º lugar); `modelos.Ocr(cache_dir: Path = CACHE_MODELOS)` com `.ler(dados: bytes) -> str` (texto em MAIÚSCULAS).

- [ ] **Step 1: Escrever o teste que falha**

`catalogo/tests/test_fotos_modelos.py`:

```python
import io

import pytest

pytest.importorskip("torch")
pytest.importorskip("open_clip")
pytest.importorskip("easyocr")
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from catalogo.fotos import modelos  # noqa: E402

pytestmark = pytest.mark.skipif(not (modelos.CACHE_MODELOS / "open_clip").exists(),
                                reason="pesos do CLIP não estão em /mnt/dados/cache")


def _png(im) -> bytes:
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


@pytest.fixture(scope="module")
def visao():
    return modelos.Visao(["car tire", "brake pad", "spark plug"])


def test_ranking_devolve_posicao_lixo_e_primeiro_lugar(visao):
    pneu = Image.new("RGB", (300, 300), "white")
    d = ImageDraw.Draw(pneu)
    d.ellipse((30, 30, 270, 270), fill="black")
    d.ellipse((110, 110, 190, 190), fill="gray")
    rank, lixo, topo = visao.ranking(_png(pneu), "car tire")
    assert isinstance(rank, int) and 1 <= rank <= len(visao.nomes)
    assert isinstance(lixo, bool) and topo in visao.nomes
    assert visao.ranking(_png(pneu), "rotulo que nao existe")[0] is None
    assert len(visao.nomes) == 3 + len(modelos.LIXO)


def test_ocr_le_marca_impressa():
    im = Image.new("RGB", (600, 200), "white")
    fonte = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 90)
    ImageDraw.Draw(im).text((20, 40), "BOSCH", fill="black", font=fonte)
    assert "BOSCH" in modelos.Ocr().ler(_png(im))
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `catalogo/.venv-fotos/bin/python -m pytest catalogo/tests/test_fotos_modelos.py -v`
Expected: FAIL, `ImportError: cannot import name 'modelos'`

- [ ] **Step 3: Implementar**

`catalogo/fotos/modelos.py`:

```python
"""Modelos locais de visão: CLIP zero-shot (qual tipo de peça? é lixo?) e OCR (marca no rótulo).

Medido no spike de 2026-10-05: o CLIP separou 10/10 imagens ruins (placeholder, desenho,
peça errada) e pôs o tipo certo no top 3 em 79% das fotos boas. Pesado: importe só quando for usar.
"""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

# O disco principal tem pouco espaço; os pesos já estão aqui (compartilhados com o Agrocarreiro).
CACHE_MODELOS = Path("/mnt/dados/cache")
LIXO: dict[str, str] = {
    "LIXO:carro": "a photo of a car",
    "LIXO:desenho": "a technical drawing with dimensions",
    "LIXO:placeholder": "a gray placeholder icon meaning image not available",
    "LIXO:caixa": "a cardboard product box",
    "LIXO:banner": "an advertisement banner with text",
}


class Visao:
    def __init__(self, rotulos: list[str], cache_dir: Path = CACHE_MODELOS):
        import open_clip
        import torch

        self._torch = torch
        self.modelo, _, self.preparo = open_clip.create_model_and_transforms(
            "ViT-B-32-quickgelu", pretrained="openai", cache_dir=str(cache_dir / "open_clip"))
        self.modelo.eval()
        tokenizador = open_clip.get_tokenizer("ViT-B-32-quickgelu")
        self.nomes = list(rotulos) + list(LIXO)
        prompts = [f"a product photo of a {r}" for r in rotulos] + list(LIXO.values())
        with torch.no_grad():
            textos = self.modelo.encode_text(tokenizador(prompts))
            self.textos = textos / textos.norm(dim=-1, keepdim=True)

    def ranking(self, dados: bytes, tipo_en: str) -> tuple[int | None, bool, str]:
        from PIL import Image

        imagem = Image.open(BytesIO(dados)).convert("RGB")
        with self._torch.no_grad():
            f = self.modelo.encode_image(self.preparo(imagem).unsqueeze(0))
            f = f / f.norm(dim=-1, keepdim=True)
            probabilidades = (100 * f @ self.textos.T).softmax(-1)[0]
        ordem = [self.nomes[i] for i in probabilidades.argsort(descending=True).tolist()]
        rank = ordem.index(tipo_en) + 1 if tipo_en and tipo_en in self.nomes else None
        return rank, ordem[0].startswith("LIXO:"), ordem[0]


class Ocr:
    def __init__(self, cache_dir: Path = CACHE_MODELOS):
        import easyocr

        # quantize=False: a CPU desta máquina só tem AVX; o caminho quantizado morre com SIGILL.
        self.leitor = easyocr.Reader(["pt", "en"], gpu=False, verbose=False, quantize=False,
                                     model_storage_directory=str(cache_dir / "easyocr"))

    def ler(self, dados: bytes) -> str:
        import numpy as np
        from PIL import Image

        imagem = Image.open(BytesIO(dados)).convert("RGB")
        imagem.thumbnail((1200, 1200))
        return " ".join(self.leitor.readtext(np.array(imagem), detail=0)).upper()
```

- [ ] **Step 4: Rodar e ver passar**

Run: `catalogo/.venv-fotos/bin/python -m pytest catalogo/tests/test_fotos_modelos.py -v`
Expected: 2 passed (a primeira execução leva alguns segundos para carregar os pesos)

- [ ] **Step 5: Commit**

```bash
git add catalogo/fotos/modelos.py catalogo/tests/test_fotos_modelos.py
git commit -m "feat(fotos): CLIP zero-shot por tipo de peca e OCR de marca

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Configuração e orquestrador (`executar.py`)

**Files:**
- Modify: `catalogo/config.py`
- Create: `catalogo/fotos/executar.py`
- Test: `catalogo/tests/test_fotos_executar.py`

**Interfaces:**
- Consumes: tudo das Tasks 1–6.
- Produces:
  - `Settings.fotos_dir`, `Settings.candidatas_dir`, `Settings.backups_dir`, `Settings.revisao_dir` (`str`; env `FOTOS_DIR`, `CANDIDATAS_DIR`, `BACKUPS_DIR`, `REVISAO_DIR`)
  - `executar.Contexto` (dataclass): `conn, buscador: Callable[[str], list[Resultado]], baixador: Callable[[str], bytes | None], visao (tem .ranking), ocr (tem .ler), dir_candidatas: Path, dir_fotos: Path, agora: Callable[[], str], fracao_auditoria: float, rng: random.Random, espera: float = 0.0, hashes_bloqueados: frozenset[str] = frozenset()`
  - `executar.processar_grupo(ctx: Contexto, row) -> str` (`"aprovada" | "revisao" | "sem_foto"`; propaga `BuscaBloqueada` sem alterar o grupo)
  - `executar.selecionar_piloto(conn, n: int = 100, seed: int = 42) -> list[str]`
  - `executar.main(argv: list[str] | None = None) -> int` (0 = lote processado, 3 = DuckDuckGo bloqueando, 4 = nada pendente)

- [ ] **Step 1: Escrever o teste que falha**

`catalogo/tests/test_fotos_executar.py`:

```python
import io
import random

import pytest

pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from catalogo.db import conectar, criar_schema, upsert_produto  # noqa: E402
from catalogo.fotos import banco, busca, executar  # noqa: E402
from catalogo.fotos.normalizar import normalizar  # noqa: E402
from catalogo.models import Produto  # noqa: E402

Q = "2026-10-05T12:00:00"


def _img(cor) -> bytes:
    im = Image.new("RGB", (300, 300), "white")
    im.paste(Image.new("RGB", (200, 200), cor), (50, 50))
    buf = io.BytesIO()
    im.save(buf, "PNG")
    return buf.getvalue()


IMAGENS = {"https://img/vermelha.png": _img("red"), "https://img/azul.png": _img("blue"),
           "https://img/cinza.png": _img("gray")}


class Visao:
    """Falso CLIP: vermelho = tipo certo em 1º; azul = tipo em 40º; cinza = lixo."""

    def ranking(self, dados, tipo_en):
        r, g, b = Image.open(io.BytesIO(dados)).convert("RGB").getpixel((200, 200))
        if r > 200 and b < 80:
            return (1 if tipo_en else None), False, tipo_en or "car tire"
        if b > 200 and r < 80:
            return 40, False, "car tire"
        return 2, True, "LIXO:placeholder"


class Ocr:
    def __init__(self, texto=""):
        self.texto = texto

    def ler(self, dados):
        return self.texto


def _ctx(conn, tmp_path, resultados, ocr="", fracao=0.0):
    def buscador(consulta):
        if isinstance(resultados, Exception):
            raise resultados
        return [busca.Resultado(url, "https://produto.mercadolivre.com.br/x", titulo) for url, titulo in resultados]

    return executar.Contexto(conn=conn, buscador=buscador, baixador=IMAGENS.get, visao=Visao(), ocr=Ocr(ocr),
                             dir_candidatas=tmp_path / "cand", dir_fotos=tmp_path / "fotos", agora=lambda: Q,
                             fracao_auditoria=fracao, rng=random.Random(0))


@pytest.fixture
def conn():
    c = conectar(":memory:")
    criar_schema(c)
    for codigo, desc, cat in [("1", "PASTILHA FREIO DT AGILE/CELTA", "Freios"),
                              ("2", "OLEO MOTOR 15W40 PETRONAS SYNTIUM 800 SE", "Lubrificantes e Químicos"),
                              ("3", "AMORT DT UNO 10/", "Suspensão e Direção")]:
        upsert_produto(c, Produto(id=0, codigo=codigo, descricao=desc, categoria=cat))
    c.commit()
    banco.criar_schema_fotos(c)
    banco.sincronizar_grupos(c, Q)
    yield c
    c.close()


def _grupo(conn, codigo):
    return conn.execute("SELECT g.* FROM foto_grupos g JOIN produtos p ON p.foto_grupo = g.chave"
                        " WHERE p.codigo = ?", (codigo,)).fetchone()


def _imagem(conn, codigo):
    return conn.execute("SELECT imagem_url FROM produtos WHERE codigo = ?", (codigo,)).fetchone()[0]


def _pendentes(conn, tipo):
    return conn.execute("SELECT count(*) FROM foto_revisao WHERE tipo = ? AND status = 'pendente'",
                        (tipo,)).fetchone()[0]


def test_tudo_concorda_aprova_publica_e_audita(conn, tmp_path):
    ctx = _ctx(conn, tmp_path, [("https://img/vermelha.png", "Pastilha Freio Dianteira Agile Cobreq")], fracao=1.0)
    assert executar.processar_grupo(ctx, _grupo(conn, "1")) == "aprovada"
    assert _imagem(conn, "1").startswith("/fotos/")
    assert _pendentes(conn, "auditoria") == 1
    assert list((tmp_path / "cand").glob("*.webp")) == []  # candidata copiada e apagada


def test_titulo_sem_carro_vai_para_revisao_com_as_candidatas(conn, tmp_path):
    ctx = _ctx(conn, tmp_path, [("https://img/vermelha.png", "Pastilha Freio Dianteira Cobreq"),
                                ("https://img/azul.png", "Pastilha Freio Agile")])
    assert executar.processar_grupo(ctx, _grupo(conn, "1")) == "revisao"
    assert _imagem(conn, "1") == ""
    candidatas = banco.candidatas_de(conn, _grupo(conn, "1")["chave"])
    assert len(candidatas) == 2 and all((tmp_path / "cand" / c["arquivo"]).exists() for c in candidatas)
    assert _pendentes(conn, "revisao") == 1


def test_marca_fora_do_titulo_ou_outra_marca_no_rotulo_nao_aprovam(conn, tmp_path):
    chave = _grupo(conn, "2")["chave"]
    ctx = _ctx(conn, tmp_path, [("https://img/vermelha.png", "Oleo Motor 15w40 Syntium 800 1 Litro")])
    assert executar.processar_grupo(ctx, _grupo(conn, "2")) == "revisao"
    banco.resetar_grupos(conn, [chave], tmp_path / "cand")
    titulo = "Oleo Petronas Syntium 800 15w40 Motor"
    ctx = _ctx(conn, tmp_path, [("https://img/vermelha.png", titulo)], ocr="LUBRAX ESSENCIAL")
    assert executar.processar_grupo(ctx, _grupo(conn, "2")) == "revisao"
    banco.resetar_grupos(conn, [chave], tmp_path / "cand")
    ctx = _ctx(conn, tmp_path, [("https://img/vermelha.png", titulo)], ocr="PETRONAS SYNTIUM")
    assert executar.processar_grupo(ctx, _grupo(conn, "2")) == "aprovada"


def test_so_lixo_fica_sem_foto_e_cria_grupo_de_tipo(conn, tmp_path):
    ctx = _ctx(conn, tmp_path, [("https://img/cinza.png", "Amortecedor Dianteiro Uno")])
    assert executar.processar_grupo(ctx, _grupo(conn, "3")) == "sem_foto"
    assert _grupo(conn, "3")["tentativas"] == 1
    tipo = conn.execute("SELECT * FROM foto_grupos WHERE chave = 'TIPO:amortecedor'").fetchone()
    assert tipo["status"] == "pendente" and tipo["n_produtos"] == 1


def test_titulo_de_placeholder_nem_e_baixado(conn, tmp_path):
    ctx = _ctx(conn, tmp_path, [("https://img/vermelha.png", "Imagem indisponível")])
    assert executar.processar_grupo(ctx, _grupo(conn, "3")) == "sem_foto"


def test_grupo_de_tipo_nunca_aprova_sozinho(conn, tmp_path):
    chave = banco.garantir_grupo_tipo(conn, normalizar("AMORT DT UNO 10/"), Q)
    row = conn.execute("SELECT * FROM foto_grupos WHERE chave = ?", (chave,)).fetchone()
    ctx = _ctx(conn, tmp_path, [("https://img/vermelha.png", "Amortecedor Dianteiro")])
    assert executar.processar_grupo(ctx, row) == "revisao"


def test_busca_bloqueada_deixa_o_grupo_pendente(conn, tmp_path):  # Review Focus 4
    ctx = _ctx(conn, tmp_path, busca.BuscaBloqueada("202 Ratelimit"))
    with pytest.raises(busca.BuscaBloqueada):
        executar.processar_grupo(ctx, _grupo(conn, "1"))
    assert _grupo(conn, "1")["status"] == "pendente"


def test_piloto_estratificado_e_deterministico(conn):
    a = executar.selecionar_piloto(conn, n=6, seed=42)
    assert a == executar.selecionar_piloto(conn, n=6, seed=42)
    assert sorted(a) == sorted({_grupo(conn, c)["chave"] for c in ("1", "2", "3")})


def test_main_sem_pendentes_e_relatorio(tmp_path, capsys):
    db = tmp_path / "vazio.db"
    assert executar.main(["--db", str(db)]) == 4
    assert executar.main(["--db", str(db), "--relatorio"]) == 0
    assert "produtos_ativos" in capsys.readouterr().out
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `catalogo/.venv-fotos/bin/python -m pytest catalogo/tests/test_fotos_executar.py -v`
Expected: FAIL, `ImportError: cannot import name 'executar'`

- [ ] **Step 3: Adicionar os diretórios ao `config.py`**

Em `catalogo/config.py`, substituir a dataclass `Settings` e a função `get_settings` por:

```python
@dataclass(frozen=True)
class Settings:
    nome_loja: str
    site_url: str
    db_path: str
    fonte_xlsx_path: str
    por_pagina: int = 48
    fotos_dir: str = str(BASE_DIR / "data" / "fotos")
    candidatas_dir: str = str(BASE_DIR / "data" / "fotos_candidatas")
    backups_dir: str = str(BASE_DIR / "data" / "backups")
    revisao_dir: str = str(BASE_DIR / "revisao" / "folhas")


def get_settings() -> Settings:
    return Settings(
        nome_loja=os.getenv("NOME_LOJA", "Carreiro Auto Peças"),
        site_url=os.getenv("SITE_URL", "https://carreiro-autopecas.netlify.app"),
        db_path=os.getenv("DB_PATH", str(BASE_DIR / "data" / "catalogo.db")),
        # Planilha exportada do sistema da loja (ver README, seção "Planilha real").
        fonte_xlsx_path=os.getenv("FONTE_XLSX_PATH", ""),
        por_pagina=int(os.getenv("POR_PAGINA", "48")),
        # Pipeline de fotos (ver README, seção "Fotos")
        fotos_dir=os.getenv("FOTOS_DIR", str(BASE_DIR / "data" / "fotos")),
        candidatas_dir=os.getenv("CANDIDATAS_DIR", str(BASE_DIR / "data" / "fotos_candidatas")),
        backups_dir=os.getenv("BACKUPS_DIR", str(BASE_DIR / "data" / "backups")),
        revisao_dir=os.getenv("REVISAO_DIR", str(BASE_DIR / "revisao" / "folhas")),
    )
```

- [ ] **Step 4: Implementar o orquestrador**

`catalogo/fotos/executar.py`:

```python
"""Processa grupos pendentes: busca → baixa → verifica → aprova, manda para revisão ou fica sem foto.

    catalogo/.venv-fotos/bin/python -m catalogo.fotos.executar --limite 100     # um lote
    catalogo/.venv-fotos/bin/python -m catalogo.fotos.executar --piloto         # amostra fixa, audita 100%
    catalogo/.venv-fotos/bin/python -m catalogo.fotos.executar --refazer-piloto # volta o piloto a pendente
    catalogo/.venv-fotos/bin/python -m catalogo.fotos.executar --relatorio

Retorno: 0 = lote processado, 3 = DuckDuckGo bloqueando (rode de novo depois), 4 = nada pendente.
O status do grupo só é gravado no fim do processamento: interrompido no meio, ele continua pendente.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sqlite3
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from catalogo.config import get_settings
from catalogo.db import conectar, criar_schema
from catalogo.fotos import banco, busca, imagem
from catalogo.fotos.dados.tipos_en import TIPOS_EN
from catalogo.fotos.normalizar import Chave
from catalogo.fotos.verificar import Decisao, Sinais, decidir, marca_no_ocr, outra_marca_no_ocr, sinais_de_texto

MAX_DOWNLOADS = 8        # candidatas baixadas por consulta
MAX_REVISAO = 4          # candidatas mostradas ao Agy
PAUSAS_BLOQUEIO = (0, 30, 90, 300)  # segundos antes de cada tentativa quando o DuckDuckGo recusa


@dataclass
class Contexto:
    conn: sqlite3.Connection
    buscador: Callable[[str], list[busca.Resultado]]
    baixador: Callable[[str], bytes | None]
    visao: Any
    ocr: Any
    dir_candidatas: Path
    dir_fotos: Path
    agora: Callable[[], str]
    fracao_auditoria: float
    rng: random.Random
    espera: float = 0.0
    hashes_bloqueados: frozenset[str] = frozenset()


@dataclass
class Avaliada:
    decisao: Decisao
    resultado: busca.Resultado
    webp: bytes
    clip_rank: int | None
    clip_top: str
    ocr: str


def _avaliar(ctx: Contexto, ch: Chave, resultados: list[busca.Resultado]) -> list[Avaliada]:
    avaliadas: list[Avaliada] = []
    baixadas = 0
    for r in resultados:
        if baixadas >= MAX_DOWNLOADS:
            break
        if busca.bloqueado(r) or imagem.termo_placeholder(f"{r.titulo} {r.url_imagem}"):
            continue
        dados = ctx.baixador(r.url_imagem)
        baixadas += 1
        if not dados or imagem.sha1(dados) in ctx.hashes_bloqueados:
            continue
        processada, _motivo = imagem.processar(dados)
        if processada is None:
            continue
        rank, lixo, topo = ctx.visao.ranking(processada.webp, ch.tipo_en)
        texto_ocr = ctx.ocr.ler(dados) if ch.marca else ""
        sinais = Sinais(
            valida=True, clip_rank=rank, clip_top_lixo=lixo, **sinais_de_texto(ch, r.titulo),
            ocr_marca=bool(ch.marca) and marca_no_ocr(ch.marca, texto_ocr),
            ocr_outra_marca=bool(ch.marca) and outra_marca_no_ocr(ch.marca, texto_ocr),
            dominio_loja=busca.eh_loja(r), fundo_branco=processada.fundo_branco,
        )
        avaliadas.append(Avaliada(decidir(ch, sinais), r, processada.webp, rank, topo, texto_ocr))
    return avaliadas


def _nome_candidata(chave: str, i: int) -> str:
    return f"{hashlib.sha1(chave.encode()).hexdigest()[:12]}_{i}.webp"


def _registrar(ctx: Contexto, chave: str, avaliadas: list[Avaliada]) -> list[int]:
    Path(ctx.dir_candidatas).mkdir(parents=True, exist_ok=True)
    novas = []
    for i, a in enumerate(avaliadas):
        nome = _nome_candidata(chave, i)
        (Path(ctx.dir_candidatas) / nome).write_bytes(a.webp)
        novas.append(banco.NovaCandidata(
            arquivo=nome, url=a.resultado.url_pagina or a.resultado.url_imagem, titulo=a.resultado.titulo,
            dominio=busca.dominio(a.resultado.url_imagem), clip_rank=a.clip_rank, clip_top=a.clip_top,
            ocr_texto=a.ocr[:300], pontuacao=a.decisao.pontuacao, aprovada_auto=a.decisao.aprovada,
            motivo="; ".join(a.decisao.motivos)))
    return banco.registrar_candidatas(ctx.conn, chave, novas)


def _por_pontuacao(avaliadas: list[Avaliada]) -> list[Avaliada]:
    return sorted(avaliadas, key=lambda a: -a.decisao.pontuacao)


def processar_grupo(ctx: Contexto, row: sqlite3.Row) -> str:
    ch = banco.chave_de(row)
    chave = row["chave"]
    avaliadas: list[Avaliada] = []
    for consulta in (c for c in (row["consulta"], row["consulta_alt"]) if c):
        avaliadas = _avaliar(ctx, ch, ctx.buscador(consulta))
        if ctx.espera:
            time.sleep(ctx.espera)
        if any(a.decisao.plausivel for a in avaliadas):
            break

    quando = ctx.agora()
    banco.limpar_candidatas(ctx.conn, chave, ctx.dir_candidatas)
    aprovadas = _por_pontuacao([a for a in avaliadas if a.decisao.aprovada])
    if aprovadas:
        [candidata_id] = _registrar(ctx, chave, aprovadas[:1])
        banco.aprovar(ctx.conn, chave, candidata_id, origem="auto", quando=quando,
                      dir_candidatas=ctx.dir_candidatas, dir_fotos=ctx.dir_fotos)
        banco.limpar_candidatas(ctx.conn, chave, ctx.dir_candidatas)
        if ctx.rng.random() < ctx.fracao_auditoria:
            banco.registrar_revisao(ctx.conn, chave, "auditoria", quando)
        return "aprovada"

    plausiveis = _por_pontuacao([a for a in avaliadas if a.decisao.plausivel])[:MAX_REVISAO]
    if plausiveis:
        _registrar(ctx, chave, plausiveis)
        banco.marcar_status(ctx.conn, chave, "revisao", quando)
        banco.registrar_revisao(ctx.conn, chave, "revisao", quando)
        return "revisao"

    banco.marcar_status(ctx.conn, chave, "sem_foto", quando, tentativa=True)
    banco.garantir_grupo_tipo(ctx.conn, ch, quando)
    return "sem_foto"


def selecionar_piloto(conn: sqlite3.Connection, n: int = 100, seed: int = 42) -> list[str]:
    """Amostra fixa estratificada pelas categorias; devolve as chaves de grupo (sem repetir)."""
    rng = random.Random(seed)
    categorias = [r[0] for r in conn.execute(
        "SELECT DISTINCT categoria FROM produtos WHERE ativo = 1 AND foto_grupo != '' ORDER BY categoria")]
    if not categorias:
        return []
    por_categoria = math.ceil(n / len(categorias))
    chaves: list[str] = []
    for categoria in categorias:
        grupos = [r[0] for r in conn.execute(
            "SELECT foto_grupo FROM produtos WHERE ativo = 1 AND foto_grupo != '' AND categoria = ? ORDER BY codigo",
            (categoria,))]
        chaves += rng.sample(grupos, min(por_categoria, len(grupos)))
    return list(dict.fromkeys(chaves))


def _hashes_bloqueados(pasta: Path) -> frozenset[str]:
    arquivo = pasta / "hashes_bloqueados.txt"
    if not arquivo.exists():
        return frozenset()
    return frozenset(l.strip() for l in arquivo.read_text().splitlines() if l.strip() and not l.startswith("#"))


def _imprimir_relatorio(conn: sqlite3.Connection) -> None:
    print(json.dumps(banco.relatorio(conn), ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    s = get_settings()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=s.db_path)
    ap.add_argument("--limite", type=int, default=100, help="grupos por lote")
    ap.add_argument("--piloto", action="store_true", help="só a amostra fixa (~100 produtos); audita 100%%")
    ap.add_argument("--refazer-piloto", action="store_true", help="volta os grupos do piloto para pendente")
    ap.add_argument("--espera", type=float, default=3.0, help="segundos entre buscas")
    ap.add_argument("--auditar", type=float, default=0.03, help="fração das aprovações automáticas auditada")
    ap.add_argument("--relatorio", action="store_true")
    args = ap.parse_args(argv)

    conn = conectar(args.db)
    try:
        criar_schema(conn)
        banco.criar_schema_fotos(conn)
        if args.relatorio:
            _imprimir_relatorio(conn)
            return 0
        banco.sincronizar_grupos(conn, banco.agora())
        chaves = selecionar_piloto(conn) if (args.piloto or args.refazer_piloto) else None
        if args.refazer_piloto:
            n = banco.resetar_grupos(conn, chaves or [], Path(s.candidatas_dir))
            print(f"{n} grupos do piloto voltaram para pendente.")
            return 0
        fila = banco.grupos_pendentes(conn, len(chaves) if chaves is not None else args.limite, chaves)
        if not fila:
            print("Nada pendente.")
            return 4

        from catalogo.fotos import modelos  # pesado: só carrega quando há trabalho

        ctx = Contexto(
            conn=conn, buscador=busca.buscar_imagens, baixador=busca.baixar,
            visao=modelos.Visao(sorted(set(TIPOS_EN.values()))), ocr=modelos.Ocr(),
            dir_candidatas=Path(s.candidatas_dir), dir_fotos=Path(s.fotos_dir), agora=banco.agora,
            fracao_auditoria=1.0 if args.piloto else args.auditar, rng=random.Random(),
            espera=args.espera, hashes_bloqueados=_hashes_bloqueados(Path(args.db).parent),
        )
        contagem: Counter[str] = Counter()
        for i, row in enumerate(fila, 1):
            for pausa in PAUSAS_BLOQUEIO:
                time.sleep(pausa)
                try:
                    status = processar_grupo(ctx, row)
                    break
                except busca.BuscaBloqueada as erro:
                    print(f"  DuckDuckGo recusou ({erro}); tentando de novo...", flush=True)
            else:
                print("DuckDuckGo segue bloqueando. Parei; o que já foi feito está salvo. Rode de novo mais tarde.")
                return 3
            contagem[status] += 1
            print(f"[{i}/{len(fila)}] {status:<9} {row['n_produtos']:>4} prod.  {row['consulta'][:70]}", flush=True)
        print("Lote:", dict(contagem))
        _imprimir_relatorio(conn)
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: Rodar e ver passar**

Run: `catalogo/.venv-fotos/bin/python -m pytest catalogo/tests/test_fotos_executar.py -v`
Expected: 9 passed

- [ ] **Step 6: Suíte inteira**

Run: `catalogo/.venv-fotos/bin/python -m pytest catalogo/tests -q`
Expected: tudo passa

- [ ] **Step 7: Commit**

```bash
git add catalogo/config.py catalogo/fotos/executar.py catalogo/tests/test_fotos_executar.py
git commit -m "feat(fotos): orquestrador por grupo com aprovacao, revisao, sem foto e piloto

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Revisão pelo Agy (folhas de contato + decisões)

**Files:**
- Create: `catalogo/fotos/revisar.py`
- Create: `catalogo/revisao/CONTEXTO_AGY.md`
- Create: `catalogo/revisao/PROMPT_AGY.md`
- Test: `catalogo/tests/test_fotos_revisar.py`

**Interfaces:**
- Consumes: `banco.*`, `Settings.candidatas_dir/fotos_dir/backups_dir/revisao_dir`.
- Produces: `revisar.LADO_MINIATURA: int = 220`; `revisar.parse_decisoes(texto: str) -> list[tuple[int, str]]` (valor `"0"`–`"9"` ou `"x"`); `revisar.pendentes(conn) -> list[sqlite3.Row]`; `revisar.aplicar(conn, decisoes, *, por: str, quando: str, dir_candidatas: Path, dir_fotos: Path) -> dict[str, int]` (valida tudo antes de mudar qualquer coisa; `ValueError` se algo não bate); `revisar.gerar(conn, dir_saida: Path, dir_candidatas: Path, dir_fotos: Path) -> list[Path]`; `revisar.main(argv) -> int` (0 ok, 2 decisão inválida).

- [ ] **Step 1: Escrever o teste que falha**

`catalogo/tests/test_fotos_revisar.py`:

```python
import pytest

pytest.importorskip("PIL")
from PIL import Image  # noqa: E402

from catalogo.db import conectar, criar_schema, upsert_produto  # noqa: E402
from catalogo.fotos import banco, revisar  # noqa: E402
from catalogo.models import Produto  # noqa: E402

Q = "2026-10-05T12:00:00"


@pytest.fixture
def estado(tmp_path):
    db = tmp_path / "c.db"
    conn = conectar(str(db))
    criar_schema(conn)
    for codigo, desc in [("1", "PASTILHA FREIO DT AGILE/CELTA"), ("2", "AMORT DT UNO 10/")]:
        upsert_produto(conn, Produto(id=0, codigo=codigo, descricao=desc, categoria="Freios"))
    conn.commit()
    banco.criar_schema_fotos(conn)
    banco.sincronizar_grupos(conn, Q)
    cand = tmp_path / "cand"
    cand.mkdir()
    rids = {}
    for codigo in ("1", "2"):
        chave = conn.execute("SELECT foto_grupo FROM produtos WHERE codigo = ?", (codigo,)).fetchone()[0]
        novas = []
        for i, cor in enumerate(("red", "blue")):
            nome = f"{codigo}_{i}.webp"
            Image.new("RGB", (400, 400), cor).save(cand / nome, "WEBP")
            novas.append(banco.NovaCandidata(nome, f"https://loja/{codigo}/{i}", f"Titulo {codigo} {i}", "loja",
                                             1, "brake pad", "", 50 - i, False, "titulo_sem_veiculo"))
        banco.registrar_candidatas(conn, chave, novas)
        banco.marcar_status(conn, chave, "revisao", Q)
        rids[codigo] = banco.registrar_revisao(conn, chave, "revisao", Q)
    yield {"db": db, "conn": conn, "cand": cand, "fotos": tmp_path / "fotos", "rids": rids}
    conn.close()


def _imagem(conn, codigo):
    return conn.execute("SELECT imagem_url FROM produtos WHERE codigo = ?", (codigo,)).fetchone()[0]


def _aplicar(e, texto):
    return revisar.aplicar(e["conn"], revisar.parse_decisoes(texto), por="agy", quando=Q,
                           dir_candidatas=e["cand"], dir_fotos=e["fotos"])


def test_parse_decisoes():
    assert revisar.parse_decisoes("12:0, 13:X") == [(12, "0"), (13, "x")]
    for ruim in ("", "12-0", "12:9x", "1:0,1:x", "abc"):
        with pytest.raises(ValueError):
            revisar.parse_decisoes(ruim)


def test_escolher_candidata_aprova_na_ordem_da_folha(estado):
    r1 = estado["rids"]["1"]
    azul = (estado["cand"] / "1_1.webp").read_bytes()  # [1] na folha = 2ª maior pontuação
    assert _aplicar(estado, f"{r1}:1")["aprovadas"] == 1
    url = _imagem(estado["conn"], "1")
    assert (estado["fotos"] / url.removeprefix("/fotos/")).read_bytes() == azul
    rev = estado["conn"].execute("SELECT * FROM foto_revisao WHERE id = ?", (r1,)).fetchone()
    assert (rev["status"], rev["decidido_por"]) == ("aprovada", "agy")
    assert banco.candidatas_de(estado["conn"], rev["chave"]) == []
    assert not (estado["cand"] / "1_0.webp").exists()  # candidatas do grupo decidido são apagadas


def test_x_rejeita_e_cria_grupo_de_tipo(estado):
    _aplicar(estado, f"{estado['rids']['2']}:x")
    tipo = estado["conn"].execute("SELECT status FROM foto_grupos WHERE chave = 'TIPO:amortecedor'").fetchone()
    assert tipo[0] == "pendente"
    assert _imagem(estado["conn"], "2") == ""


def test_erro_no_comando_nao_aplica_nada(estado):  # Review Focus 3
    r1, r2 = estado["rids"]["1"], estado["rids"]["2"]
    for texto in (f"{r1}:0,999:0", f"{r1}:0,{r2}:7"):
        with pytest.raises(ValueError):
            _aplicar(estado, texto)
    status = [r[0] for r in estado["conn"].execute("SELECT status FROM foto_revisao ORDER BY id")]
    assert status == ["pendente", "pendente"] and _imagem(estado["conn"], "1") == ""


def test_auditoria_confirma_ou_desfaz(estado):
    _aplicar(estado, f"{estado['rids']['1']}:0")
    chave = estado["conn"].execute("SELECT foto_grupo FROM produtos WHERE codigo = '1'").fetchone()[0]
    aud = banco.registrar_revisao(estado["conn"], chave, "auditoria", Q)
    with pytest.raises(ValueError):
        _aplicar(estado, f"{aud}:1")
    assert _aplicar(estado, f"{aud}:x")["desfeitas"] == 1
    assert _imagem(estado["conn"], "1") == ""


def test_gerar_folhas_png_txt_e_html(estado, tmp_path):
    arquivos = revisar.gerar(estado["conn"], tmp_path / "folhas", estado["cand"], estado["fotos"])
    nomes = sorted(p.name for p in arquivos)
    assert nomes == ["folha_001.png", "folha_001.txt", "index.html"]
    texto = (tmp_path / "folhas" / "folha_001.txt").read_text()
    assert f"R{estado['rids']['1']}" in texto and "Titulo 1 0" in texto
    assert Image.open(tmp_path / "folhas" / "folha_001.png").width == 4 * (revisar.LADO_MINIATURA + 10) + 10


def test_main_faz_backup_antes_de_decidir(estado, tmp_path, monkeypatch):
    monkeypatch.setenv("BACKUPS_DIR", str(tmp_path / "bk"))
    monkeypatch.setenv("CANDIDATAS_DIR", str(estado["cand"]))
    monkeypatch.setenv("FOTOS_DIR", str(estado["fotos"]))
    assert revisar.main(["--db", str(estado["db"]), "--decidir", "abc"]) == 2      # nem chega ao backup
    assert revisar.main(["--db", str(estado["db"]), "--decidir", "999:0"]) == 2    # backup feito, nada aplicado
    assert revisar.main(["--db", str(estado["db"]), "--decidir", f"{estado['rids']['1']}:0"]) == 0
    assert len(list((tmp_path / "bk").glob("*.db"))) == 2
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `catalogo/.venv-fotos/bin/python -m pytest catalogo/tests/test_fotos_revisar.py -v`
Expected: FAIL, `ImportError: cannot import name 'revisar'`

- [ ] **Step 3: Implementar `revisar.py`**

`catalogo/fotos/revisar.py`:

```python
"""Fila de revisão (Agy) e auditoria: gera folhas de contato e aplica as decisões.

    catalogo/.venv-fotos/bin/python -m catalogo.fotos.revisar --gerar            # folhas em catalogo/revisao/folhas/
    catalogo/.venv-fotos/bin/python -m catalogo.fotos.revisar --decidir 812:2,813:x
    catalogo/.venv-fotos/bin/python -m catalogo.fotos.revisar --status

Decisão por item da fila (o número "R812" impresso na folha):
  revisão   → número da candidata (0..3) que está CERTA, ou x se nenhuma serve
  auditoria → 0 confirma a foto aprovada automaticamente, x rejeita (a foto sai do site)
Tudo é validado antes de mudar qualquer coisa, e o banco ganha backup antes.
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

from catalogo.config import get_settings
from catalogo.db import conectar, criar_schema
from catalogo.fotos import banco

POR_FOLHA = 5
LADO_MINIATURA = 220
_DECISAO = re.compile(r"^(\d+):(\d|x)$")
_FONTE_NORMAL = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
_FONTE_NEGRITO = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def parse_decisoes(texto: str) -> list[tuple[int, str]]:
    itens = [p.strip().lower() for p in (texto or "").split(",") if p.strip()]
    if not itens:
        raise ValueError("nenhuma decisão informada")
    decisoes = []
    for item in itens:
        m = _DECISAO.match(item)
        if not m:
            raise ValueError(f"decisão inválida: {item!r} (use ID:N ou ID:x)")
        decisoes.append((int(m.group(1)), m.group(2)))
    ids = [i for i, _ in decisoes]
    if len(set(ids)) != len(ids):
        raise ValueError("o mesmo ID aparece mais de uma vez")
    return decisoes


def pendentes(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT r.id, r.tipo, r.chave, g.descricao_ref, g.consulta, g.marca, g.lado, g.arquivo, g.n_produtos,"
        " g.e_tipo, g.titulo_origem, g.url_origem FROM foto_revisao r JOIN foto_grupos g ON g.chave = r.chave"
        " WHERE r.status = 'pendente' ORDER BY r.tipo DESC, g.n_produtos DESC, r.id"
    ).fetchall()


def aplicar(conn: sqlite3.Connection, decisoes: list[tuple[int, str]], *, por: str, quando: str,
            dir_candidatas: Path, dir_fotos: Path) -> dict[str, int]:
    # 1ª passada: só valida. Qualquer problema levanta ValueError antes de qualquer mudança.
    plano = []
    for rid, valor in decisoes:
        r = conn.execute(
            "SELECT r.*, g.e_tipo, g.descricao_ref, g.tipo_pt, g.tipo_en FROM foto_revisao r"
            " JOIN foto_grupos g ON g.chave = r.chave WHERE r.id = ?", (rid,)).fetchone()
        if r is None:
            raise ValueError(f"R{rid} não existe")
        if r["status"] != "pendente":
            raise ValueError(f"R{rid} já foi decidida ({r['status']})")
        if r["tipo"] == "auditoria":
            if valor not in ("0", "x"):
                raise ValueError(f"R{rid} é auditoria: use 0 (confirma) ou x (rejeita)")
            plano.append((r, valor, None))
            continue
        if valor == "x":
            plano.append((r, valor, None))
            continue
        candidatas = banco.candidatas_de(conn, r["chave"])
        if int(valor) >= len(candidatas):
            raise ValueError(f"R{rid}: candidata {valor} não existe (há {len(candidatas)})")
        plano.append((r, valor, candidatas[int(valor)]["id"]))

    # 2ª passada: aplica.
    contagem = {"aprovadas": 0, "rejeitadas": 0, "confirmadas": 0, "desfeitas": 0}
    for r, valor, candidata_id in plano:
        chave = r["chave"]
        if r["tipo"] == "auditoria":
            if valor == "0":
                status = "aprovada"
                contagem["confirmadas"] += 1
            else:
                banco.rejeitar_grupo(conn, chave, origem=f"auditoria:{por}", quando=quando)
                banco.garantir_grupo_tipo(conn, banco.chave_de(r), quando)
                status = "rejeitada"
                contagem["desfeitas"] += 1
        elif valor == "x":
            banco.rejeitar_grupo(conn, chave, origem=por, quando=quando)
            banco.garantir_grupo_tipo(conn, banco.chave_de(r), quando)
            status = "rejeitada"
            contagem["rejeitadas"] += 1
        else:
            banco.aprovar(conn, chave, candidata_id, origem=por, quando=quando,
                          dir_candidatas=dir_candidatas, dir_fotos=dir_fotos)
            status = "aprovada"
            contagem["aprovadas"] += 1
        banco.decidir_revisao(conn, r["id"], status, candidata_id=candidata_id, por=por, quando=quando)
        if r["tipo"] == "revisao":
            banco.limpar_candidatas(conn, chave, dir_candidatas)
    return contagem


def _exigencias(item: sqlite3.Row) -> str:
    if item["e_tipo"]:
        return "FOTO GENÉRICA DO TIPO DE PEÇA (sem carro, sem marca)"
    partes = ["tipo de peça"]
    veiculo = item["chave"].split("|")[1]  # chave = "peca|veiculo|lado|marca"
    if veiculo:
        partes.append(f"carro {veiculo}")
    if item["lado"]:
        partes.append(f"lado {item['lado']}")
    if item["marca"]:
        partes.append(f"marca {item['marca']}")
    return " + ".join(partes)


def _imagens(conn: sqlite3.Connection, item: sqlite3.Row, dir_candidatas: Path, dir_fotos: Path):
    """Lista de (rótulo, caminho, título, url, motivo) na ordem em que aparecem na folha."""
    if item["tipo"] == "auditoria":
        return [("0", Path(dir_fotos) / item["arquivo"], item["titulo_origem"], item["url_origem"], "")]
    return [(str(i), Path(dir_candidatas) / c["arquivo"], c["titulo"], c["url"], c["motivo"])
            for i, c in enumerate(banco.candidatas_de(conn, item["chave"])[:4])]


def _fontes():
    from PIL import ImageFont

    try:
        return ImageFont.truetype(_FONTE_NEGRITO, 16), ImageFont.truetype(_FONTE_NORMAL, 12)
    except OSError:
        padrao = ImageFont.load_default()
        return padrao, padrao


def gerar(conn: sqlite3.Connection, dir_saida: Path, dir_candidatas: Path, dir_fotos: Path) -> list[Path]:
    from PIL import Image, ImageDraw

    dir_saida = Path(dir_saida)
    dir_saida.mkdir(parents=True, exist_ok=True)
    for antigo in list(dir_saida.glob("folha_*")) + list(dir_saida.glob("index.html")):
        antigo.unlink()
    itens = pendentes(conn)
    fonte, fonte_p = _fontes()
    arquivos: list[Path] = []
    for n, inicio in enumerate(range(0, len(itens), POR_FOLHA), start=1):
        bloco = itens[inicio:inicio + POR_FOLHA]
        altura_linha = LADO_MINIATURA + 80
        folha = Image.new("RGB", (4 * (LADO_MINIATURA + 10) + 10, altura_linha * len(bloco)), "white")
        d = ImageDraw.Draw(folha)
        linhas = []
        for k, item in enumerate(bloco):
            y = k * altura_linha
            descricao = item["descricao_ref"] or item["consulta"]
            regra = "0 confirma / x rejeita" if item["tipo"] == "auditoria" else "N da certa / x nenhuma"
            d.text((8, y + 4), f"R{item['id']} [{item['tipo']}] {descricao}"[:90], fill="black", font=fonte)
            d.text((8, y + 26), f"exige: {_exigencias(item)}  |  {regra}"[:130], fill=(0, 80, 170), font=fonte_p)
            linhas.append(f"R{item['id']} [{item['tipo']}] {descricao}  ({item['n_produtos']} produtos)")
            linhas.append(f"  busca: {item['consulta']}")
            linhas.append(f"  exige: {_exigencias(item)}  |  responda: {regra}")
            for j, (rotulo, caminho, titulo, url, motivo) in enumerate(_imagens(conn, item, dir_candidatas, dir_fotos)):
                x = 10 + j * (LADO_MINIATURA + 10)
                if caminho.exists():
                    with Image.open(caminho) as im:
                        miniatura = im.convert("RGB")
                    miniatura.thumbnail((LADO_MINIATURA, LADO_MINIATURA))
                    folha.paste(miniatura, (x, y + 46))
                d.rectangle((x, y + 46, x + 22, y + 66), fill="red")
                d.text((x + 6, y + 47), rotulo, fill="white", font=fonte)
                d.text((x, y + 48 + LADO_MINIATURA), titulo[:34], fill=(90, 90, 90), font=fonte_p)
                linhas.append(f"  [{rotulo}] {titulo}")
                linhas.append(f"       {url}")
                linhas.append(f"       arquivo: {caminho}")
                if motivo:
                    linhas.append(f"       por que não foi automática: {motivo}")
            linhas.append("")
        png = dir_saida / f"folha_{n:03d}.png"
        txt = dir_saida / f"folha_{n:03d}.txt"
        folha.save(png)
        txt.write_text("\n".join(linhas), encoding="utf-8")
        arquivos += [png, txt]
    corpo = "\n".join(f'<h2>{p.stem}</h2><img src="{p.name}" style="max-width:100%">'
                      for p in arquivos if p.suffix == ".png")
    index = dir_saida / "index.html"
    index.write_text("<!doctype html><meta charset='utf-8'><title>Revisão de fotos</title>"
                     f"<h1>{len(itens)} itens pendentes</h1>{corpo or '<p>Fila vazia.</p>'}", encoding="utf-8")
    return arquivos + [index]


def main(argv: list[str] | None = None) -> int:
    s = get_settings()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=s.db_path)
    ap.add_argument("--gerar", action="store_true", help="gera as folhas de contato da fila pendente")
    ap.add_argument("--decidir", default="", help='ex.: "812:2,813:x"')
    ap.add_argument("--por", default="agy", help="quem decidiu (fica registrado)")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args(argv)

    conn = conectar(args.db)
    try:
        criar_schema(conn)
        banco.criar_schema_fotos(conn)
        if args.decidir:
            try:
                decisoes = parse_decisoes(args.decidir)   # texto inválido: sai antes do backup
                copia = banco.backup(args.db, s.backups_dir)
                contagem = aplicar(conn, decisoes, por=args.por, quando=banco.agora(),
                                   dir_candidatas=Path(s.candidatas_dir), dir_fotos=Path(s.fotos_dir))
            except ValueError as erro:
                print(f"ERRO: {erro}. Nada foi alterado.", file=sys.stderr)
                return 2
            print(f"Backup: {copia}\nAplicado: {contagem}")
        if args.gerar:
            arquivos = gerar(conn, Path(s.revisao_dir), Path(s.candidatas_dir), Path(s.fotos_dir))
            print(f"{len([a for a in arquivos if a.suffix == '.png'])} folhas em {s.revisao_dir}")
        if args.status or not (args.gerar or args.decidir):
            print(json.dumps(banco.relatorio(conn), ensure_ascii=False, indent=2))
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Escrever o contexto e o prompt do Agy**

Dois arquivos: o **contexto** (o que é o projeto, o que é foto correta, como ler as descrições)
e o **prompt** (a tarefa, passo a passo). Para colocar o Agy para trabalhar, basta dizer a ele:
"Leia `catalogo/revisao/PROMPT_AGY.md` e execute."

`catalogo/revisao/CONTEXTO_AGY.md`:

````markdown
# Contexto: fotos do catálogo Carreiro Auto Peças

Leia este arquivo inteiro antes de revisar qualquer foto.

## O projeto

A Carreiro Auto Peças é uma rede de 5 lojas de autopeças (CE/PI). O catálogo online tem
cerca de 17 mil peças e nenhuma tinha foto. A planilha da loja só traz um **nome abreviado**
de cada produto (sem código de barras, sem código do fabricante), por exemplo:

    PASTILHA FREIO DT AGILE/CELTA/CORSA/PRISMA

Um robô (`catalogo/fotos/executar.py`) transforma esse nome numa busca
("pastilha freio dianteiro agile"), baixa fotos de anúncios (quase sempre Mercado Livre) e
aprova sozinho só quando todos os sinais batem. **O que ficou em dúvida vem para você.**

Produtos com a mesma peça e o mesmo carro dividem a foto: cada decisão sua vale para todos
os produtos daquele grupo (o número aparece na folha, ex.: "(7 produtos)").

## O que é uma foto CORRETA

A foto é **ilustrativa** (o site avisa isso), mas precisa mostrar a coisa certa. Confira
nesta ordem e pare no primeiro "não":

1. **Tipo de peça.** É a peça descrita? Pastilha não é disco nem sapata. Amortecedor não é
   kit de batente. Bomba d'água não é bomba de combustível.
2. **Posição.** Dianteiro não é traseiro. Superior não é inferior.
3. **Carro.** Quando a folha diz `carro X`, o anúncio precisa ser para esse carro (olhe o
   título do anúncio, embaixo de cada imagem e completo no `.txt`).
4. **Lado.** Quando diz `lado direito` ou `lado esquerdo`, o anúncio não pode ser do outro lado.
5. **Marca.** Quando diz `marca X`, a embalagem ou o título precisam ser dessa marca.
   Óleo Petronas com foto de óleo Mobil é ERRADO, mesmo sendo "óleo 15W40".
6. **Medida.** Em pneu, óleo, lâmpada e correia a medida faz parte do produto:
   175/75 R13 não é 175/75 R14; 5W30 não é 15W40; H4 não é H7.

Rejeite sempre, mesmo que o título pareça certo:

- desenho técnico ou esquema com cotas;
- foto só do carro, sem a peça;
- caixa fechada sem a peça visível;
- kit com peças que o produto não inclui (ex.: produto "cabos de vela", foto de cabos + velas);
- imagem de "indisponível", banner de propaganda, logotipo;
- marca d'água grande cobrindo a peça;
- foto borrada ou tão pequena que não dá para reconhecer a peça.

Aceite sem problema: fundo branco ou não; peça com um carrinho pequeno desenhado ao lado
(é comum no Mercado Livre); par de peças quando o produto é unitário (duas pastilhas, dois
amortecedores), desde que seja a mesma peça.

**Regra de ouro: foto errada é pior que nenhuma foto. Na dúvida, rejeite.**

## Como ler os nomes abreviados

O nome segue o formato `PEÇA + detalhes + CARRO(S) + ano + lado`. As siglas mais comuns:

| Sigla | Significa | Sigla | Significa |
|---|---|---|---|
| DT, DIANT | dianteiro | TS, TRAS | traseiro |
| LD, L/D | lado direito | LE, L/E | lado esquerdo |
| SUP / INF | superior / inferior | EXT / INT | externo / interno |
| AMORT | amortecedor | ESTAB | (barra) estabilizadora |
| BAND | bandeja | DIR | direção |
| DH, DIR HIDR | direção hidráulica | CX DIR | caixa de direção |
| MT, MTR | motor | MT PART | motor de partida |
| MT VENT | motor da ventoinha | ALT | alternador |
| EMBR | embreagem | HOMOC | homocinética |
| RADIAD, RAD | radiador | DAGUA | d'água |
| VALV | válvula | TERMOST | termostática |
| CABEC | cabeçote | ADM / ESC | admissão / escape |
| COMB | combustível | INJ | injetor |
| IGN | ignição | VOLT | voltagem |
| ACD, AR COND | ar-condicionado | LIMP PARAB | limpador de para-brisa |
| LANT | lanterna | PARACH | para-choque |
| RETROV | retrovisor | SILENC | silencioso (escapamento) |
| ROL | rolamento | JG / CJ | jogo / conjunto |
| C/ | com | S/ | sem |
| SAV, VOY, PAR | Saveiro, Voyage, Parati | D.REY, WEEK | Del Rey, Weekend |
| MBB, MB | Mercedes-Benz | GM | Chevrolet |

Números como `99/`, `08/14`, `1.0/1.6`, `8V` são ano e motor: ajudam a entender, mas não
dá para conferir por foto. Não rejeite por causa deles.

A lista completa de siglas está em `catalogo/fotos/dados/siglas.py`, a de carros em
`catalogo/fotos/dados/veiculos.py` e a de marcas em `catalogo/fotos/dados/marcas.py`.
Você pode ler esses arquivos, mas não editar.

## O que você vai ver nas folhas

`catalogo/revisao/folhas/folha_NNN.png` tem até 5 itens. Cada item traz:

- `R123 [revisao]` ou `R123 [auditoria]`: o número do item e o tipo;
- o nome original da planilha;
- `exige:` o que a foto precisa mostrar (tipo de peça + carro + lado + marca);
- até 4 imagens, cada uma com um número num quadrado vermelho (0, 1, 2, 3) e o começo do
  título do anúncio.

O `folha_NNN.txt` ao lado repete tudo em texto, com o título completo, o link do anúncio, o
caminho do arquivo de cada imagem (para você abrir uma imagem sozinha e ver melhor) e o
motivo de o robô não ter aprovado sozinho.

Dois tipos de item:

- **revisao:** o robô ficou em dúvida. Escolha a imagem certa ou diga que nenhuma serve.
- **auditoria:** o robô aprovou sozinho e a foto JÁ ESTÁ no site. Só há uma imagem.
  Confirme ou derrube. Seja tão rigoroso quanto na revisão: é assim que medimos se o robô
  está acertando.

Item marcado `FOTO GENÉRICA DO TIPO DE PEÇA`: serve qualquer foto limpa daquele tipo de
peça, sem carro específico e sem marca aparente (ela vai cobrir vários produtos sem marca).

## Erros que já vimos o robô encontrar

- foto de "imagem indisponível" com título de anúncio certo;
- óleo ou aditivo de outra marca;
- pneu do mesmo modelo, mas de outro aro;
- desenho técnico no lugar da foto;
- kit com peças a mais;
- peça de posição trocada (traseira no lugar de dianteira).
````

`catalogo/revisao/PROMPT_AGY.md`:

````markdown
# Tarefa: revisar a fila de fotos do catálogo Carreiro Auto Peças

Projeto: `/home/salati/Documentos/projetos/carreiro autopeças/carreiro-autopecas`
Rode todos os comandos a partir dessa pasta, com `catalogo/.venv-fotos/bin/python`.

**Antes de começar, leia `catalogo/revisao/CONTEXTO_AGY.md` inteiro.** Ele explica o
projeto, o que é uma foto correta e como ler os nomes abreviados.

A busca de fotos pode estar rodando em segundo plano enquanto você trabalha (processo
`loop.sh` / `catalogo.fotos.executar`). Isso é esperado: a fila cresce sozinha. Não mexa
nesse processo.

## O que fazer

1. Gere as folhas da fila atual:

   ```bash
   catalogo/.venv-fotos/bin/python -m catalogo.fotos.revisar --gerar
   ```

2. Abra cada `catalogo/revisao/folhas/folha_NNN.png` (você consegue ver imagens) junto com
   o `folha_NNN.txt` correspondente. Para cada item `R<número>`, decida seguindo os
   critérios do contexto (tipo de peça → posição → carro → lado → marca → medida):

   - item `[revisao]`: o número da imagem que está CERTA (0, 1, 2 ou 3), ou `x` se nenhuma serve.
     Se mais de uma serve, escolha a mais limpa (só a peça, fundo claro).
   - item `[auditoria]`: `0` se a foto está certa, `x` se está errada.

   Se a miniatura não der para decidir, abra o arquivo da imagem indicado no `.txt`.
   Continuou em dúvida? `x`.

3. Aplique as decisões de uma folha por vez (número do item sem o "R", separados por vírgula):

   ```bash
   catalogo/.venv-fotos/bin/python -m catalogo.fotos.revisar --decidir 123:2,124:x,125:0
   ```

   O script faz backup do banco antes de aplicar. Se algum número estiver errado, ele
   recusa TUDO, avisa qual foi o problema e não muda nada: corrija e rode de novo.

4. Volte ao passo 1 (as folhas são geradas de novo, só com o que ainda falta) e repita até
   o comando dizer `0 folhas`, ou até completar cerca de 30 minutos de trabalho.
   Se a fila estiver vazia mas a busca ainda estiver rodando, espere 1 minuto e gere de novo.

## Limites

- Não edite nenhum arquivo `.py` nem o banco de dados diretamente: use só os dois comandos acima.
- Não use git (nada de commit, push, checkout).
- Não pare, reinicie nem altere o processo de busca.
- Não apague nada em `catalogo/data/`.

## Relatório final

Ao terminar, responda com:

1. Quantos itens você aprovou, rejeitou (`x` em revisão), confirmou e derrubou (`x` em auditoria).
2. Dos itens de **auditoria** derrubados: o número `R`, o nome do produto e o que a foto
   mostrava de errado. Isso é o mais importante do relatório.
3. Padrões de erro que se repetiram (ex.: "disco de freio aparecendo em pastilha",
   "anúncio de kit em produto unitário", "mesma imagem errada em vários carros").
4. Qualquer sigla ou nome de produto que você não conseguiu entender.
````

- [ ] **Step 5: Rodar e ver passar**

Run: `catalogo/.venv-fotos/bin/python -m pytest catalogo/tests/test_fotos_revisar.py -v`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add catalogo/fotos/revisar.py catalogo/revisao/CONTEXTO_AGY.md catalogo/revisao/PROMPT_AGY.md catalogo/tests/test_fotos_revisar.py
git commit -m "feat(fotos): fila de revisao do Agy com folhas de contato e decisoes validadas

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Foto no card do catálogo

**Files:**
- Modify: `catalogo/app.py` (logo após `app.mount("/static", ...)`)
- Modify: `catalogo/templates/_card_produto.html:2`
- Modify: `catalogo/static/catalogo.css` (depois da regra `.card-ico svg`)
- Test: `catalogo/tests/test_fotos_card.py`

**Interfaces:**
- Consumes: `Produto.imagem_url` (já existe), `Settings.fotos_dir`.

- [ ] **Step 1: Escrever o teste que falha**

`catalogo/tests/test_fotos_card.py`:

```python
from fastapi.testclient import TestClient

from catalogo.db import conectar, criar_schema, upsert_produto
from catalogo.models import Produto


def test_card_mostra_foto_com_selo_ou_icone(tmp_path, monkeypatch):
    db = tmp_path / "app.db"
    conn = conectar(str(db))
    criar_schema(conn)
    upsert_produto(conn, Produto(id=0, codigo="000001", descricao="PASTILHA FREIO DT AGILE",
                                 categoria="Freios", imagem_url="/fotos/abc.webp"))
    upsert_produto(conn, Produto(id=0, codigo="000002", descricao="AMORT DT GOL G5", categoria="Suspensão e Direção"))
    conn.commit()
    conn.close()
    monkeypatch.setenv("DB_PATH", str(db))
    from catalogo.app import app

    c = TestClient(app)
    pagina = c.get("/").text
    assert 'src="/fotos/abc.webp"' in pagina and 'loading="lazy"' in pagina
    assert pagina.count("Imagem ilustrativa") == 1
    assert pagina.count('class="card-ico"') == 1
    assert c.get("/fotos/nao-existe.webp").status_code == 404
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `catalogo/.venv-fotos/bin/python -m pytest catalogo/tests/test_fotos_card.py -v`
Expected: FAIL em `'src="/fotos/abc.webp"' in pagina`

- [ ] **Step 3: Implementar**

Em `catalogo/app.py`, logo depois da linha `app.mount("/static", ...)`:

```python
# Fotos aprovadas pelo pipeline (catalogo/fotos/). A pasta precisa existir: o StaticFiles
# do Starlette confere o diretório na 1ª requisição e quebra (RuntimeError) se ele faltar.
_FOTOS_DIR = Path(get_settings().fotos_dir)
_FOTOS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/fotos", StaticFiles(directory=str(_FOTOS_DIR)), name="fotos")
```

Em `catalogo/templates/_card_produto.html`, trocar a linha 2
(`  <div class="card-ico" aria-hidden="true">{{ icone(p.categoria) }}</div>`) por:

```html
  {% if p.imagem_url %}
  <figure class="card-foto">
    <img src="{{ p.imagem_url }}" alt="{{ p.descricao }}" loading="lazy" decoding="async" width="400" height="400">
    <figcaption>Imagem ilustrativa</figcaption>
  </figure>
  {% else %}
  <div class="card-ico" aria-hidden="true">{{ icone(p.categoria) }}</div>
  {% endif %}
```

Em `catalogo/static/catalogo.css`, depois da regra `.card-ico svg{...}`:

```css
.card-foto{position:relative;margin:0;aspect-ratio:1/1;border-radius:12px;overflow:hidden;background:#fff}
.card-foto img{display:block;width:100%;height:100%;object-fit:contain}
.card-foto figcaption{position:absolute;left:8px;bottom:8px;padding:2px 8px;border-radius:999px;font:600 10.5px var(--font-body);letter-spacing:.02em;background:rgba(6,8,13,.72);color:#e8eef9}
```

- [ ] **Step 4: Rodar e ver passar (e o resto do site)**

Run: `catalogo/.venv-fotos/bin/python -m pytest catalogo/tests/test_fotos_card.py catalogo/tests/test_importacao_e_app.py -v`
Expected: tudo passa

- [ ] **Step 5: Conferir no navegador**

Run: `catalogo/.venv-fotos/bin/uvicorn catalogo.app:app --port 8000` e abrir `http://127.0.0.1:8000`.
Expected: sem fotos aprovadas ainda, todos os cards continuam com o ícone e a página não mudou de layout.

- [ ] **Step 6: Commit**

```bash
git add catalogo/app.py catalogo/templates/_card_produto.html catalogo/static/catalogo.css catalogo/tests/test_fotos_card.py
git commit -m "feat(catalogo): card mostra foto aprovada com selo Imagem ilustrativa

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Loop de execução e documentação

**Files:**
- Create: `catalogo/fotos/loop.sh`
- Modify: `catalogo/README.md` (nova seção "Fotos"; trocar a pendência 4)

- [ ] **Step 1: Criar o loop**

`catalogo/fotos/loop.sh`:

```bash
#!/usr/bin/env bash
# Roda o pipeline de fotos em lotes até não sobrar grupo pendente.
#   nohup catalogo/fotos/loop.sh >> /tmp/fotos_carreiro.log 2>&1 &   # rodar em segundo plano
#   tail -f /tmp/fotos_carreiro.log                                  # acompanhar
#   pkill -INT -f catalogo/fotos/loop.sh; pkill -INT -f catalogo.fotos.executar   # parar
# Pode parar a qualquer momento: grupo interrompido continua pendente e é refeito.
set -u
cd "$(dirname "$0")/../.."
while true; do
  catalogo/.venv-fotos/bin/python -m catalogo.fotos.executar --limite 100
  rc=$?
  case $rc in
    0) sleep 5 ;;                                                    # lote ok, próximo
    4) echo "$(date '+%F %T') nada pendente: fim."; exit 0 ;;
    3) echo "$(date '+%F %T') DuckDuckGo bloqueando: pausa de 30 min."; sleep 1800 ;;
    *) echo "$(date '+%F %T') erro rc=$rc: parei."; exit "$rc" ;;
  esac
done
```

Run: `chmod +x catalogo/fotos/loop.sh && bash -n catalogo/fotos/loop.sh && echo sintaxe-ok`
Expected: `sintaxe-ok`

- [ ] **Step 2: Documentar no README**

Em `catalogo/README.md`, trocar a pendência 4 da lista "Pendências para virar catálogo completo" por:

```markdown
4. Fotos: pipeline pronto (seção "Fotos"); falta rodar o catálogo inteiro e a revisão do Agy. A descrição continua vindo cortada em 45 caracteres do sistema de origem.
```

E acrescentar ao fim do arquivo:

````markdown
## Fotos

Design: `docs/superpowers/specs/2026-10-05-fotos-catalogo-design.md`. A planilha não tem
EAN nem código de fabricante, então a foto é **ilustrativa** e só entra quando tipo de
peça, carro, lado e marca batem. Na dúvida, o produto fica sem foto.

```bash
# uma vez: venv separado (Python 3.12 + torch CPU); pesos dos modelos em /mnt/dados/cache
uv venv --python 3.12 catalogo/.venv-fotos
uv pip install --python catalogo/.venv-fotos/bin/python -r catalogo/requirements-fotos.txt \
  --index-url https://pypi.org/simple --extra-index-url https://download.pytorch.org/whl/cpu \
  --index-strategy unsafe-best-match

catalogo/.venv-fotos/bin/python -m catalogo.fotos.executar --piloto      # amostra fixa, audita 100%
catalogo/.venv-fotos/bin/python -m catalogo.fotos.executar --relatorio
nohup catalogo/fotos/loop.sh >> /tmp/fotos_carreiro.log 2>&1 &         # catálogo inteiro (~12-24h)
catalogo/.venv-fotos/bin/python -m catalogo.fotos.revisar --gerar       # folhas para o Agy
catalogo/.venv-fotos/bin/python -m pytest catalogo/tests -q             # testes (todos)
```

- **Grupo:** produtos com a mesma peça+carro+lado+marca dividem a foto (`produtos.foto_grupo`).
- **Aprovação automática:** título do anúncio com peça e carro (e marca e medida quando houver),
  CLIP com o tipo da peça no top 3 e nada de lixo, OCR sem outra marca no rótulo. Constantes
  em `catalogo/fotos/verificar.py`.
- **Revisão do Agy:** diga a ele "Leia `catalogo/revisao/PROMPT_AGY.md` e execute". O contexto
  (o que é foto correta, glossário de siglas) está em `catalogo/revisao/CONTEXTO_AGY.md`.
- **Auditoria:** 3% das aprovações automáticas (100% no piloto) entram na fila como `auditoria`.
  Se o erro medido passar de 1% (com pelo menos 100 auditadas), pare o loop, aperte a regra
  (com teste) e refaça as aprovações automáticas do tipo de peça afetado.
- **Foto de tipo de peça:** só para produto sem marca, e sempre revisada.
- **Placeholder recorrente:** acrescente o SHA-1 do arquivo baixado em
  `catalogo/data/hashes_bloqueados.txt` (um por linha) e ele nunca mais é usado.
- **Siglas, carros, marcas e rótulos do CLIP:** `catalogo/fotos/dados/`. Cobertura medida em
  2026-10-05 (17.149 produtos): 100% com peça reconhecida, 85,7% com rótulo para o CLIP, 8.539
  grupos. Metas no teste `test_cobertura_no_catalogo_real`: ≥ 99%, ≥ 83% e ≤ 9.000.
````

- [ ] **Step 3: Commit**

```bash
git add catalogo/fotos/loop.sh catalogo/README.md
git commit -m "docs(fotos): loop de execucao e secao Fotos no README

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Piloto (operacional) e parada para o Isac

**Files:** nenhum código novo. Ajustes de regra, se houver, entram com teste nas Tasks 2/3 e um commit próprio.

- [ ] **Step 1: Suíte completa verde antes de tocar no banco real**

Run: `catalogo/.venv-fotos/bin/python -m pytest catalogo/tests -q`
Expected: tudo passa

- [ ] **Step 2: Backup do banco real**

```bash
catalogo/.venv-fotos/bin/python -c "from catalogo.fotos import banco; print(banco.backup('catalogo/data/catalogo.db', 'catalogo/data/backups'))"
```

Expected: imprime o caminho de um arquivo `catalogo/data/backups/catalogo_AAAAMMDD_HHMMSS_*.db`.

- [ ] **Step 3: Rodar o piloto**

Run: `catalogo/.venv-fotos/bin/python -m catalogo.fotos.executar --piloto 2>&1 | tee /tmp/piloto_fotos.log`
Expected: ~100 linhas `[i/N] aprovada|revisao|sem_foto ...` e o relatório JSON no fim. Anotar o tempo total.

- [ ] **Step 4: Auditar 100% das aprovações automáticas**

```bash
catalogo/.venv-fotos/bin/python -m catalogo.fotos.revisar --gerar
```

Abrir cada `catalogo/revisao/folhas/folha_NNN.png` (itens `[auditoria]`) e conferir as 4
regras (tipo, carro, lado, marca), olhando também o `.txt`. Registrar cada erro: descrição,
o que a foto mostra e qual sinal deixou passar.

- [ ] **Step 5: Critério**

- **Zero erro nas aprovações automáticas →** aplicar `0` nas auditorias
  (`revisar --decidir ID:0,... --por claude`) e seguir para o Step 6.
- **Algum erro →** aplicar `x` nos errados; ajustar a regra (constante em `verificar.py`,
  rótulo em `tipos_en.py`, sigla/carro/marca em `dados/`) com um teste novo que reproduza
  o caso; commit; `executar --refazer-piloto`; voltar ao Step 3.

- [ ] **Step 6: Reportar ao Isac e PARAR**

Relatório (página com as folhas, ou texto) contendo:
- números do piloto: % aprovada automaticamente, % revisão, % sem foto, tempo por grupo e
  projeção para ~8,5 mil grupos;
- erros encontrados na auditoria e o que foi ajustado (ou "zero erro");
- tamanho projetado da fila do Agy.

**Não iniciar `loop.sh` sem o aval do Isac.**
