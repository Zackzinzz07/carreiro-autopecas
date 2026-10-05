# Fotos do catálogo Carreiro Auto Peças — design

Data: 2026-10-05 · Status: aguardando revisão do Isac

## 1. Objetivo e definição de "correto"

Dar foto aos 17.149 produtos ativos do catálogo (`catalogo/`) **sem publicar foto errada**.
Na dúvida, o produto fica sem foto (ícone da categoria, como hoje).

A planilha não tem EAN nem código do fabricante, só a descrição abreviada
(`PASTILHA FREIO DT AGILE/CELTA/CORSA/PRISMA`). Por isso ninguém consegue garantir que a foto
seja a unidade exata da prateleira. **"Correto" neste projeto quer dizer:**

1. **tipo de peça** certo (pastilha de freio dianteira, não traseira nem disco);
2. **carro** certo quando a descrição cita um (foto de anúncio para Agile/Celta/Corsa);
3. **lado** certo quando a descrição diz LD/LE (o anúncio não pode dizer o lado oposto);
4. **marca** certa quando a descrição cita uma (óleo Petronas só com foto Petronas).

Toda foto exibida leva o selo **"Imagem ilustrativa"**.

Decisões do Isac (2026-10-05):
- Marca: só a marca correta; sem confirmação, sem foto.
- Verificação **local e gratuita** (CLIP + OCR), sem API paga.
- A revisão do que não for aprovado automaticamente é feita pelo **Agy**, a partir das
  instruções em `catalogo/revisao/`.

## 2. Evidência (spike de 2026-10-05, amostra de 36 produtos, 3 por categoria)

| Medida | Resultado |
|---|---|
| Busca DuckDuckGo Imagens com descrição expandida: 1ª imagem correta | 30/36 (83%) |
| Pelo menos uma imagem correta entre as 4 primeiras | 35/36 |
| CLIP zero-shot: imagens ruins (placeholder, desenho, peça errada) fora do top 3 | **10/10** |
| CLIP zero-shot: imagens boas com o tipo certo em 1º / no top 3 | 54% / 79% |
| OCR: marca lida quando visível no rótulo (Petronas, Bosch) | sim (com miniatura de 230 px) |
| OCR: marca errada (Motorlub no lugar de Crachi) passou como certa | nunca |
| Buscas distintas para o catálogo inteiro (produtos agrupados por peça+carro) | 8.132 |

Falhas observadas: placeholder "imagem indisponível" (5×), marca diferente em óleo (2 produtos),
desenho técnico, foto de caixa, kit com peças a mais. O CLIP vai bem em peças comuns
(pneu, filtro, óleo, tambor) e mal em peças raras (bobina de campo, coifa): essas caem na revisão.

## 3. Visão geral do fluxo

```
produtos ──normalizar──▶ grupo (peça+carro+lado+marca) ──buscar──▶ até 12 candidatas
   ▲                                                                   │ baixar, validar, WebP
   │                                                                   ▼
imagem_url ◀── aprovado ◀── decisão ◀── verificar (texto + CLIP + OCR) por candidata
                              │
                              ├─ alta em todos os critérios ─▶ aprovada automaticamente (3% vão para auditoria)
                              ├─ alguma candidata plausível ─▶ fila de revisão do Agy (até 4 candidatas)
                              └─ nada plausível ─────────────▶ sem foto (nova tentativa com consulta alternativa)
```

A unidade de trabalho é o **grupo**, não o produto: todos os produtos com a mesma chave
(peça+carro+lado+marca) recebem a mesma foto. Isso reduz 17 mil buscas para ~8 mil e faz
cada decisão de revisão valer para vários produtos.

## 4. Componentes

Novo pacote `catalogo/fotos/`. Cada módulo tem uma responsabilidade e é testável sozinho.

| Arquivo | Responsabilidade |
|---|---|
| `fotos/dados/siglas.py` | Dicionário sigla → palavra (`AMORT`→amortecedor, `CX DIR`→caixa direção…). ~300 siglas, montado pela frequência real na planilha. |
| `fotos/dados/veiculos.py` | Modelos de carro/caminhão e montadoras, extraídos da planilha e revisados. Marca o início da "aplicação" na descrição. |
| `fotos/dados/marcas.py` | Marcas que aparecem nas descrições (MOBIL, PETRONAS, BOSCH, NGK, COFAP, TECFIL, OVATION…). |
| `fotos/dados/tipos_en.py` | Nome em inglês do tipo de peça para o CLIP (`pastilha freio`→"brake pad"). Casamento pelo prefixo mais longo da peça expandida. Tipo sem rótulo não tem aprovação automática: vai para a revisão. |
| `fotos/normalizar.py` | Descrição → `Chave(peca, veiculo, lado, marca)` + consultas de busca (principal e alternativa). Função pura. |
| `fotos/busca.py` | DuckDuckGo Imagens (`ddgs`, região br-pt), bloqueio de domínios, pausa e backoff, download com timeout. |
| `fotos/imagem.py` | Validação (tamanho mínimo, proporção, placeholder por hash e heurística), conversão para WebP 400px. Adaptado de `Agrocarreiro/catalogo/imagens.py`. |
| `fotos/verificar.py` | Sinais por candidata (texto do título, CLIP zero-shot, OCR) e **regra de decisão**. A regra é uma função pura sobre os sinais, testável sem rodar modelos. |
| `fotos/banco.py` | Tabelas de grupos, candidatas e revisão; aprovação propaga `produtos.imagem_url`; backup antes de decisões. |
| `fotos/executar.py` | CLI que processa grupos pendentes em lotes, retomável (`--limite`, `--piloto`, `--grupos`). |
| `fotos/revisar.py` | Gera as folhas de revisão para o Agy e aplica decisões (`--decidir`). |
| `fotos/auditar.py` | Sorteia 3% das aprovações automáticas para a folha de auditoria e aplica o resultado. |
| `revisao/INSTRUCOES_AGY.md` | Tarefa do Agy (versionado). As folhas geradas ficam em `revisao/folhas/` (fora do git). |

### 4.1 Normalização

`PASTILHA FREIO DT AGILE/CELTA/CORSA/PRISMA`
→ peça `pastilha freio dianteiro`, carro `agile`, lado —, marca —
→ consulta `pastilha freio dianteiro agile`.

- A peça vai do início até o primeiro veículo ou primeiro token com número.
- `C/` e `S/` viram "com"/"sem"; "com"/"sem" soltos no fim são descartados.
- O carro considerado é o primeiro modelo citado.
- LD/LE viram "lado direito/esquerdo" e entram na consulta.
- Sem carro (lâmpada, óleo, pneu, fusível): a consulta é a descrição inteira expandida, porque
  medida, especificação e marca são o que identifica o item.
- Consulta alternativa (2ª tentativa): peça + segundo carro citado, ou só a peça.

### 4.2 Sinais por candidata

- **Texto:** palavras-núcleo da peça no título do anúncio (com tolerância a plural, gênero e
  acento), carro no título, marca no título, lado oposto no título.
- **CLIP zero-shot** (`ViT-B-32-quickgelu`, pesos já em `/mnt/dados/cache/open_clip`): a imagem é
  comparada com "a product photo of a {tipo}" para todos os tipos de `tipos_en.py`, mais 5 classes
  de lixo (carro, desenho técnico, placeholder, caixa, banner). O sinal é a posição do tipo
  esperado e se o 1º lugar é lixo.
- **OCR** (`easyocr`, pt+en, `quantize=False` porque a máquina só tem AVX), na imagem original:
  marca esperada lida (com comparação aproximada ≥ 0,72, como no Agrocarreiro) ou **outra marca
  conhecida** lida. Só roda quando o produto tem marca.

### 4.3 Regra de decisão

Uma candidata é **aprovada automaticamente** só se cumprir todos os itens abaixo:

1. Imagem válida, domínio não bloqueado, hash fora da lista de placeholders.
2. CLIP: 1º lugar não é classe de lixo **e** o tipo esperado está no top 3.
3. Título contém as palavras-núcleo da peça **e**, se houver, o carro.
4. Se o produto tem lado: o título não cita o lado oposto.
5. Se o produto tem marca: a marca está no título **e** o OCR não leu outra marca conhecida.

Entre candidatas aprovadas, vence a de maior pontuação (desempate: domínio de loja de peças,
depois fundo branco).

**Vai para a revisão do Agy** quando nenhuma candidata passa, mas pelo menos uma não foi
descartada como lixo pelo CLIP. A fila leva até 4 candidatas, ordenadas pela pontuação, com o
motivo da reprovação automática.

**Fica sem foto** quando todas são lixo ou não há resultado. O grupo tenta a consulta
alternativa uma vez. Depois disso, fica registrado como `sem_foto` e não volta para a fila
automática.

Os limiares (top 3, pontuação) ficam em constantes no topo de `verificar.py`. O piloto
(seção 8) é o que os calibra.

### 4.4 Foto por tipo de peça (reserva)

Só para produtos **sem marca** cujo grupo terminou `sem_foto` ou foi rejeitado na revisão:

- Um grupo especial por tipo (`TIPO:pastilha freio dianteiro`), buscado sem carro.
- **Nunca é aprovado automaticamente:** toda foto de tipo passa pela revisão do Agy.
- Produtos com marca nunca usam foto de tipo.

## 5. Banco de dados

Tabelas novas em `catalogo/data/catalogo.db`, criadas por `fotos/banco.py`. As existentes não mudam.

```sql
ALTER TABLE produtos ADD COLUMN foto_grupo TEXT NOT NULL DEFAULT '';  -- chave do grupo

CREATE TABLE foto_grupos (
  chave TEXT PRIMARY KEY,          -- 'pastilha freio dianteiro|agile||'  ou 'TIPO:...'
  consulta TEXT NOT NULL, consulta_alt TEXT NOT NULL DEFAULT '',
  tipo_en TEXT NOT NULL DEFAULT '', marca TEXT NOT NULL DEFAULT '', lado TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'pendente',  -- pendente|aprovada|revisao|sem_foto|rejeitada
  origem TEXT NOT NULL DEFAULT '',          -- auto|agy|auditoria
  arquivo TEXT NOT NULL DEFAULT '',         -- fotos/<sha1>.webp
  url_origem TEXT NOT NULL DEFAULT '', titulo_origem TEXT NOT NULL DEFAULT '',
  tentativas INTEGER NOT NULL DEFAULT 0, atualizado_em TEXT NOT NULL
);

CREATE TABLE foto_candidatas (
  id INTEGER PRIMARY KEY, chave TEXT NOT NULL REFERENCES foto_grupos(chave),
  arquivo TEXT NOT NULL, url TEXT NOT NULL, titulo TEXT NOT NULL, dominio TEXT NOT NULL,
  clip_rank INTEGER, clip_top TEXT, ocr_texto TEXT, pontuacao INTEGER NOT NULL,
  aprovada_auto INTEGER NOT NULL, motivo TEXT NOT NULL
);

CREATE TABLE foto_revisao (
  id INTEGER PRIMARY KEY, chave TEXT NOT NULL REFERENCES foto_grupos(chave),
  tipo TEXT NOT NULL,                -- revisao|auditoria
  status TEXT NOT NULL DEFAULT 'pendente',  -- pendente|aprovada|rejeitada|obsoleta
  candidata_escolhida INTEGER, decidido_por TEXT, criado_em TEXT NOT NULL, decidido_em TEXT
);
```

- Aprovar um grupo grava `foto_grupos.arquivo` e copia `imagem_url = '/fotos/<arquivo>'` para
  todos os produtos com aquele `foto_grupo`.
- Rejeitar na auditoria desfaz isso.
- Reimportar a planilha recalcula `foto_grupo` e preserva as aprovações (chave estável).
- Fotos em `catalogo/data/fotos/` (fora do git). ~8 mil × ~30 KB ≈ 250 MB. Candidatas em
  `catalogo/data/fotos_candidatas/`, apagadas quando o grupo é decidido.

## 6. Revisão pelo Agy

O `catalogo/revisao/INSTRUCOES_AGY.md` segue o modelo que funcionou no Agrocarreiro
(`Agrocarreiro/catalogo/data_teste/tarefa_agy_revisao.md`):

1. `python -m catalogo.fotos.revisar --gerar` cria `revisao/folhas/fila_NNN.html`. Cada folha
   tem 20 grupos; cada grupo mostra a descrição original, a expansão, a marca/lado exigidos e
   até 4 candidatas numeradas, com o título do anúncio.
2. O Agy olha as imagens e decide por grupo: o número da candidata correta, ou `x` se nenhuma
   serve.
3. Aplica com `python -m catalogo.fotos.revisar --decidir 812:2,813:x,814:0`. O script faz
   backup do banco antes, valida os ids e registra `decidido_por='agy'`.
4. Critérios escritos para ele, na ordem: tipo de peça → carro → lado → marca. **Na dúvida,
   `x`.** Rejeitar também desenho técnico, foto só do carro, caixa sem a peça, kit com itens
   que o produto não inclui, marca d'água grande e banner.
5. Limites: não editar código, não mexer em git, não editar o banco direto, não interferir no
   processo de busca em andamento.
6. Ao final, ele relata contagens e padrões de erro recorrentes.

A auditoria usa as mesmas folhas, com `tipo=auditoria` e uma única candidata (a aprovada
automaticamente).

## 7. Catálogo (UI)

- `templates/_card_produto.html`: com `imagem_url`, mostra `<img loading="lazy">` (proporção
  fixa, `object-fit: contain`, fundo claro) e o selo "Imagem ilustrativa". Sem foto, continua o
  ícone da categoria.
- `app.py`: monta `/fotos` como estático a partir de `catalogo/data/fotos/`.
- Nada muda na landing (`index.html`).

## 8. Execução e piloto

1. **Piloto** (`executar.py --piloto`): 100 produtos fixos (seed 42, estratificados pelas 12
   categorias), processados de ponta a ponta. Todas as aprovações automáticas do piloto são
   auditadas (por mim e numa página para o Isac).
   - **Critério para seguir: zero erros nas aprovações automáticas.** Se houver algum, aperto
     a regra e repito o piloto.
   - O piloto também mede: % aprovado automaticamente, % para revisão, % sem foto e tempo por
     grupo.
2. **Execução completa:** `catalogo/fotos/loop.sh` chama `executar.py --limite 100` em ciclo,
   com pausa de ~3 s entre buscas e backoff em bloqueio. Estimativa: 12 a 24 horas para ~8 mil
   grupos. Pode ser interrompido e retomado.
3. **Auditoria contínua:** 3% das aprovações automáticas vão para a fila de auditoria. Se o
   erro medido passar de 1% (amostra mínima de 100), paro, aperto a regra e reprocesso as
   aprovações automáticas do tipo de peça afetado.

## 9. Testes

- `normalizar`: tabela de ~40 descrições reais → chave e consulta esperadas (inclui sem carro,
  com marca, LD/LE, `C/` e `S/`, descrição cortada em 45 caracteres).
- Cobertura dos dicionários, medida contra o banco real: % de ocorrências de token com sigla
  conhecida e % de produtos com rótulo em inglês. As metas e os números ficam registrados no
  README.
- `verificar.decidir`: sinais injetados (sem rodar modelos), cobrindo cada regra da 4.3,
  especialmente marca errada, lado oposto e lixo em 1º lugar.
- `imagem`: placeholder, imagem pequena, proporção extrema, conversão WebP.
- `banco`: aprovação propaga `imagem_url`; rejeição na auditoria desfaz; reimportação preserva;
  backup antes de decidir.
- `revisar`: parse de `--decidir`, ids inválidos, folha gerada contém os grupos pendentes.
- Card: renderiza foto + selo quando há `imagem_url`, ícone quando não há.
- Rede e modelos ficam fora dos testes unitários. `busca` e os modelos são testados no piloto.

## 10. Dependências

`ddgs`, `pillow`, `open_clip_torch`, `torch` (CPU), `easyocr`, todos já usados no venv do
Agrocarreiro. Os pesos ficam em `/mnt/dados/cache`, porque o disco principal tem pouco espaço.
Vão para `catalogo/requirements-fotos.txt`, separados, para o catálogo web não carregar torch.

## 11. Fora do escopo

Deploy e exportação estática do catálogo, API paga de visão, preços, revisão das categorias
inferidas, estoque por loja.

## 12. Riscos

| Risco | Mitigação |
|---|---|
| DuckDuckGo limitar as requisições | pausa entre buscas, backoff, retomada; piloto mede a taxa |
| Fila do Agy maior que o esperado (CLIP fraco em peças raras) | agrupamento reduz a fila; folhas de 20 grupos; o piloto mede o volume |
| Foto errada aprovada automaticamente | regra conjuntiva (todos os sinais), piloto com zero erro, auditoria contínua de 3% |
| Anúncio com título certo e foto de outra coisa | CLIP rejeita lixo e tipo errado; auditoria |
| Hotlink/URL da origem expirar | a foto é baixada e servida localmente; a URL fica só como registro |
