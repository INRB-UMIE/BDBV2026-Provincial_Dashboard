"""
Shared path/config constants for the dashboard build.

Same conventions as BDBV2026-Epidemic_Dashboard/Scripts/common/paths.py:
every input directory can be overridden by an environment variable, and the
default assumes the data repo is cloned as a *sibling* of this one
(../BDBV2026-Provincial_Reports), which is also how the CI checks it out.
"""

from __future__ import annotations

import os
import re
import unicodedata
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = SCRIPT_DIR.parent

DATA_ROOT = Path(os.environ.get("DATA_ROOT") or (REPO_ROOT / "Data")).resolve()
OUTPUT_DIR = REPO_ROOT / "output"

# build/ of BDBV2026-Provincial_Reports (manifest.json + timeseries/*.csv)
BUILD_DIR = Path(
    os.environ.get("BUILD_DIR")
    or (REPO_ROOT.parent / "BDBV2026-Provincial_Reports" / "build")
).resolve()
BUILD_MANIFEST = BUILD_DIR / "manifest.json"
TIMESERIES_DIR = BUILD_DIR / "timeseries"
# qa/ lives next to build/ in the data repo
QA_LOG = Path(os.environ.get("QA_LOG") or (BUILD_DIR.parent / "qa" / "qa_log.csv")).resolve()
DATA_REPO = os.environ.get("DATA_REPO", "INRB-UMIE/BDBV2026-Provincial_Reports").strip()

# Health-zone geometry: the shapefile of BDBV2026-Data
# (data/shapefiles/DRC_Health_zones.shp + .dbf/.shx/.prj/.cpg), read directly
# by common/shapefile_reader.py. Default assumes BDBV2026-Data is cloned as a
# sibling of this repo (same convention as the epidemic dashboard's BUILD_DIR).
# GEO_SOURCE may also point at a GeoJSON with the same columns.
GEO_SOURCE = Path(
    os.environ.get("GEO_SOURCE")
    or (REPO_ROOT.parent / "BDBV2026-Data" / "data" / "shapefiles" / "DRC_Health_zones.shp")
).resolve()

# Extraction des présentations (pipeline extraire_rapports.py de BDBV2026-Provincial_Reports) :
# <EXTRACTION_DIR>/PRESENTATION_JJMMAAAA/extraction/extraction_JJMMAAAA.json
# (piliers, points saillants, défis, indicateurs clés, fiabilité des 3 méthodes, contrôles).
EXTRACTION_DIR = Path(
    os.environ.get("EXTRACTION_DIR")
    or (REPO_ROOT.parent / "BDBV2026-Provincial_Reports" / "data" / "presentations")
).resolve()

BRANDING_DIR = DATA_ROOT / "Branding"
BRANDING_URLS = BRANDING_DIR / "urls.txt"
THEME_CSS = BRANDING_DIR / "dashboard-theme.css"
LOGOS_PNG = BRANDING_DIR / "all_logos.png"

# view id -> output filename (relative to OUTPUT_DIR and REPO_ROOT)
PAGE_FILENAMES = {
    "overview": "index.html",
    "summary": "synthese.html",
    "zones": "zones.html",
    "trends": "tendances.html",
    "alerts": "alertes-contacts.html",
    "quality": "qualite.html",
    "pillars": "piliers.html",
    "kpis": "kpi-piliers.html",
    "week": "semaine.html",
}

ASSETS_DIRNAME = "assets"

# One summary page per province: province-<slug>.html (e.g. province-nord-kivu.html)
PROVINCE_VIEW_ID = "province"


def province_filename(province: str) -> str:
    s = unicodedata.normalize("NFKD", province)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return f"province-{s}.html"
