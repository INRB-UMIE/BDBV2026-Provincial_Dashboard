"""« Piliers et fiabilité » : lecture de l'extraction des présentations et pages qui l'affichent."""
import json

from common import data_sources
from common.payload import build_shared_payload


def test_extraction_is_loaded_compactly():
    ext = data_sources.load_extractions()
    assert len(ext["rows"]) == 1
    r = ext["rows"][0]
    # extraction sans « date_presentation » (ancienne convention) : la date du dossier (30/09) est ramenée à la
    # date des données, la veille (29/09)
    assert r["date"] == "2026-09-29" and r["province"] == "Tshopo"
    assert r["cles"]["cumul_confirmes"]["n"] == 45 and r["cles"]["cumul_confirmes"]["s"] == 2
    assert r["fiabilite"]["score"] == 95 and r["n_methodes"] == 3
    pil = {p["id"]: p for p in r["piliers"]}
    assert pil["coordination"]["sections"]["points_saillants"] == [{"t": "Confirmation du 45e cas", "s": 2, "c": 3}]
    assert pil["coordination"]["indicateurs"][0]["c"] == 3
    assert pil["pec"]["incertain"] == [3]                 # confiance 0.3 < 0.4
    assert "tableaux" not in json.dumps(r)                # les tableaux bruts ne sont pas embarqués
    assert ext["piliers"]["pec"] == "Prise en charge"


def test_missing_or_broken_extraction_is_tolerated(tmp_path, monkeypatch):
    monkeypatch.setattr(data_sources, "EXTRACTION_DIR", tmp_path / "absent")
    assert data_sources.load_extractions()["rows"] == []
    bad = tmp_path / "PRESENTATION_01102026" / "extraction"
    bad.mkdir(parents=True)
    (bad / "extraction_01102026.json").write_text("{pas du json", encoding="utf-8")
    monkeypatch.setattr(data_sources, "EXTRACTION_DIR", tmp_path)
    assert data_sources.load_extractions()["rows"] == []


def test_payload_carries_extraction_without_changing_build_dates():
    p = build_shared_payload()
    assert p["meta"]["dates"] == ["2026-09-29", "2026-09-30"]    # même dates que le build
    assert p["meta"]["latest_date"] == "2026-09-30"
    assert [r["province"] for r in p["extraction"]] == ["Tshopo"]
    assert p["extraction_labels"]["piliers"]["coordination"] == "Coordination / synthèse"


def test_extraction_is_embedded_only_where_needed(tmp_path, monkeypatch):
    import build_dashboard

    monkeypatch.setattr(build_dashboard, "OUTPUT_DIR", tmp_path)
    assert build_dashboard.main() == 0
    piliers = (tmp_path / "piliers.html").read_text(encoding="utf-8")
    assert 'data-view="pillars"' in piliers and 'id="table-cles"' in piliers and 'id="pillar-items"' in piliers
    assert "Confirmation du 45e cas" in piliers
    assert "</script> <" not in piliers.split("window.PAYLOAD=")[1].split(";</script>")[0]
    tshopo = (tmp_path / "province-tshopo.html").read_text(encoding="utf-8")
    assert 'id="prov-pillars"' in tshopo and "Confirmation du 45e cas" in tshopo
    haut = (tmp_path / "province-haut-uele.html").read_text(encoding="utf-8")
    assert "Confirmation du 45e cas" not in haut           # seulement la province de la page
    assert "Confirmation du 45e cas" not in (tmp_path / "synthese.html").read_text(encoding="utf-8")
    assert 'href="piliers.html"' in (tmp_path / "index.html").read_text(encoding="utf-8")


def test_kpi_and_ocr_items_are_loaded():
    r = data_sources.load_extractions()["rows"][0]
    assert r["kpi"]["surveillance"]["alertes_total"] == {"v": "151", "n": 151, "d": None, "p": None, "s": 6,
                                                         "src": "tableau", "l": "ligne « Total » du tableau des alertes", "c": 3}
    assert r["kpi"]["surveillance"]["taux_verification"]["p"] == 100.0
    assert r["kpi"]["laboratoire"]["positifs"]["n"] == 2 and r["kpi"]["pci"] == {}
    surv = next(p for p in r["piliers"] if p["id"] == "surveillance")
    assert surv["ocr"] == [4]
    assert surv["sections"]["points_saillants"][0]["o"] == 1          # marqué « lu par OCR »
    ext = data_sources.load_extractions()
    assert [x["cle"] for x in ext["kpi_definitions"]["laboratoire"]][-1] == "taux_positivite"


def test_kpi_page_is_built(tmp_path, monkeypatch):
    import build_dashboard

    monkeypatch.setattr(build_dashboard, "OUTPUT_DIR", tmp_path)
    assert build_dashboard.main() == 0
    page = (tmp_path / "kpi-piliers.html").read_text(encoding="utf-8")
    assert 'data-view="kpis"' in page
    for pil in ("surveillance", "laboratoire", "pci"):
        assert f'id="kpis-{pil}"' in page and f'id="table-{pil}"' in page and f'id="chart-{pil}"' in page
    assert '"taux_positivite"' in page                                   # définitions des KPI embarquées
    assert 'href="kpi-piliers.html"' in (tmp_path / "index.html").read_text(encoding="utf-8")
    tshopo = (tmp_path / "province-tshopo.html").read_text(encoding="utf-8")
    assert 'id="prov-kpis"' in tshopo and '"POSITIFS"' in tshopo          # KPI de la province embarqués
    assert '"POSITIFS"' not in (tmp_path / "synthese.html").read_text(encoding="utf-8")


def test_week_page_is_built(tmp_path, monkeypatch):
    import build_dashboard

    monkeypatch.setattr(build_dashboard, "OUTPUT_DIR", tmp_path)
    assert build_dashboard.main() == 0
    page = (tmp_path / "semaine.html").read_text(encoding="utf-8")
    assert 'data-view="week"' in page and 'id="week-pillars"' in page and 'id="week-priorites"' in page
    assert 'id="export-pdf"' in page and 'id="export-word"' in page and 'id="zs-alert"' in page
    assert 'id="week-heatmap"' in page and 'id="week-lecture"' in page and '"semaines"' in page
    assert 'id="week-province"' in page and 'id="week-section"' in page and 'id="week-pillar"' in page
    assert "Confirmation du 45e cas" in page                       # toute l'extraction est embarquée
    assert '"semaines"' not in (tmp_path / "synthese.html").read_text(encoding="utf-8")   # priorités : pages qui les affichent
    assert 'href="semaine.html"' in (tmp_path / "index.html").read_text(encoding="utf-8")
    assert '"alertes_zs"' in (tmp_path / "synthese.html").read_text(encoding="utf-8")     # bandeau ZS sur toutes les pages
    prov = next(tmp_path.glob("province-*.html")).read_text(encoding="utf-8")
    assert 'id="prov-prio"' in prov and '"semaines"' in prov                              # encadré priorités


def test_missing_province_totals_come_from_the_presentation_card():
    from common.payload import completer_totaux
    summary = [{"date": "2026-10-08", "province": "Ituri", "cumul_confirmes": None, "cumul_deces": None, "letalite_pct": None},
               {"date": "2026-10-08", "province": "Tshopo", "cumul_confirmes": 55, "cumul_deces": 21, "letalite_pct": 38.2}]
    ext = [{"date": "2026-10-08", "province": "Ituri", "cles": {"cumul_confirmes": {"n": 6505, "s": 2, "src": "carte", "l": "Cumul"},
                                                                "cumul_deces": {"n": 3047, "s": 2, "src": "carte", "l": "Décès"}}},
           {"date": "2026-10-08", "province": "Tshopo", "cles": {"cumul_confirmes": {"n": 99, "s": 2, "src": "carte", "l": "x"}}}]
    completer_totaux(summary, ext)
    assert summary[0]["cumul_confirmes"] == 6505 and summary[0]["cumul_deces"] == 3047
    assert summary[0]["letalite_pct"] == 46.8 and "diapositive 2" in summary[0]["source_cumul"]
    assert summary[1]["cumul_confirmes"] == 55 and "source_cumul" not in summary[1]      # le build n'est jamais remplacé
