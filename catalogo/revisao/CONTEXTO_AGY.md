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
4. **Ano.** Quando a folha diz `ano 2012 a 2014` (ou `ano 2010 em diante`, `ano até 2013`), o
   anúncio precisa ser de um ano dessa faixa. Corolla 2020 não serve para Corolla 12/14: é outra
   geração, e peças de lataria (grade, para-choque, farol, lanterna, retrovisor) mudam de formato.
   Se o anúncio não diz o ano e você não consegue reconhecer a geração pela foto, rejeite.
5. **Lado.** Quando diz `lado direito` ou `lado esquerdo`, o anúncio não pode ser do outro lado.
6. **Marca.** Quando diz `marca X`, a embalagem ou o título precisam ser dessa marca.
   Óleo Petronas com foto de óleo Mobil é ERRADO, mesmo sendo "óleo 15W40".
7. **Medida.** Em pneu, óleo, lâmpada e correia a medida faz parte do produto:
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
- `exige:` o que a foto precisa mostrar (tipo de peça + carro + ano + lado + marca);
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

## Erros que o robô já cometeu sozinho (piloto de 11/10/2026)

Estes passaram pela aprovação automática e só a auditoria pegou. Fique atento a eles:

- grade do Corolla 2020 num produto Corolla 12/14 (geração errada);
- bomba d'água da S10 4.3 V6 num produto S10 MWM diesel (motor errado);
- kit de 4 amortecedores, dianteiros e traseiros, num produto "amortecedor dianteiro";
- kit de correia com polias e tensor num produto que é só a correia;
- mangotes superior e inferior juntos num produto "mangote superior";
- foto com telefone, texto ou logotipo de outra loja por cima da peça.

Regra para kit: se o produto é UMA peça e a foto mostra essa peça junto com OUTRAS peças
diferentes, rejeite. Duas ou mais unidades da mesma peça (par de pastilhas, jogo de velas) pode.

## Erros que já vimos o robô encontrar

- foto de "imagem indisponível" com título de anúncio certo;
- óleo ou aditivo de outra marca;
- pneu do mesmo modelo, mas de outro aro;
- desenho técnico no lugar da foto;
- kit com peças a mais;
- peça de posição trocada (traseira no lugar de dianteira).
