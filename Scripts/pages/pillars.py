"""Piliers et fiabilité (piliers.html) : synthèse générale de l'extraction des présentations.

Données : <EXTRACTION_DIR>/PRESENTATION_JJMMAAAA/extraction/extraction_JJMMAAAA.json, produit par
extraire_rapports.py (BDBV2026-Provincial_Reports/data/presentations) :
indicateurs clés par province, coordination et piliers (points saillants, réalisations, défis,
planification), fiabilité de l'extraction (4 méthodes comparées : python-pptx, XML, LibreOffice+PDF, OCR)
et contrôles de cohérence. Les KPI Surveillance, Labo et PCI ont leur page (pages/kpis.py).
"""

from common.chrome import render_page

VIEW_ID = "pillars"
TITLE = "Piliers et fiabilité"

BODY = """
<div class="coverage-note" id="extraction-note" role="status"></div>
<section class="kpis" id="kpis" aria-label="Indicateurs clés des présentations"></section>
<article class="card">
  <header class="card-head"><h3>Indicateurs clés par province</h3>
    <p class="card-sub">Lus sur les cartes de synthèse des présentations (à défaut, ligne Total du tableau des cas par ZS).
    Survolez une valeur pour voir sa diapositive d'origine.</p></header>
  <div class="table-wrap" id="table-cles"></div>
</article>
<section class="grid-2">
  <article class="card">
    <header class="card-head"><h3>Fiabilité de l'extraction</h3>
      <p class="card-sub">Score sur 100 : éléments retrouvés par au moins 2 des 4 méthodes de lecture (40 %), accord du texte
      natif (15 %), éléments vus à l'écran par l'OCR (15 %), diapositives lisibles (20 % ; une diapositive en image lue par OCR
      compte pour moitié), cohérence des chiffres (10 %). Sans OCR : 50 / 20 / – / 20 / 10.</p></header>
    <div class="chart" id="chart-fiabilite"></div>
  </article>
  <article class="card">
    <header class="card-head"><h3>Contrôles de cohérence</h3>
      <p class="card-sub">Sommes, totaux des tableaux, dates et évolution depuis la veille, vérifiés automatiquement.</p></header>
    <div class="table-wrap" id="table-controles"></div>
  </article>
</section>
<article class="card">
  <header class="card-head"><h3>Détail de la fiabilité</h3></header>
  <div class="table-wrap" id="table-fiabilite"></div>
</article>
<article class="card">
  <header class="card-head"><h3>Coordination et piliers, toutes provinces</h3>
    <p class="card-sub">Chaque élément porte sa province, sa diapositive et le nombre de méthodes qui l'ont retrouvé ;
    « OCR » signale un élément lu sur une diapositive en image, à vérifier dans le PowerPoint.</p></header>
  <div class="filters inline">
    <label for="pillar-select">Pilier</label><select id="pillar-select"></select>
    <label for="section-select">Rubrique</label><select id="section-select"></select>
  </div>
  <div id="pillar-items" class="pillar-items"></div>
</article>
"""


def build_page(payload: dict) -> str:
    return render_page(VIEW_ID, TITLE, BODY, payload)
