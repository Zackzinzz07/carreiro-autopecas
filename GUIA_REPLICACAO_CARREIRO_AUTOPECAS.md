# 📘 Guia de Replicação: Catálogo Digital Carreiro Auto Peças

> **Destinado a:** Qualquer IA ou desenvolvedor que for atuar no projeto **Carreiro Auto Peças**.  
> **Base de Referência:** Arquitetura do repositório `Agrocarreiro` (`/home/salati/Documentos/projetos/Agrocarreiro`).  
> **Repositório Destino:** `/home/salati/Documentos/projetos/carreiro autopeças/carreiro-autopecas` (remote `git@github.com:Zackzinzz07/carreiro-autopecas.git`).

---

## 1. Visão Geral e Contexto dos Projetos

O cliente possui duas marcas principais geridas pela família:
1. **Agrocarreiro** (Agropecuária & Pet Shop — 3 lojas no DF/GO) — **Projeto de referência 100% pronto e validado**.
2. **Carreiro Auto Peças** (Distribuidora de Peças Automotivas — 5 lojas no CE/PI) — **Projeto onde o catálogo deve ser implementado**.

### Estado Atual da Carreiro Auto Peças:
- **Landing Page:** Já está 100% pronta e no ar em `carreiro-autopecas.netlify.app` (`index.html` na raiz).
  - Tema: Escuro (`--bg-0: #06080d`), tipografia Outfit + Inter.
  - Possui animação de motor 4 cilindros em Canvas 2D, apresentação da empresa e cards das 5 lojas.
  - **ATENÇÃO: Não quebre ou altere a estrutura da landing page existente sem necessidade.**
- **Planilha Real de Estoque:** Já está salva na pasta pai:
  `/home/salati/Documentos/projetos/carreiro autopeças/PRODUTOS E PREÇOS v2.xlsx` (~635 KB).
- **Protótipo Visual do Catálogo:**
  `/home/salati/Documentos/projetos/carreiro autopeças/prototipo2.html`.
  - Este arquivo contém a referência visual exata (tema escuro) que combina com a landing page.

---

## 2. As 5 Lojas da Carreiro Auto Peças (Dados do Checkout WhatsApp)

Assim como fizemos no Agrocarreiro com o seletor de lojas no carrinho, o catálogo da Carreiro Auto Peças deve ter o seletor das **5 filiais da rede** (dados extraídos de `prototipo2.html` e `index.html`):

1. **Poranga - CE (Matriz):**
   - Endereço: Av. Dr. Epitácio de Pinho, Centro
   - WhatsApp: Verificar no `index.html` da landing page
2. **Pedro II - PI (Filial 1):**
   - Endereço: Av. Cel. Cordeiro, Centro
3. **Piripiri - PI (Filial 2):**
   - Endereço: Av. Aderson Alves Ferreira
4. **Campo Maior - PI (Filial 3):**
   - Endereço: Av. Santo Antônio, Centro
5. **José de Freitas - PI (Filial 4):**
   - Endereço: Av. Paulino Rocha, Centro

---

## 3. Diferença Crítica do Domínio: Auto Peças NÃO tem EAN

No Agrocarreiro, ~82% dos produtos tinham código de barras EAN válido (permitindo consulta na Bluesoft/Cosmos).  
**Em Auto Peças é diferente:**
- Os produtos raramente são buscados por código de barras.
- Os produtos possuem:
  - `Nome / Descrição` (ex: *Amortecedor Dianteiro Turbogás*)
  - `Marca / Fabricante` (ex: *Cofap, Nakata, Bosch, Fras-le, Mahle, Monroe, TRW, Magneti Marelli*)
  - `Código da Peça / Referência do Fabricante` (ex: *GP30123, HG31010, FDB1001*)
  - `Aplicação / Veículo` (ex: *Gol G5 / Voyage / Fox 1.0 1.6 2008 a 2014*)
- **Estratégia de Busca de Imagens:**
  - Buscar no DuckDuckGo / Bing Imagens usando a combinação: `"{fabricante} {codigo_referencia}"` ou `"{descricao} {fabricante} {aplicacao}"`.
  - Domínios automotivos confiáveis: Mercado Livre (`mlstatic.com`), Canal da Peça, Hipervarejo, Autoglass, AutoZone, Dpaschoal, PitStop, etc.

---

## 4. Arquitetura Padrão a Ser Copiada do Agrocarreiro

Copie a estrutura da pasta `catalogo/` do Agrocarreiro para dentro de `carreiro-autopecas/catalogo/`:

```text
carreiro-autopecas/
├── index.html                    # Landing page original (tema escuro)
├── assets/                       # Vídeos e imagens da landing
├── netlify.toml                  # Configuração de build e cache Netlify
├── catalogo/                     # Catálogo de peças
│   ├── config.py                 # Settings (whatsapp_loja, db_path, etc.)
│   ├── db.py                     # SQLite + Schema de produtos
│   ├── icones.py                 # Ícones SVG das categorias de auto peças
│   ├── whatsapp.py               # Formatador de links wa.me
│   ├── templates/
│   │   ├── index.html            # Catálogo estático/SSR com busca instantânea
│   │   └── _card_produto.html    # Card individual de peça
│   ├── static/
│   │   └── icons/                # Ícones SVG das categorias
│   └── scripts/
│       ├── importar_excel.py     # Parser para 'PRODUTOS E PREÇOS v2.xlsx'
│       ├── fetch_images.py       # Pipeline de busca de fotos com OCR
│       └── gerar_estatico.py     # Exporta site completo para dist/
└── dist/                         # Gerado pelo script (onde roda o Netlify)
    ├── index.html                # Landing page na raiz
    ├── catalogo/index.html       # Catálogo em /catalogo
    ├── produtos.json             # Busca rápida instantânea no cliente
    ├── images/                   # Fotos WebP dos produtos
    └── static/                   # Ícones e logo
```

---

## 5. Passo a Passo Recomendado para a Próxima IA

### Passo 1: Inspeção da Planilha de Estoque
Examinar a planilha `/home/salati/Documentos/projetos/carreiro autopeças/PRODUTOS E PREÇOS v2.xlsx`:
- Identificar as colunas: Código, Descrição, Fabricante/Marca, Aplicação, Preço de Venda, Categoria.
- Criar o script `catalogo/scripts/importar_excel.py` para carregar esses dados no SQLite (`catalogo/data/catalogo.db`).

### Passo 2: Estruturar o Banco de Dados (`db.py`)
Tabela `produtos`:
```sql
CREATE TABLE IF NOT EXISTS produtos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    id_sistema TEXT UNIQUE,
    descricao TEXT NOT NULL,
    categoria TEXT NOT NULL,
    fabricante TEXT,
    referencia TEXT,
    aplicacao TEXT,
    preco_venda REAL NOT NULL,
    unidade TEXT DEFAULT 'un',
    imagem_url TEXT DEFAULT '',
    ativo INTEGER DEFAULT 1
);
```

### Passo 3: Adaptar o Template (`catalogo/templates/index.html`)
- Utilizar o tema escuro (`--bg-0: #06080d`, `--accent: #e63946` ou amarelo/dourado automotivo) baseado em `prototipo2.html`.
- Manter o motor de busca instantânea no front-end via `produtos.json` (o mesmo algoritmo ultrarrápido do Agrocarreiro).
- Categorias sugeridas do setor:
  - ⚙️ Motor
  - 🔄 Câmbio / Transmissão
  - 🛞 Suspensão & Direção
  - 🛑 Freios
  - ⚡ Elétrica & Ignição
  - ⏱️ Distribuição / Correias
  - 🚗 Lataria & Cabine
  - 📦 Filtros & Óleos
  - 🧰 Variados & Ferramentas

### Passo 4: Implementar o Carrinho com Seletor das 5 Lojas
Replicar a lógica adicionada no Agrocarreiro em `catalogo/templates/index.html`:
- Dropdown no rodapé do carrinho com as 5 filiais da Carreiro Auto Peças (Poranga, Pedro II, Piripiri, Campo Maior, José de Freitas).
- Ao clicar em "Enviar Pedido", direcionar para o WhatsApp da unidade escolhida com o pedido já formatado.

### Passo 5: Compilador Estático (`gerar_estatico.py`)
- O script compila:
  1. A landing page existente (`index.html`) para `dist/index.html`.
  2. O catálogo para `dist/catalogo/index.html`.
  3. O `produtos.json` para `dist/produtos.json`.
  4. As imagens WebP para `dist/images/`.
- Permite publicar no Netlify via CLI (`npx netlify-cli deploy --prod --dir=dist`) ou arrastando em `app.netlify.com/drop`.

---

## 6. Comandos Úteis do Agrocarreiro para Consulta

- Gerar o site estático:
  ```bash
  python3 -m catalogo.scripts.gerar_estatico
  ```
- Publicar no Netlify:
  ```bash
  npx netlify-cli deploy --prod --dir=dist
  ```
- Verificar o banco de dados:
  ```bash
  sqlite3 catalogo/data/catalogo.db "SELECT count(*) FROM produtos WHERE ativo=1;"
  ```
- Ler o histórico e decisões de engenharia:
  Consulte o arquivo `CONTEXTO_AGY.md` na raiz do Agrocarreiro.
