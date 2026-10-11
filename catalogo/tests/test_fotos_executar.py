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
