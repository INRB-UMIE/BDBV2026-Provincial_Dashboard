"""Qualité des données (qualite.html): couverture et constats de la QA."""

from common.chrome import render_page

VIEW_ID = "quality"
TITLE = "Qualité des données"

BODY = """
<article class="card">
  <header class="card-head"><h3>Tableaux extraits par province</h3>
    <p class="card-sub">« Image » : le tableau existe dans la présentation mais il est collé en image et ne peut pas être lu.</p></header>
  <div class="table-wrap" id="coverage-matrix"></div>
</article>
<article class="card">
  <header class="card-head"><h3>Constats de la QA</h3></header>
  <div class="filters inline">
    <label for="level-select">Niveau</label>
    <select id="level-select">
      <option value="">Tous</option>
      <option value="fail">Erreurs bloquantes</option>
      <option value="warn">Avertissements</option>
    </select>
  </div>
  <div class="table-wrap" id="table-qa"></div>
</article>
"""


def build_page(payload: dict) -> str:
    return render_page(VIEW_ID, TITLE, BODY, payload)
