"""Résumé de la semaine (semaine.html) : la semaine (lundi → dimanche) qui contient la date choisie, lue comme
un épidémiologiste — lecture en quelques phrases, priorités classées, indicateurs de riposte en couleurs
(cibles CDC/OMS), évolution en graphiques, points remontés par les provinces regroupés par thème, puis le
détail par pilier.

Données : priorités calculées au build par common/priorites.py (payload["semaines"]) à partir du build de
BDBV2026-Provincial_Reports et de l'extraction des présentations. Les chiffres restent disponibles au survol.
"""

from common.chrome import render_page

VIEW_ID = "week"
TITLE = "Résumé de la semaine"

BODY = """
<div class="coverage-note" id="extraction-note" role="status"></div>
<div class="week-head">
  <button type="button" class="week-nav" id="week-prev" aria-label="Semaine précédente">◀</button>
  <div><div class="week-title" id="week-title"></div><div class="week-sub" id="week-sub"></div></div>
  <button type="button" class="week-nav" id="week-next" aria-label="Semaine suivante">▶</button>
  <div class="week-export" role="group" aria-label="Exporter le résumé de la semaine">
    <button type="button" class="btn-export" id="export-pdf" title="Ouvre l'impression : choisissez « Enregistrer au format PDF »">⤓ PDF</button>
    <button type="button" class="btn-export" id="export-word" title="Télécharge un document Word (.docx) modifiable">⤓ Word</button>
  </div>
</div>

<article class="card lecture-card">
  <header class="card-head"><h3>Lecture de la semaine</h3></header>
  <div id="week-lecture" class="lecture"></div>
</article>

<section aria-labelledby="h-prio">
  <h3 class="section-title" id="h-prio">Priorités de la semaine</h3>
  <p class="section-sub">Classées par gravité puis par importance épidémiologique. Un problème = une carte, avec les provinces
  concernées. Ouvrez une carte pour voir les chiffres.</p>
  <div id="week-priorites" class="prio-grid"></div>
  <div id="week-bons" class="bons"></div>
</section>

<article class="card">
  <header class="card-head"><h3>Indicateurs de riposte par province</h3>
    <p class="card-sub" id="heat-sub"></p></header>
  <div class="heat-legend" aria-hidden="true">
    <span><i class="hs ok"></i>Cible atteinte</span><span><i class="hs attention"></i>À surveiller</span>
    <span><i class="hs critique"></i>Critique</span><span><i class="hs nd"></i>Non rapporté</span>
  </div>
  <div class="table-wrap" id="week-heatmap"></div>
</article>

<section class="grid-2">
  <article class="card">
    <header class="card-head"><h3>Nouveaux cas confirmés par jour</h3>
      <p class="card-sub">Cartes de synthèse des présentations ; survolez une barre pour la valeur.</p></header>
    <div id="week-cas" class="multiples-cas"></div>
  </article>
  <article class="card">
    <header class="card-head"><h3>Zones de santé : 21 et 42 jours</h3>
      <p class="card-sub">Active : cas dans les 21 derniers jours · vigilance : 22–42 jours · sous contrôle : plus de 42 jours
      (critère OMS de fin de transmission).</p></header>
    <div id="week-zs" class="chart"></div>
  </article>
</section>

<article class="card">
  <header class="card-head"><h3>Ce que remontent les provinces</h3>
    <p class="card-sub">Défis, points saillants et recommandations de la semaine, regroupés quand ils se répètent d'un jour ou
    d'une province à l'autre, puis classés par thème selon leur poids épidémiologique.</p></header>
  <div class="filters inline">
    <label for="week-province">Province</label><select id="week-province"></select>
  </div>
  <div id="week-points" class="themes-grid"></div>
</article>

<details class="card week-detail">
  <summary><strong>Détail par pilier</strong> <span class="muted">tous les points et KPI de la semaine, jour par jour</span></summary>
  <div class="filters inline week-filters">
    <label for="week-section">Rubrique</label><select id="week-section"></select>
    <label for="week-pillar">Pilier</label><select id="week-pillar"></select>
  </div>
  <div id="week-pillars" class="week-pillars"></div>
</details>
<p class="reference" id="week-ref"></p>
"""


def build_page(payload: dict) -> str:
    return render_page(VIEW_ID, TITLE, BODY, payload)
