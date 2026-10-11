"""Build the single JSON payload shared by every page (window.PAYLOAD).

Same pattern as the epidemic dashboard: one payload, embedded in each page,
so the JS engine can read any slice whatever page is open.
"""

from __future__ import annotations

import datetime as dt
import json

from common.data_sources import load_extractions, load_manifest, load_qa, load_timeseries
from common.paths import DATA_REPO, province_filename


def build_shared_payload() -> dict:
    manifest = load_manifest()
    ts = load_timeseries()
    qa = load_qa()
    extraction = load_extractions()
    dates = manifest.get("dates") or sorted({r["date"] for r in ts["summary"]})
    # les dates et provinces de l'extraction des présentations s'ajoutent à celles du build
    dates = sorted(set(dates) | {r["date"] for r in extraction["rows"]})
    provinces = sorted({r["province"] for r in ts["summary"] if r.get("province")}
                       | {r["province"] for r in extraction["rows"] if r.get("province")})
    completer_totaux(ts["summary"], extraction["rows"])
    payload = {
        "meta": {
            "latest_date": manifest.get("date") or (dates[-1] if dates else None),
            "dates": dates,
            "provinces": provinces,
            "province_pages": {prov: province_filename(prov) for prov in provinces},
            "data_repo": DATA_REPO,
            "data_commit": manifest.get("commit", ""),
            "data_built_at": manifest.get("built_at", ""),
            "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        },
        **ts,
        "qa": qa,
        "extraction": extraction["rows"],
        "extraction_labels": {"piliers": extraction["piliers"], "sections": extraction["sections"],
                              "kpi": extraction.get("kpi_definitions") or {}},
    }
    n = {k: len(v) for k, v in ts.items()}
    print(f"  payload: {len(dates)} date(s), {len(provinces)} province(s), rows {n}, qa {len(qa)}")
    return payload


def completer_totaux(summary: list[dict], extraction: list[dict]) -> None:
    """Province sans tableau des cas par ZS ce jour-là (tableau absent ou collé en image) : le cumul des
    confirmés et des décès est repris de la carte de synthèse de sa présentation (extraction), et marqué
    comme tel (`source_cumul`). Les valeurs du build ne sont jamais remplacées."""
    cles = {(r["date"], r["province"]): r.get("cles") or {} for r in extraction}
    for row in summary:
        c = cles.get((row.get("date"), row.get("province")))
        if not c:
            continue
        repris = []
        for champ, cle in (("cumul_confirmes", "cumul_confirmes"), ("cumul_deces", "cumul_deces")):
            v = (c.get(cle) or {}).get("n")
            if row.get(champ) is None and isinstance(v, (int, float)):
                row[champ] = v
                info = c[cle]
                repris.append(f"{info.get('l') or cle} : diapositive {info.get('s')} ({info.get('src')})")
        if repris:
            row["source_cumul"] = "présentation — " + " ; ".join(repris)
            if row.get("letalite_pct") is None and row.get("cumul_confirmes") and row.get("cumul_deces") is not None:
                row["letalite_pct"] = round(100 * row["cumul_deces"] / row["cumul_confirmes"], 1)


def payload_script(payload: dict) -> str:
    """<script> tag embedding the payload; `</` is escaped so the JSON can't close the tag."""
    js = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f"<script>window.PAYLOAD={js};</script>"
