"""Alertes et contacts (alertes-contacts.html)."""

from common.chrome import render_page

VIEW_ID = "alerts"
TITLE = "Alertes et contacts"

BODY = """
<div class="filters" id="province-filter" role="group" aria-label="Filtrer par province"></div>
<section class="grid-2">
  <article class="card">
    <header class="card-head"><h3>Sources des alertes</h3>
      <p class="card-sub">Part de chaque source dans le total des alertes de la province.</p></header>
    <div class="chart" id="chart-sources"></div>
    <details class="table-toggle"><summary>Voir le tableau</summary><div class="table-wrap" id="table-sources"></div></details>
  </article>
  <article class="card">
    <header class="card-head"><h3>Contacts à suivre et vus</h3></header>
    <div class="chart" id="chart-contacts"></div>
  </article>
</section>
<article class="card">
  <header class="card-head"><h3>Alertes par zone de santé</h3></header>
  <div class="table-wrap" id="table-alerts"></div>
</article>
<article class="card">
  <header class="card-head"><h3>Suivi des contacts par zone de santé</h3></header>
  <div class="table-wrap" id="table-contacts"></div>
</article>
"""


def build_page(payload: dict) -> str:
    return render_page(VIEW_ID, TITLE, BODY, payload)
