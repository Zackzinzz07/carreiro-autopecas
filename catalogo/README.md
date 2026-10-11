# Catálogo Carreiro Auto Peças

FastAPI + Jinja2 + SQLite (FTS5). Arquitetura no padrão do `Agrocarreiro/catalogo/`, visual da landing (tema escuro, Outfit/Inter).
**Não é deploy** — roda local. A landing (`index.html`) não é tocada por nada aqui.

## Rodar local

```bash
cd carreiro-autopecas                       # raiz do repo
python3 -m venv catalogo/.venv && catalogo/.venv/bin/pip install -r catalogo/requirements.txt
catalogo/.venv/bin/python -m catalogo.sync.importar --arquivo "../PRODUTOS E PREÇOS v2.xlsx"          # simula (relatório)
catalogo/.venv/bin/python -m catalogo.sync.importar --arquivo "../PRODUTOS E PREÇOS v2.xlsx" --gravar # grava em catalogo/data/catalogo.db
catalogo/.venv/bin/uvicorn catalogo.app:app --port 8000                                               # http://127.0.0.1:8000
catalogo/.venv/bin/python -m pytest catalogo/tests -q
```

## O que já funciona

- Lista paginada (48/página), busca instantânea FTS5 por descrição, código, referência e EAN (prefixo, sem acento, todos os termos).
- Sinônimos de busca para abreviações da planilha (`amortecedor` acha `AMORT`, `dianteiro` acha `DT`/`DIANT`) — `SINONIMOS` em `db.py`.
- 12 categorias + filtro por "tipo de peça" (primeira palavra da descrição).
- Botão **Pedir no WhatsApp**: abre a escolha entre as 5 lojas (`lojas.py`) e monta o link `wa.me` com a peça e o código. Sem JS, cai na matriz (Poranga). A última loja escolhida fica destacada.

## O que a planilha atual (`PRODUTOS E PREÇOS v2.xlsx`) tem e não tem

Tem: `Código`, `Descrição`, `Cód Barras` — 17.166 linhas, 17 marcadas `INATIVO` (ignoradas) → **17.149 ativos**.

Não tem, e por isso o catálogo mostra "Consulte o preço" e ícone no lugar de foto:

| Falta | Como está tratado |
|---|---|
| Preço | coluna `preco` existe no banco e aparece na UI/WhatsApp assim que a planilha trouxer `Preço` |
| Categoria | **inferida** pela descrição (`categorias.py`, regras em ordem; ~7% cai em "Variados"). É heurística — revisar |
| Marca / aplicação | colunas existem, vazias; aceitas se a planilha trouxer `Marca` / `Aplicação` |
| Imagem | coluna `imagem_url` pronta; sem pipeline de imagens ainda |
| Estoque por loja | não existe: as 5 lojas mostram o mesmo catálogo; disponibilidade é confirmada no WhatsApp |

`Cód Barras` é tratado assim: 8/12/13/14 dígitos e diferente do código → `ean`; qualquer outro valor diferente do código → `referencia` (código alternativo, **significado a confirmar com o cliente**); igual ao código → ignorado.

## Planilha real: formato esperado

Primeira aba, primeira linha = cabeçalho (acento e caixa não importam).

| Coluna | Obrigatória | Uso |
|---|---|---|
| `Código` | sim | chave única do produto (texto: preserva zeros à esquerda) |
| `Descrição` | sim | nome; base da busca e da categoria |
| `Cód Barras` | não | EAN ou código alternativo (ver acima) |
| `Preço` | não | número ou `1.234,56` |
| `Marca`, `Aplicação` | não | exibidos no card |

Descrição contendo a palavra `INATIVO` é ignorada. Reimportar atualiza os existentes e **desativa** (não apaga) quem sumiu da planilha. Sempre rode sem `--gravar` antes e leia o relatório.

## Pendências para virar catálogo completo

1. Confirmar com o cliente o que é `Cód Barras` quando difere do código.
2. Preços (planilha ou outra fonte). Sem isso é catálogo de consulta, não de venda.
3. Revisar as categorias inferidas e o "Variados".
4. Fotos: pipeline pronto (seção "Fotos"); falta rodar o catálogo inteiro e a revisão do Agy. A descrição continua vindo cortada em 45 caracteres do sistema de origem.
5. Decidir hospedagem: FastAPI não roda no Netlify estático da landing.

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
  CLIP com o tipo da peça no top 3 e nada de lixo, e, se o produto tem marca, o OCR lendo essa
  marca no rótulo (pneu e câmara dispensam: a marca fica na lateral). Constantes em
  `catalogo/fotos/verificar.py`.
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
- **Conteúdo de terceiros:** as imagens vêm de sites desconhecidos. O download só aceita http(s)
  para endereço público (inclusive após redirecionamento), até 12 MB e 30 s, sem compressão; a
  imagem só é aberta se for JPEG/PNG/WebP com até 40 MP. Limites em `busca.py` e `imagem.py`.
