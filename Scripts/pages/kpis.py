"""KPI Surveillance · Labo · PCI (kpi-piliers.html).

Données : champ « kpi_piliers » de <EXTRACTION_DIR>/PRESENTATION_JJMMAAAA/extraction/extraction_JJMMAAAA.json,
calculé par kpi_piliers.py (BDBV2026-Provincial_Reports/data/presentations) à partir des cartes, des lignes
Total des tableaux, des tableaux d'évolution, des phrases et de l'OCR des présentations provinciales.
Les taux sont recalculés à partir des numérateurs et dénominateurs extraits ; les totaux toutes provinces
ne portent que sur les provinces qui rapportent la valeur.
"""

from common.chrome import render_page

VIEW_ID = "kpis"
TITLE = "KPI Surveillance · Labo · PCI"


def _bloc(pid: str, titre: str, sous_titre: str, titre_graphique: str) -> str:
    return f"""
<article class="card kpi-pillar" id="bloc-{pid}">
  <header class="card-head"><h3>{titre}</h3><p class="card-sub">{sous_titre}</p></header>
  <section class="kpis kpis-pillar" id="kpis-{pid}" aria-label="{titre} : toutes provinces"></section>
  <div class="kpi-pillar-body">
    <div><h4 class="chart-title">{titre_graphique}</h4><div class="chart" id="chart-{pid}"></div></div>
    <div class="table-wrap" id="table-{pid}"></div>
  </div>
</article>"""


BODY = """
<div class="coverage-note" id="extraction-note" role="status"></div>
<p class="page-intro">KPI lus dans les présentations provinciales du jour : ligne Total des tableaux en priorité, puis
tableaux d'évolution (colonne du jour), cartes, phrases et, pour les diapositives en image, OCR. Les taux sont
recalculés. Les totaux « toutes provinces » ne portent que sur les provinces qui rapportent la valeur.
Survolez une valeur pour voir sa diapositive, sa source et le nombre de méthodes de lecture qui la retrouvent.</p>
""" + _bloc("surveillance", "Surveillance", "Alertes du jour, vérification, validation, transfert des suspects, recherche active, complétude.",
            "Alertes vérifiées sur alertes du jour") \
    + _bloc("laboratoire", "Laboratoire", "Échantillons reçus, analysés, en cours, positifs et taux de positivité (positifs / analysés).",
            "Taux de positivité") \
    + _bloc("pci", "PCI / WASH", "Rings ouverts, ESS / FOSA et ménages décontaminés, ménages dotés en kits, prestataires infectés.",
            "Taux de couverture PCI")


def build_page(payload: dict) -> str:
    return render_page(VIEW_ID, TITLE, BODY, payload)
