"""Résumé de la semaine (semaine.html) : une fenêtre par pilier pour la semaine (lundi → dimanche)
qui contient la date choisie.

Données : toutes les extractions des présentations de la semaine (EXTRACTION_DIR, extraire_rapports.py).
Pour chaque pilier :
  - KPI jour par jour et total de la semaine (Surveillance, Laboratoire, PCI ; indicateurs clés pour la
    coordination) : sommes pour les flux (alertes, échantillons…), dernière valeur pour les stocks,
    taux recalculés sur la semaine ;
  - points saillants, réalisations, défis, planification et recommandations de toutes les provinces,
    regroupés quand le même point revient d'un jour à l'autre (« 5 j. »), un défi présent tous les jours
    étant signalé comme persistant.
"""

from common.chrome import render_page

VIEW_ID = "week"
TITLE = "Résumé de la semaine"

BODY = """
<div class="coverage-note" id="extraction-note" role="status"></div>
<p class="page-intro" id="week-intro"></p>
<section class="kpis" id="week-kpis" aria-label="La semaine en chiffres"></section>
<div class="filters inline week-filters">
  <label for="week-province">Province</label><select id="week-province"></select>
  <label for="week-section">Rubrique</label><select id="week-section"></select>
  <label for="week-pillar">Pilier</label><select id="week-pillar"></select>
  <button type="button" class="chip" id="week-toggle" aria-pressed="false">Tout déplier</button>
</div>
<div id="week-pillars" class="week-pillars"></div>
"""


def build_page(payload: dict) -> str:
    return render_page(VIEW_ID, TITLE, BODY, payload)
