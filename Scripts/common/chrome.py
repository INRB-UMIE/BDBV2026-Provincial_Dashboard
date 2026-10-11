"""Header / tabs / footer shared by every page (the dashboard "chrome")."""

from __future__ import annotations

import html

from common.paths import ASSETS_DIRNAME, LOGOS_PNG, PAGE_FILENAMES
from common.payload import payload_script

LEAFLET_CSS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
LEAFLET_JS = "https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"

TABS = [
    ("overview", "Situation actuelle"),
    ("summary", "Synthèse"),
    ("zones", "Zones de santé"),
    ("trends", "Tendances"),
    ("alerts", "Alertes et contacts"),
    ("quality", "Qualité des données"),
    ("pillars", "Piliers et fiabilité"),
    ("kpis", "KPI Surv. · Labo · PCI"),
    ("week", "Résumé de la semaine"),
]
# libellés courts, affichés quand la barre d'onglets manque de place (voir dashboard.css)
TABS_COURTS = {"overview": "Situation", "zones": "Zones", "alerts": "Alertes", "quality": "Qualité",
               "pillars": "Piliers", "kpis": "KPI piliers", "week": "Semaine"}

def _logo_tag() -> str:
    """Logos are copied to output/assets/ by build_dashboard.py (see LOGOS_PNG)."""
    if not LOGOS_PNG.exists():
        return ""
    return (f'<img class="logos" src="{ASSETS_DIRNAME}/{LOGOS_PNG.name}" '
            f'alt="INRB, INSP, UMIE, INOHA, Africa CDC, OMS">')


def render_page(view_id: str, title: str, body: str, payload: dict, province: str | None = None,
                with_map: bool = False) -> str:
    meta = payload.get("meta", {})
    # l'extraction des présentations n'est embarquée que là où elle sert (taille des pages)
    if view_id in ("pillars", "kpis", "week"):
        page_payload = payload
    elif province:
        page_payload = {**payload, "extraction": [r for r in payload.get("extraction", []) if r.get("province") == province]}
    else:
        page_payload = {**payload, "extraction": []}
    tab_links = []
    for vid, label in TABS:
        active = vid == view_id
        cls = "tab active" if active else "tab"
        current = ' aria-current="page"' if active else ""
        court = TABS_COURTS.get(vid)
        texte = (f'<span class="t-long">{html.escape(label)}</span><span class="t-short" aria-hidden="true">{html.escape(court)}</span>'
                 if court else html.escape(label))
        tab_links.append(f'<a class="{cls}" href="{PAGE_FILENAMES[vid]}" data-view="{vid}" title="{html.escape(label)}"{current}>'
                         f'{texte}</a>')
    tabs = '<div class="tab-links">\n' + "\n".join(tab_links) + "\n</div>"
    province_attr = f' data-province="{html.escape(province)}"' if province else ""
    # Same Leaflet build and CDN as BDBV2026-Epidemic_Dashboard (unpkg 1.9.4). Scripts
    # are `defer`, so they run in order: leaflet -> geo -> engine. If Leaflet cannot
    # load (offline), engine.js falls back to its built-in SVG map.
    leaflet_css = f'<link rel="stylesheet" href="{LEAFLET_CSS}">\n' if with_map else ""
    geo_tag = (f'<script defer src="{LEAFLET_JS}"></script>\n'
               f'<script defer src="{ASSETS_DIRNAME}/geo.js"></script>\n') if with_map else ""
    commit = html.escape(meta.get("data_commit") or "")
    repo = html.escape(meta.get("data_repo") or "")
    built = html.escape((meta.get("data_built_at") or "")[:16].replace("T", " "))
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{html.escape(title)} · MVE Bundibugyo 2026 — Présentations provinciales</title>
{leaflet_css}<link rel="stylesheet" href="{ASSETS_DIRNAME}/dashboard.css">
{payload_script(page_payload)}
{geo_tag}<script defer src="{ASSETS_DIRNAME}/engine.js"></script>
</head>
<body data-view="{view_id}"{province_attr}>
<header class="site-header">
  <div class="brand">
    {_logo_tag()}
    <div class="titles">
      <h1>MVE Bundibugyo 2026 — Présentations provinciales</h1>
      <p class="subtitle">Chiffres extraits automatiquement des présentations quotidiennes des DPS</p>
    </div>
  </div>
  <div id="tracker" aria-live="polite"></div>

</header>
<nav class="tabs" aria-label="Pages du tableau de bord">
{tabs}
<div class="nav-controls">
  <div class="date-picker">
    <label for="date-select">Date du rapport</label>
    <select id="date-select" aria-label="Date du rapport"></select>
  </div>
</div>
</nav>
<main id="main">
<h2 class="page-title">{html.escape(title)}</h2>
{body}
</main>
<footer class="site-footer">
  <p><strong>Données préliminaires et confidentielles.</strong> Chiffres tels que présentés par les DPS, sans correction ;
  les incohérences repérées sont listées dans « Qualité des données ». Ne pas diffuser.</p>
  <p class="build-info">Source : <code>{repo}</code>{f" @ <code>{commit}</code>" if commit else ""}{f" · build des données {built} UTC" if built else ""}
  · INRB · INSP · UMIE · INOHA</p>
</footer>
</body>
</html>
"""
