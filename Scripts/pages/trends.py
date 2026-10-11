"""Tendances (tendances.html): évolution par date, total et petits multiples par province."""

from common.chrome import render_page

VIEW_ID = "trends"
TITLE = "Tendances"

BODY = """
<div class="filters">
  <label for="metric-select">Indicateur</label>
  <select id="metric-select"></select>
</div>
<article class="card">
  <header class="card-head"><h3 id="national-title">Ensemble des provinces extraites</h3>
    <p class="card-sub">Somme des provinces dont le tableau a été extrait à chaque date : une province manquante fait baisser le total.</p></header>
  <div class="chart" id="chart-national"></div>
</article>
<section class="multiples" id="chart-multiples" aria-label="Une courbe par province"></section>
"""


def build_page(payload: dict) -> str:
    return render_page(VIEW_ID, TITLE, BODY, payload)
