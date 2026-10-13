"""Piliers et fiabilité (piliers.html) : synthèse générale de l'extraction des présentations.

Données : <EXTRACTION_DIR>/PRESENTATION_JJMMAAAA/extraction/extraction_JJMMAAAA.json, produit par
extraire_rapports.py (BDBV2026-Provincial_Reports/data/presentations) :
indicateurs clés par province, coordination et piliers (points saillants, réalisations, défis,
planification), fiabilité de l'extraction (chiffres près de leur étiquette, concordance des sources, visibilité à
l'écran), éléments à vérifier et contrôles de cohérence. Les KPI Surveillance, Labo et PCI ont leur page (pages/kpis.py).
"""

from common.chrome import render_page

VIEW_ID = "pillars"
TITLE = "Piliers et fiabilité"

BODY = """
<div class="coverage-note" id="extraction-note" role="status"></div>
<section class="kpis" id="kpis" aria-label="Indicateurs clés des présentations"></section>
<article class="card">
  <header class="card-head"><h3>Indicateurs clés par province</h3>
    <p class="card-sub">Lus sur les cartes de synthèse des présentations (à défaut, ligne Total du tableau des cas par ZS,
    lue par le pipeline du dépôt).
    Survolez une valeur pour voir sa diapositive d'origine.</p></header>
  <div class="table-wrap" id="table-cles"></div>
</article>
<section class="grid-2">
  <article class="card">
    <header class="card-head"><h3>Fiabilité de l'extraction</h3>
      <p class="card-sub">Score sur 100 de l'extraction (les bons chiffres aux bons indicateurs) : chiffres lus à côté de leur
      étiquette par le PDF ou l'OCR (35 %), concordance carte / tableau par ZS / veille / KPI (20 %), chiffres visibles à
      l'écran (15 %), diapositives lisibles (15 %), lecture du texte (15 %). Plafond 85 sans OCR, 70 sans PDF ni OCR.</p></header>
    <div class="chart" id="chart-fiabilite"></div>
  </article>
  <article class="card">
    <header class="card-head"><h3>Contrôles de cohérence</h3>
      <p class="card-sub">Sommes, totaux des tableaux, dates et évolution depuis la veille, vérifiés automatiquement.</p></header>
    <div class="table-wrap" id="table-controles"></div>
  </article>
</section>
<article class="card">
  <header class="card-head"><h3>À vérifier dans les PowerPoint</h3>
    <p class="card-sub">Présentations absentes ou illisibles, sources discordantes, chiffres lus dans le fichier mais absents de
    l'écran, texte invisible écarté (forme masquée, texte de la couleur du fond, hors de la diapositive), chiffres lus loin de
    leur étiquette.</p></header>
  <div class="table-wrap" id="table-averifier"></div>
</article>
<details class="card raw-values">
  <summary><strong>Détail de la fiabilité</strong> <span class="muted">chiffres par province et par méthode</span></summary>
  <div class="table-wrap" id="table-fiabilite"></div>
</details>
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
