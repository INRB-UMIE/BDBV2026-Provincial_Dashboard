"""Load BDBV2026-Provincial_Reports' build/ (manifest + time series) and QA log.

Every input is tolerated when missing: the loader returns empty lists and
prints a warning, and the corresponding panels show an empty state instead
of the build failing (same policy as the epidemic dashboard).
"""

from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path

import re

from common.paths import BUILD_MANIFEST, EXTRACTION_DIR, QA_LOG, TIMESERIES_DIR

TIMESERIES_FILES = {
    "summary": "province_summary.csv",
    "cases": "cases_by_zone.csv",
    "alerts_zone": "alerts_by_zone.csv",
    "alerts_aire": "alerts_by_aire.csv",
    "contacts": "contacts_by_zone.csv",
    "sources": "alert_sources.csv",
}

# Columns kept per table (keeps the embedded payload small and stable).
KEEP = {
    "summary": None,  # all
    "cases": ["date", "province", "zone", "zone_resolved", "cumul_confirmes", "cumul_deces",
              "letalite", "confirmes_21j", "deces_21j", "date_dernier_cas",
              "jours_depuis_dernier_cas"],
    "alerts_zone": ["date", "province", "zone", "nouvelles_alertes_vivants", "nouvelles_alertes_deces",
                    "total_alertes", "validees_vivants", "validees_deces", "invalidees_vivants",
                    "invalidees_deces", "suspects_transferes"],
    "alerts_aire": ["date", "province", "zone", "aire_sante", "nouvelles_alertes_vivants",
                    "nouvelles_alertes_deces", "total_alertes", "validees_vivants", "validees_deces"],
    "contacts": ["date", "province", "zone", "a_suivre", "vus", "taux_suivi_pct", "nouveaux",
                 "devenus_suspects", "perdus_de_vue", "jamais_vus", "non_vus", "contacts_confirmes"],
    "sources": ["date", "province", "source", "vivants", "deces", "total"],
}


def _coerce(v: str):
    if v is None or v == "":
        return None
    if v in ("True", "False"):
        return v == "True"
    try:
        f = float(v)
    except ValueError:
        return v
    return int(f) if f.is_integer() and "." not in v else f


def read_table(path: Path, keep: list[str] | None = None) -> list[dict]:
    if not path.exists():
        print(f"  WARNING: {path} not found; panel will be empty")
        return []
    with path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    text_cols = {"date", "province", "zone", "aire_sante", "source", "date_dernier_cas",
                 "tables_extraites", "tables_manquantes", "check", "status", "detail"}
    out = []
    for r in rows:
        row = {}
        for c in keep or list(r.keys()):
            raw = r.get(c, "")
            if raw in ("", None):
                row[c] = None
            elif c in text_cols:
                row[c] = raw
            else:
                row[c] = _coerce(raw)
        out.append(row)
    return out


def load_manifest() -> dict:
    if not BUILD_MANIFEST.exists():
        print(f"  WARNING: {BUILD_MANIFEST} not found; is BDBV2026-Provincial_Reports cloned "
              f"next to this repo (or BUILD_DIR set)?")
        return {}
    return json.loads(BUILD_MANIFEST.read_text(encoding="utf-8"))


def load_timeseries() -> dict[str, list[dict]]:
    return {key: read_table(TIMESERIES_DIR / fname, KEEP[key])
            for key, fname in TIMESERIES_FILES.items()}


def load_qa() -> list[dict]:
    rows = read_table(QA_LOG, ["date", "province", "check", "status", "detail"])
    return [{k: (str(v) if v is not None else "") for k, v in r.items()} for r in rows]


# ── Extraction des présentations (piliers, points saillants, fiabilité) ──────
SECTIONS_EXTRACTION = ("points_saillants", "realisations", "defis", "planification", "recommandations")


def _iso(date_fr: str) -> str | None:
    m = re.fullmatch(r"(\d{2})/(\d{2})/(\d{4})", date_fr or "")
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else None


def _compact_presentation(date: str, pr: dict) -> dict:
    """Une ligne (date, province) compacte : ce que les pages affichent, sans les tableaux bruts."""
    piliers: dict[str, dict] = {}
    for d in pr.get("diapositives", []):
        if d.get("type") != "contenu" or not d.get("pilier"):
            continue
        pil = piliers.setdefault(d["pilier"], {"id": d["pilier"], "libelle": d.get("pilier_libelle") or d["pilier"],
                                               "diapos": [], "indicateurs": [], "sections": {}, "incertain": []})
        pil["diapos"].append(d["numero"])
        if d.get("pilier_confiance", 1) < 0.4:
            pil["incertain"].append(d["numero"])
        if d.get("lu_par_ocr"):
            pil.setdefault("ocr", []).append(d["numero"])
        ocr_items = set(d.get("ocr_items") or [])
        for x in d.get("indicateurs", []):
            pil["indicateurs"].append({"l": x["indicateur"], "v": x["valeur"], "det": x.get("detail", ""),
                                       "c": x.get("confirmations"), "s": d["numero"]})
        conf = d.get("confirmations", {})
        for k in SECTIONS_EXTRACTION:
            items = d.get("sections", {}).get(k, [])
            cs = conf.get(k, [])
            for i, t in enumerate(items):
                it = {"t": t, "s": d["numero"], "c": cs[i] if i < len(cs) else None}
                if t in ocr_items:
                    it["o"] = 1          # lu par OCR sur une diapositive en image
                pil["sections"].setdefault(k, []).append(it)
    cles = {k: {"v": v.get("valeur"), "n": v.get("num"), "d": v.get("den"), "s": v.get("diapositive"),
                "src": v.get("source"), "l": v.get("libelle")} for k, v in (pr.get("indicateurs_cles") or {}).items()}
    kpi = {pil: {k: {"v": v.get("valeur"), "n": v.get("n"), "d": v.get("d"), "p": v.get("pct"),
                     "s": v.get("diapo"), "src": v.get("src"), "l": v.get("lib"), "c": v.get("conf")}
                 for k, v in (kk or {}).items()}
           for pil, kk in (pr.get("kpi_piliers") or {}).items()}
    return {
        "date": date, "province": pr.get("province"), "fichier": pr.get("fichier"),
        "kpi": kpi, "methodes": pr.get("methodes") or [],
        "date_garde": pr.get("date_garde"), "n_diapos": pr.get("nb_diapositives"),
        "n_methodes": len(pr.get("methodes") or []),
        "fiabilite": pr.get("fiabilite") or {}, "controles": pr.get("controles") or [],
        "note_fichier": pr.get("note_fichier"),
        "cles": cles, "piliers": list(piliers.values()),
    }


def load_extractions() -> dict:
    """Toutes les extractions disponibles : {"rows": [...], "piliers": {id: libellé}, "sections": {id: libellé}}.

    Lit EXTRACTION_DIR/PRESENTATION_*/extraction/extraction_*.json. Absent -> listes vides (pas d'erreur).
    """
    out = {"rows": [], "piliers": {}, "sections": {}, "kpi_definitions": {}, "echecs": []}
    if not EXTRACTION_DIR.exists():
        print(f"  WARNING: {EXTRACTION_DIR} not found; « Piliers et fiabilité » will be empty")
        return out
    fichiers = sorted(EXTRACTION_DIR.glob("PRESENTATION_*/extraction/extraction_*.json"))
    for f in fichiers:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError) as ex:
            print(f"  WARNING: {f} illisible ({ex}); ignoré")
            continue
        date = _iso(data.get("date", ""))
        if not date:
            continue
        # convention : « date » = date des données (veille de la présentation). Les extractions antérieures à cette
        # convention (sans « date_presentation ») portent la date du dossier : on la ramène à la veille.
        if not data.get("date_presentation"):
            date = (dt.date.fromisoformat(date) - dt.timedelta(days=1)).isoformat()
        out["piliers"].update(data.get("piliers") or {})
        out["sections"].update(data.get("sections") or {})
        out["kpi_definitions"].update(data.get("kpi_definitions") or {})
        out["rows"].extend(_compact_presentation(date, pr) for pr in data.get("presentations", []))
        # provinces absentes ou dont la présentation n'a pas pu être lue (extraction version ≥ 4)
        out["echecs"].extend({"date": date, "province": e.get("province"), "statut": e.get("statut"),
                              "raison": e.get("raison"), "fichier": e.get("fichier")} for e in data.get("echecs") or [])
    # une même date traitée deux fois (deux dossiers) : on garde la dernière lecture
    uniques = {(r["date"], r["province"]): r for r in out["rows"]}
    out["rows"] = sorted(uniques.values(), key=lambda r: (r["date"], r["province"] or ""))
    lues = set(uniques)
    out["echecs"] = [e for e in {(e["date"], e["province"]): e for e in out["echecs"]}.values()
                     if (e["date"], e["province"]) not in lues]
    print(f"  extraction: {len(fichiers)} fichier(s), {len(out['rows'])} présentation(s)")
    return out
