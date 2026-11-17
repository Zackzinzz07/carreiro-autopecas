# Catálogo Carreiro Auto Peças

FastAPI + Jinja2 + SQLite (FTS5). Arquitetura no padrão do `Agrocarreiro/catalogo/`, visual da landing (tema escuro, Outfit/Inter).
O catálogo estático é gerado em `publico/` por `python -m catalogo.scripts.gerar_estatico` e publicado manualmente no Netlify (site `carreiro-autopecas`, não ligado ao GitHub). O FastAPI (`app.py`) continua sendo só para uso local.

## Rodar local

```bash
cd carreiro-autopecas                       # raiz do repo
python3 -m venv catalogo/.venv && catalogo/.venv/bin/pip install -r catalogo/requirements.txt
catalogo/.venv/bin/python -m catalogo.sync.importar --arquivo "../PRODUTOS E PREÇOS.xlsx"          # simula (relatório)
catalogo/.venv/bin/python -m catalogo.sync.importar --arquivo "../PRODUTOS E PREÇOS.xlsx" --gravar # grava em catalogo/data/catalogo.db
catalogo/.venv/bin/uvicorn catalogo.app:app --port 8000                                            # http://127.0.0.1:8000
catalogo/.venv/bin/python -m pytest catalogo/tests -q
```

## Geração estática e deploy (Netlify)

O catálogo estático é gerado em `publico/` e publicado manualmente no Netlify (site `carreiro-autopecas`, não ligado ao GitHub):

```bash
catalogo/.venv/bin/python -m catalogo.scripts.gerar_estatico # gera catálogo estático em publico/
cp index.html publico/ && rm -rf publico/assets && cp -r assets publico/   # landing + assets da raiz
rm -f publico/assets/image*.png                             # fotos de referência: não publicar (.gitignore)
npx netlify-cli deploy --prod --dir=publico --site f3408469-54f1-473d-b701-b85f27435652
```

O FastAPI (`app.py`) continua sendo só para uso local.

## O que já funciona

- Lista paginada (48/página), busca instantânea FTS5 por descrição, código, referência e EAN (prefixo, sem acento, todos os termos).
- Sinônimos de busca para abreviações da planilha (`amortecedor` acha `AMORT`, `dianteiro` acha `DT`/`DIANT`) — `SINONIMOS` em `db.py`.
- 12 categorias + filtro por "tipo de peça" (primeira palavra da descrição).
- **Cards deduplicados com preços**: o catálogo junta num card os códigos com a mesma descrição.
  - Preço igual em todos -> `'R$ 14,00'`.
  - Preços diferentes -> `'a partir de R$ X'` e cada código com o seu preço na lista (2.759 dos 2.848 cards com vários códigos têm preços diferentes).
  - Sem preço -> `'Consulte o preço'`.
  - Valores no formato `'R$ 1.234,56'`.
- Botão **Pedir no WhatsApp**: abre a escolha entre as 5 lojas (`lojas.py`) e monta o link `wa.me` com a peça e os códigos. A mensagem lista o código e o preço de cada um. Sem JS, cai na matriz (Poranga). A última loja escolhida fica destacada.

## O que a planilha atual (`PRODUTOS E PREÇOS.xlsx`) tem e não tem

Tem: `Código`, `Descrição`, `Pr. Venda` — 17.166 linhas, 17 marcadas `INATIVO` (ignoradas) → **17.149 ativos**. Preço em texto (ex.: `'27,00'`).

A planilha anterior (`PRODUTOS E PREÇOS v2.xlsx`) tinha `Cód Barras` e nenhum preço. A planilha atual não tem `Cód Barras`, mas quando a planilha não traz uma coluna opcional, o import mantém o valor que já está no banco (EAN/referência continuam os da planilha v2) em vez de apagar.

| Campo | Situação | Como está tratado |
|---|---|---|
| Preço | **Resolvido** | Coluna `Pr. Venda` aceita; exibido nos cards e no WhatsApp no formato `R$ 1.234,56`. Apenas 4 produtos sem preço ("Consulte o preço") |
| Cód Barras / EAN | **Preservado** | Mantido do banco (da planilha v2) quando a nova planilha omite a coluna |
| Categoria | Inferida | Inferida pela descrição (`categorias.py`, regras em ordem; ~7% cai em "Variados"). É heurística — revisar |
| Marca / aplicação | Opcional | Colunas existem, vazias; aceitas se a planilha trouxer `Marca` / `Aplicação` |
| Imagem | Em andamento | Coluna `imagem_url` pronta; pipeline de imagens em andamento (seção Fotos) |
| Estoque por loja | Não existe | As 5 lojas mostram o mesmo catálogo; disponibilidade é confirmada no WhatsApp |

`Cód Barras` (da planilha v2 / mantido no banco): 8/12/13/14 dígitos e diferente do código → `ean`; qualquer outro valor diferente do código → `referencia` (código alternativo, **significado a confirmar com o cliente**); igual ao código → ignorado.

## Planilha real: formato esperado

Primeira aba, primeira linha = cabeçalho (acento e caixa não importam).

| Coluna | Obrigatória | Uso |
|---|---|---|
| `Código` | sim | chave única do produto (texto: preserva zeros à esquerda) |
| `Descrição` | sim | nome; base da busca, da categoria e do agrupamento no card |
| `Pr. Venda` (ou `Preço`, `Preço Venda`, `Preço de Venda`, `Valor`, `Valor Venda`) | não | número ou texto como `'27,00'` ou `'1.234,56'` |
| `Cód Barras` | não | EAN ou código alternativo (se omitida, mantém o que já está no banco) |
| `Marca`, `Aplicação` | não | exibidos no card |

Regras do sync / importador:
- Descrição contendo a palavra `INATIVO` é ignorada.
- Reimportar atualiza os existentes e **desativa** (não apaga) quem sumiu da planilha.
- Omissão de colunas opcionais mantém os dados existentes no banco em vez de sobrescrever com vazio.
- O relatório do import lista produtos novos separados em:
  - **Dentro do dedupe**: descrição já existe num card (entra no card existente).
  - **Fora do dedupe**: descrição inédita (card novo).
  - Grava a lista em `catalogo/data/novos_produtos.csv`.
- Na planilha de nov/2026: 0 novos, 0 alterados de descrição, 0 sumiram; só 4 produtos sem preço.
- Sempre rode sem `--gravar` antes e leia o relatório.

## Pendências para virar catálogo completo

1. Confirmar com o cliente o que é `Cód Barras` quando difere do código.
2. ~~Preços~~ — **Resolvido**: integrado a partir de `../PRODUTOS E PREÇOS.xlsx` (`Pr. Venda`), com regras para preços múltiplos por card e no WhatsApp.
3. Revisar as categorias inferidas e o "Variados".
4. Fotos: pipeline pronto (seção "Fotos"); falta rodar o catálogo inteiro e a revisão do Agy. A descrição continua vindo cortada em 45 caracteres do sistema de origem.
5. Hospedagem: catálogo estático gerado em `publico/` e publicado manualmente no Netlify (`carreiro-autopecas`). FastAPI (`app.py`) continua sendo só para uso local.

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
nohup catalogo/fotos/loop.sh >> /tmp/fotos_carreiro.log 2>&1 &         # catálogo inteiro (dias)
catalogo/.venv-fotos/bin/python -m catalogo.fotos.revisar --gerar       # folhas para o Agy
catalogo/.venv-fotos/bin/python -m pytest catalogo/tests -q             # testes (todos)
```

- **Grupo:** produtos com a mesma peça+carro+ano+lado+marca dividem a foto (`produtos.foto_grupo`).
  O ano entrou na chave depois do piloto: sem ele, uma grade de Corolla 2020 foi parar no Corolla 12/14.
- **Aprovação automática:** título do anúncio com peça e carro (e marca e medida quando houver), de ano
  compatível, sem a posição/lado oposto, sem ser kit com peças a mais e sem telefone/propaganda de
  vendedor na imagem,
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
  2026-10-11 (17.149 produtos): 100% com peça reconhecida, 85,7% com rótulo para o CLIP, 10.607
  grupos. Metas no teste `test_cobertura_no_catalogo_real`: ≥ 99%, ≥ 83% e ≤ 11.500.
- **Conteúdo de terceiros:** as imagens vêm de sites desconhecidos. O download só aceita http(s)
  para endereço público (inclusive após redirecionamento), até 12 MB e 30 s, sem compressão; a
  imagem só é aberta se for JPEG/PNG/WebP com até 40 MP. Limites em `busca.py` e `imagem.py`.
