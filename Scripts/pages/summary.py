"""Synthèse (synthese.html): KPIs, provinces, couverture des données."""

from common.chrome import render_page

VIEW_ID = "summary"
TITLE = "Synthèse"

BODY = """
<div class="coverage-note" id="coverage-note" role="status"></div>
<section class="kpis" id="kpis" aria-label="Indicateurs clés"></section>
<section class="grid-2">
  <article class="card">
    <header class="card-head"><h3>Cumul des cas confirmés par province</h3></header>
    <div class="chart" id="chart-province-cases"></div>
  </article>
  <article class="card">
    <header class="card-head"><h3>Taux de suivi des contacts par province</h3></header>
    <div class="chart" id="chart-province-followup"></div>
  </article>
</section>
<article class="card">
  <header class="card-head"><h3>Synthèse par province</h3></header>
  <div class="table-wrap" id="table-provinces"></div>
</article>
"""


def build_page(payload: dict) -> str:
    return render_page(VIEW_ID, TITLE, BODY, payload)
