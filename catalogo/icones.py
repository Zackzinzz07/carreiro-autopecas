"""Ícones SVG (24x24, traço) por categoria — usados no lugar de foto enquanto não há imagens."""
from __future__ import annotations

_ICONES: dict[str, str] = {
    "Motor": '<rect x="4" y="8" width="14" height="9" rx="1.5"/><path d="M8 8V5h6v3M18 11h3v3h-3M4 12H2M9 17v3M13 17v3"/>',
    "Câmbio e Embreagem": '<circle cx="12" cy="12" r="3"/><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1"/>',
    "Suspensão e Direção": '<path d="M9 3h6M12 3v3M9 6h6l-1 3 1 3-1 3 1 3H9l1-3-1-3 1-3z"/>',
    "Freios": '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="2.5"/><path d="M12 4v2M12 18v2M4 12h2M18 12h2"/>',
    "Elétrica e Iluminação": '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
    "Distribuição e Correias": '<circle cx="7" cy="12" r="3.5"/><circle cx="17" cy="12" r="2.5"/><path d="M7 8.5h10M7 15.5h10"/>',
    "Arrefecimento": '<path d="M12 3s5 6 5 10a5 5 0 0 1-10 0c0-4 5-10 5-10z"/>',
    "Filtros": '<path d="M4 5h16l-6 8v6l-4-2v-4z"/>',
    "Cabine e Carroceria": '<path d="M3 15v-3l2-5h14l2 5v3zM3 15v2h3v-2M18 15v2h3v-2"/><circle cx="7.5" cy="13" r=".8"/><circle cx="16.5" cy="13" r=".8"/>',
    "Pneus e Rodas": '<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/><path d="M12 3v6M12 15v6M3 12h6M15 12h6"/>',
    "Lubrificantes e Químicos": '<path d="M8 3h8M9 3v4l-3 4v9a1 1 0 0 0 1 1h10a1 1 0 0 0 1-1v-9l-3-4V3M7 13h10"/>',
    "Variados": '<path d="M12 3 4 7v10l8 4 8-4V7zM4 7l8 4 8-4M12 11v10"/>',
}


def icone_svg(categoria: str) -> str:
    corpo = _ICONES.get(categoria, _ICONES["Variados"])
    return (
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" '
        f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{corpo}</svg>'
    )
