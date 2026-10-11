from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent


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
