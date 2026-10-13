import json
import re

from common.data_sources import load_timeseries
from common.payload import build_shared_payload, payload_script


def test_payload_from_fixture():
    p = build_shared_payload()
    assert p["meta"]["latest_date"] == "2026-09-30"
    assert p["meta"]["dates"] == ["2026-09-29", "2026-09-30"]
    assert p["meta"]["provinces"] == ["Haut-Uele", "Tshopo"]
    assert p["meta"]["data_commit"] == "abc1234"
    # missing time-series files are tolerated (empty lists, no crash)
    assert p["contacts"] == [] and p["sources"] == []


def test_types_are_coerced():
    ts = load_timeseries()
    row = next(r for r in ts["summary"] if r["province"] == "Tshopo" and r["date"] == "2026-09-30")
    assert row["cumul_confirmes"] == 45 and isinstance(row["cumul_confirmes"], int)
    assert row["taux_suivi_pct"] == 83.7
    assert row["presentation_recue"] is True
    empty = next(r for r in ts["summary"] if r["province"] == "Haut-Uele")
    assert empty["cumul_confirmes"] is None          # blank stays null, never 0
    assert empty["tables_manquantes"] == "alerts;cases;contacts"
    zone = next(r for r in ts["cases"] if r["zone"] == "Kabondo")
    assert zone["confirmes_21j"] == 0                # a real 0 is kept
    assert zone["date_dernier_cas"] == "2026-09-18"  # dates stay strings


def test_payload_cannot_close_script_tag():
    tag = payload_script(build_shared_payload())
    inner = tag[len("<script>"):-len("</script>")]
    assert "</script" not in inner
    data = json.loads(re.sub(r"^window\.PAYLOAD=|;$", "", inner).replace("<\\/", "</"))
    assert data["qa"][0]["province"] == "Haut-Uele"


def test_build_writes_every_page(tmp_path, monkeypatch):
    import build_dashboard
    from common import paths

    monkeypatch.setattr(build_dashboard, "OUTPUT_DIR", tmp_path)
    assert build_dashboard.main() == 0
    for fname in paths.PAGE_FILENAMES.values():
        html = (tmp_path / fname).read_text(encoding="utf-8")
        assert "window.PAYLOAD=" in html and 'src="assets/engine.js"' in html
    assert (tmp_path / "assets" / "engine.js").exists()
    # one summary page per province, carrying its name for engine.js
    for prov, fname in (("Tshopo", "province-tshopo.html"), ("Haut-Uele", "province-haut-uele.html")):
        html = (tmp_path / fname).read_text(encoding="utf-8")
        assert f'data-province="{prov}"' in html and 'data-view="province"' in html
        assert f'<option value="{fname}" selected>' in html      # menu Provinces : la province de la page est choisie
    assert (tmp_path / "assets" / "dashboard.css").exists()
    geo = (tmp_path / "assets" / "geo.js").read_text(encoding="utf-8")
    assert geo.startswith("/* geo-cache-key: ") and "window.GEO=" in geo and "Makiso Kisangani" in geo
    # map pages load geo.js, the others don't
    assert 'src="assets/geo.js"' in (tmp_path / "index.html").read_text(encoding="utf-8")
    assert 'src="assets/geo.js"' not in (tmp_path / "qualite.html").read_text(encoding="utf-8")
    # maps use the same Leaflet build/CDN as the epidemic dashboard, loaded before engine.js
    index = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" in index
    assert index.index("leaflet@1.9.4/dist/leaflet.js") < index.index("assets/geo.js") < index.index("assets/engine.js")
    assert 'id="map-root"' in index and 'data-map-mode="full"' in index
    assert 'id="tracker"' in index
    assert "kpis" in (tmp_path / "synthese.html").read_text(encoding="utf-8")


def test_province_filename():
    from common.paths import province_filename

    assert province_filename("Nord-Kivu") == "province-nord-kivu.html"
    assert province_filename("Kasaï-Oriental") == "province-kasai-oriental.html"
    assert province_filename("Sud Ubangi") == "province-sud-ubangi.html"


def test_geo_is_cached_until_the_shapefile_changes(tmp_path, monkeypatch):
    import build_dashboard
    from common import geo as geo_mod

    calls = []
    real = geo_mod.build_geo
    monkeypatch.setattr(build_dashboard, "build_geo", lambda *a, **k: calls.append(1) or real(*a, **k))
    assets = tmp_path / "assets"
    assets.mkdir()
    build_dashboard._write_geo(assets, {"Tshopo"})
    build_dashboard._write_geo(assets, {"Tshopo"})
    assert len(calls) == 1          # second call reused geo.js
    build_dashboard._write_geo(assets, {"Tshopo", "Haut-Uele"})
    assert len(calls) == 2          # province set changed -> rebuilt
