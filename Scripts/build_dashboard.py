#!/usr/bin/env python3
"""
Build the provincial-presentations dashboard as static HTML pages from
BDBV2026-Provincial_Reports' build/ (and qa/qa_log.csv).

Same structure as BDBV2026-Epidemic_Dashboard/Scripts/build_dashboard.py:

  1. Load all inputs and build the one shared JSON payload (common/payload.py).
  2. Write the shared static assets once: assets/dashboard.css (base +
     optional Data/Branding/dashboard-theme.css) and assets/engine.js.
  3. Call each page module in Scripts/pages/ and write output/<page>.html.

Usage
-----
    python Scripts/build_dashboard.py

Inputs (env overrides):
    BUILD_DIR   default ../BDBV2026-Provincial_Reports/build
    QA_LOG      default <BUILD_DIR>/../qa/qa_log.csv
    EXTRACTION_DIR default ../BDBV2026-Provincial_Reports/data/presentations
    DATA_ROOT   default ./Data   (branding)

Layout
------
    output/
    ├── index.html             Situation actuelle (carte plein écran, comme l'Epidemic Dashboard)
    ├── synthese.html          Synthèse (indicateurs, graphiques, tableau par province)
    ├── zones.html             Zones de santé
    ├── tendances.html         Tendances
    ├── alertes-contacts.html  Alertes et contacts
    ├── qualite.html           Qualité des données
    ├── piliers.html           Piliers et fiabilité (extraction des présentations : coordination,
    │                          piliers, points saillants, défis, fiabilité des 3 méthodes, contrôles)
    ├── province-<slug>.html   Résumé d'une province (une page par province)
    └── assets/
        ├── dashboard.css
        ├── engine.js
        └── geo.js             zones + contours de provinces (shapefile de BDBV2026-Data)

Missing inputs are tolerated: panels show an empty state and a warning is
printed.
"""

from __future__ import annotations

import hashlib
import json

from common.geo import build_geo
from common.paths import ASSETS_DIRNAME, GEO_SOURCE, LOGOS_PNG, OUTPUT_DIR, PAGE_FILENAMES, SCRIPT_DIR
from common.payload import build_shared_payload
from common.theme import load_theme_css
from pages import alerts_contacts, kpis, overview, pillars, province, quality, summary, trends, week, zones

PAGE_MODULES = [overview, summary, zones, trends, alerts_contacts, quality, pillars, kpis, week]


def _write_shared_assets(assets_dir) -> tuple[int, int]:
    base_css = (SCRIPT_DIR / "assets" / "dashboard.css").read_text(encoding="utf-8")
    theme_css = load_theme_css()
    css = base_css if not theme_css else f"{base_css}\n\n/* --- theme overrides --- */\n{theme_css}\n"
    (assets_dir / "dashboard.css").write_text(css, encoding="utf-8")
    engine_js = (SCRIPT_DIR / "assets" / "engine.js").read_text(encoding="utf-8")
    (assets_dir / "engine.js").write_text(engine_js, encoding="utf-8")
    if LOGOS_PNG.exists():
        (assets_dir / LOGOS_PNG.name).write_bytes(LOGOS_PNG.read_bytes())
    return len(css.encode("utf-8")), len(engine_js.encode("utf-8"))


def _geo_cache_key(provinces: set[str]) -> str:
    """Changes whenever the shapefile, the province set or the geometry code changes."""
    h = hashlib.sha256()
    for f in sorted(GEO_SOURCE.parent.glob(GEO_SOURCE.stem + ".*")):
        if f.suffix.lower() in (".shp", ".dbf", ".geojson", ".json"):
            h.update(f.read_bytes())
    h.update(json.dumps(sorted(provinces)).encode())
    for code in ("geo.py", "shapefile_reader.py"):
        h.update((SCRIPT_DIR / "common" / code).read_bytes())
    return h.hexdigest()[:16]


def _write_geo(assets_dir, provinces: set[str]) -> int:
    """assets/geo.js: zone polygons (provinces in the data) + every province outline.

    Built from BDBV2026-Data's shapefile (~4 M vertices, ~40 s), so the result
    is cached: the first line of geo.js carries a key of its inputs and the
    file is reused as long as nothing changed.
    """
    out = assets_dir / "geo.js"
    if not GEO_SOURCE.exists():
        print(f"  WARNING: {GEO_SOURCE} not found; maps will show 'carte indisponible' "
              f"(clone BDBV2026-Data next to this repo or set GEO_SOURCE)")
        out.write_text("window.GEO=null;\n", encoding="utf-8")
        return 0
    key = _geo_cache_key(provinces)
    header = f"/* geo-cache-key: {key} source: {GEO_SOURCE.name} */\n"
    if out.exists():
        with out.open(encoding="utf-8") as f:
            if f.readline() == header:
                print(f"  geo.js up to date ({GEO_SOURCE.name}, key {key}); reused")
                return out.stat().st_size
    print(f"  building map geometry from {GEO_SOURCE} …")
    geo = build_geo(GEO_SOURCE, provinces)
    js = header + "window.GEO=" + json.dumps(geo, ensure_ascii=False, separators=(",", ":")) + ";\n"
    out.write_text(js, encoding="utf-8")
    print(f"  wrote {out} ({len(js) / 1e6:.2f} MB: {len(geo['zones']['features'])} zones, "
          f"{len(geo['provinces']['features'])} province outlines)")
    return len(js.encode("utf-8"))


def main() -> int:
    payload = build_shared_payload()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    assets_dir = OUTPUT_DIR / ASSETS_DIRNAME
    assets_dir.mkdir(parents=True, exist_ok=True)

    css_bytes, js_bytes = _write_shared_assets(assets_dir)
    geo_bytes = _write_geo(assets_dir, set(payload["meta"].get("provinces") or []))
    print(f"\n  wrote {assets_dir / 'dashboard.css'} ({css_bytes / 1e3:.0f} KB)")
    print(f"  wrote {assets_dir / 'engine.js'} ({js_bytes / 1e3:.0f} KB)")

    total = css_bytes + js_bytes + geo_bytes
    for module in PAGE_MODULES:
        page = module.build_page(payload)
        out_path = OUTPUT_DIR / PAGE_FILENAMES[module.VIEW_ID]
        out_path.write_text(page, encoding="utf-8")
        size = len(page.encode("utf-8"))
        total += size
        print(f"  wrote {out_path} ({size / 1e3:.0f} KB)")

    # One summary page per province (province-<slug>.html)
    prov_pages = province.build_pages(payload)
    for fname, page in prov_pages.items():
        (OUTPUT_DIR / fname).write_text(page, encoding="utf-8")
        total += len(page.encode("utf-8"))
        print(f"  wrote {OUTPUT_DIR / fname}")
    # drop pages of provinces that are no longer in the data
    for stale in OUTPUT_DIR.glob("province-*.html"):
        if stale.name not in prov_pages:
            stale.unlink()

    n_pages = len(PAGE_MODULES) + len(prov_pages)
    print(f"\ntotal: {total / 1e6:.2f} MB across {n_pages} pages + shared assets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
