"""Zones de santé (zones.html): cas par ZS, activité sur 21 jours."""

from common.chrome import render_page

VIEW_ID = "zones"
TITLE = "Zones de santé"

BODY = """
<div class="filters" id="province-filter" role="group" aria-label="Filtrer par province"></div>
<article class="card map-card">
  <header class="card-head"><h3>Carte des zones de santé</h3></header>
  <div class="map-root embed" id="map-root" data-map-mode="embed"></div>
</article>
<article class="card">
  <header class="card-head map-head"><div><h3>ZS touchées sans nouveau cas notifié</h3>
    <p class="card-sub">Zones avec au moins un cas confirmé, classées selon les jours écoulés depuis leur dernier cas : 21 à 42 jours
    (vigilance : la période d'incubation est passée, la transmission n'est pas encore déclarée terminée) ou plus de 42 jours
    (fin de transmission, critère OMS). Sur la carte : couche « Statut des zones de santé ».</p></div>
    <div class="seg" role="group" aria-label="Jours sans nouveau cas">
      <button type="button" class="seg-btn" data-sanscas="vig" aria-pressed="true">21 à 42 j</button>
      <button type="button" class="seg-btn" data-sanscas="ctrl" aria-pressed="false">&gt; 42 j</button>
    </div></header>
  <div id="zs-sans-cas"></div>
</article>
<article class="card">
  <header class="card-head"><h3>Confirmés sur les 21 derniers jours, par zone de santé</h3></header>
  <div class="chart" id="chart-zones-21"></div>
</article>
<article class="card">
  <header class="card-head"><h3>Cas confirmés par zone de santé</h3>
    <p class="card-sub">Statut d'après les jours écoulés depuis le dernier cas confirmé : ≤ 21 j active, 22–42 j en surveillance, &gt; 42 j sans cas.</p></header>
  <div class="table-wrap" id="table-zones"></div>
</article>
"""


def build_page(payload: dict) -> str:
    return render_page(VIEW_ID, TITLE, BODY, payload, with_map=True)
