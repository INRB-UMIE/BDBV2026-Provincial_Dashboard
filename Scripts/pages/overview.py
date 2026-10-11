"""Situation actuelle (index.html): full-viewport map, like the epidemic dashboard.

Same layout as BDBV2026-Epidemic_Dashboard/index.html ("Current Snapshot"):
a Leaflet map over CARTO light tiles filling the viewport, with floating
panels -- Couche (health-zone search + source), Légende (gradient bar) and
Zone (details of the clicked zone) -- and a tracker of headline numbers in
the header. The panels are built by engine.js (mapView) inside #map-root.
"""

from common.chrome import render_page

VIEW_ID = "overview"
TITLE = "Situation actuelle"

BODY = """
<div id="viewport-area">
  <div class="map-root full" id="map-root" data-map-mode="full"></div>
</div>
"""


def build_page(payload: dict) -> str:
    return render_page(VIEW_ID, TITLE, BODY, payload, with_map=True)
