"""Résumé par province: one page per province (province-<slug>.html).

Same body for every province; engine.js reads <body data-province="..."> and
renders that province's slice of the shared payload for the selected date.
"""

import html

from common.chrome import render_page
from common.paths import PROVINCE_VIEW_ID, province_filename

VIEW_ID = PROVINCE_VIEW_ID

BODY = """
<p class="breadcrumb"><a href="synthese.html" data-keep-date>← Synthèse</a></p>
<article class="card summary-card">
  <header class="card-head"><h3>Résumé</h3></header>
  <div id="prov-summary" class="prose"></div>
</article>
<section class="kpis" id="kpis" aria-label="Indicateurs clés"></section>
<article class="card map-card">
  <header class="card-head"><h3>Carte des zones de santé</h3></header>
  <div class="map-root embed" id="map-root" data-map-mode="embed"></div>
</article>
<section class="grid-2">
  <article class="card">
    <header class="card-head"><h3 id="zones-chart-title">Confirmés sur les 21 derniers jours, par zone de santé</h3></header>
    <div class="chart" id="chart-zones"></div>
  </article>
  <article class="card">
    <header class="card-head"><h3>Cumul des cas confirmés dans le temps</h3></header>
    <div class="chart" id="chart-trend"></div>
  </article>
</section>
<article class="card">
  <header class="card-head"><h3>Cas confirmés par zone de santé</h3>
    <p class="card-sub">Statut : ≤ 21 j active, 22–42 j en surveillance, &gt; 42 j sans cas.</p></header>
  <div class="table-wrap" id="table-zones"></div>
</article>
<section class="grid-2">
  <article class="card">
    <header class="card-head"><h3>Contacts à suivre et vus, par zone de santé</h3></header>
    <div class="chart" id="chart-contacts"></div>
  </article>
  <article class="card">
    <header class="card-head"><h3>Sources des alertes</h3></header>
    <div class="chart" id="chart-sources"></div>
    <details class="table-toggle"><summary>Voir le tableau</summary><div class="table-wrap" id="table-sources"></div></details>
  </article>
</section>
<article class="card">
  <header class="card-head"><h3>Alertes</h3></header>
  <div class="table-wrap" id="table-alerts"></div>
</article>
<article class="card">
  <header class="card-head"><h3>Suivi des contacts par zone de santé</h3></header>
  <div class="table-wrap" id="table-contacts"></div>
</article>
<article class="card">
  <header class="card-head"><h3>KPI Surveillance · Labo · PCI</h3>
    <p class="card-sub">Lus dans la présentation du jour (tableaux, cartes, phrases, OCR) ; taux recalculés.
    Survolez une valeur pour voir sa diapositive et sa source.</p></header>
  <div id="prov-kpis" class="prov-kpis"></div>
</article>
<article class="card">
  <header class="card-head"><h3>Coordination et piliers</h3>
    <p class="card-sub">Extraits de la présentation du jour : indicateurs, points saillants, réalisations, défis et planification,
    par pilier. <span id="prov-fiabilite"></span></p></header>
  <div id="prov-controles"></div>
  <div id="prov-pillars" class="pillar-accordion"></div>
</article>
<article class="card">
  <header class="card-head"><h3>Qualité des données</h3>
    <p class="card-sub">Tableaux extraits et incohérences repérées dans la présentation de la province.</p></header>
  <div id="prov-coverage" class="coverage-pills"></div>
  <div class="table-wrap" id="table-qa"></div>
</article>
"""


def build_pages(payload: dict) -> dict[str, str]:
    """{filename: html} for every province in the payload."""
    out = {}
    for prov in payload.get("meta", {}).get("provinces", []):
        title = f"Province : {prov}"
        out[province_filename(prov)] = render_page(VIEW_ID, title, BODY, payload, province=prov, with_map=True)
    return out
