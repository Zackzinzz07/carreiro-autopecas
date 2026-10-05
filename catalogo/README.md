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
4. Fotos (pipeline de imagens como no Agrocarreiro) e nomes mais legíveis (a descrição vem cortada em 45 caracteres do sistema de origem).
5. Decidir hospedagem: FastAPI não roda no Netlify estático da landing.
