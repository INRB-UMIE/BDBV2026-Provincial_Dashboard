"""Health-zone and province geometry for the maps (standard library only).

Source: the health-zone shapefile of BDBV2026-Data,
data/shapefiles/DRC_Health_zones.{shp,dbf,shx,prj,cpg} (GRID3 COD health
zones v8.0; columns Nom / PROVINCE / ZSCode), read directly by
shapefile_reader.py. The derived build/drc_health_zones.geojson (what the
epidemic dashboard reads) is accepted as a fallback.

The epidemic dashboard cleans this coverage with shapely (_clean_coverage,
build_province_boundaries). This build has no third-party dependency, so the
same two problems are solved directly on the vertices:

1. **Zones** -- simplified *per shared arc*, not per polygon. Rings are cut
   at every vertex where the set of zones touching it changes (junctions);
   each arc is simplified once (Douglas-Peucker, canonical direction, cached)
   and reused by every zone that shares it, so neighbours keep one identical
   border instead of two slightly different ones.

2. **Province outlines** -- the edges of a province's zones that are not
   interior to the province. An edge is interior if it is exactly shared with
   another zone of the same province, *or* if it runs within SNAP_TOL of (or
   inside) another zone of the same province -- the source polygons overlap a
   little, so ~1/3 of interior edges are not exact duplicates and would
   otherwise draw stray dashes inside provinces. Outlines are emitted as
   MultiLineStrings (they are only stroked, never filled).
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

DEC_IN = 5            # match key precision (the source is rounded to 5 decimals)
SIMPLIFY_TOL = 0.001  # degrees (~110 m), same value as the epidemic dashboard
OUTLINE_TOL = 0.002   # province outlines are thicker strokes: simplify a bit more
SNAP_TOL = 0.003      # degrees (~330 m): "runs along another zone of the province"
COORD_DECIMALS = 4    # ~11 m, plenty for a zoom-10 map
CELL = 0.05           # spatial-grid cell (degrees) for the edge index
# DRC silhouette (the provinces *not* in the data, drawn in light grey behind
# the concerned ones on the general view): coarser, it is only a backdrop
BACKDROP_TOL = 0.01          # ~1.1 km
BACKDROP_OUTLINE_TOL = 0.006
BACKDROP_DECIMALS = 3

Pt = tuple[float, float]


# ── small geometry helpers ─────────────────────────────────────────────────

def _rings(geom: dict) -> list[list[list[float]]]:
    if geom["type"] == "Polygon":
        return geom["coordinates"]
    if geom["type"] == "MultiPolygon":
        return [r for poly in geom["coordinates"] for r in poly]
    return []


def _polys(geom: dict) -> list[list[list[list[float]]]]:
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return geom["coordinates"]
    return []


def _key(p) -> Pt:
    return (round(p[0], DEC_IN), round(p[1], DEC_IN))


def _seg_dist(p: Pt, a: Pt, b: Pt) -> float:
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    L = dx * dx + dy * dy
    t = 0.0 if L == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def _point_in_ring(p: Pt, ring: list) -> bool:
    x, y = p
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-300) + xi:
            inside = not inside
        j = i
    return inside


def _point_in_geom(p: Pt, geom: dict) -> bool:
    for poly in _polys(geom):
        if poly and _point_in_ring(p, poly[0]) and not any(_point_in_ring(p, h) for h in poly[1:]):
            return True
    return False


def _douglas_peucker(pts: list[Pt], tol: float) -> list[Pt]:
    if len(pts) < 3:
        return list(pts)
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        i, j = stack.pop()
        best, idx = 0.0, -1
        for k in range(i + 1, j):
            d = _seg_dist(pts[k], pts[i], pts[j])
            if d > best:
                best, idx = d, k
        if best > tol and idx > 0:
            keep[idx] = True
            stack.append((i, idx))
            stack.append((idx, j))
    return [p for p, k in zip(pts, keep) if k]


def _round(p: Pt) -> list[float]:
    return [round(p[0], COORD_DECIMALS), round(p[1], COORD_DECIMALS)]


def _ring_area(ring: list) -> float:
    s = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


# ── 1. zones: arc-consistent simplification ───────────────────────────────

def simplify_zones(features: list[dict], tol: float = SIMPLIFY_TOL) -> list[dict]:
    """Return features with simplified geometry; shared borders stay identical."""
    owners: dict[Pt, set[int]] = defaultdict(set)
    for i, f in enumerate(features):
        for ring in _rings(f["geometry"]):
            for p in ring:
                owners[_key(p)].add(i)

    cache: dict[tuple, list[Pt]] = {}

    def simplify_arc(arc: list[Pt]) -> list[Pt]:
        fwd = tuple(arc)
        rev = fwd[::-1]
        canon = min(fwd, rev)
        if canon not in cache:
            cache[canon] = _douglas_peucker(list(canon), tol)
        out = cache[canon]
        return out if canon == fwd else out[::-1]

    def simplify_ring(ring: list) -> list[list[float]] | None:
        pts = [_key(p) for p in ring]
        if pts[0] == pts[-1]:
            pts = pts[:-1]
        # drop consecutive duplicates
        pts = [p for k, p in enumerate(pts) if k == 0 or p != pts[k - 1]]
        n = len(pts)
        if n < 3:
            return None
        sets = [frozenset(owners[p]) for p in pts]
        locked = [
            len(sets[k]) >= 3 or sets[k] != sets[k - 1] or sets[k] != sets[(k + 1) % n]
            for k in range(n)
        ]
        if not any(locked):
            # isolated ring (no neighbour): lock the two farthest-apart vertices
            far = max(range(n), key=lambda k: (pts[k][0] - pts[0][0]) ** 2 + (pts[k][1] - pts[0][1]) ** 2)
            locked[0] = locked[far] = True
        starts = [k for k in range(n) if locked[k]]
        out: list[Pt] = []
        for s_i, s in enumerate(starts):
            e = starts[(s_i + 1) % len(starts)]
            arc = [pts[k % n] for k in range(s, (e if e > s else e + n) + 1)]
            seg = simplify_arc(arc)
            out.extend(seg[:-1])
        out.append(out[0])
        if len(out) < 4:
            return None
        return [_round(p) for p in out]

    result = []
    for f in features:
        polys_out = []
        for poly in _polys(f["geometry"]):
            rings_out = [simplify_ring(r) for r in poly]
            if rings_out and rings_out[0]:
                polys_out.append([r for r in rings_out if r])
        if not polys_out:
            continue
        geom = ({"type": "Polygon", "coordinates": polys_out[0]} if len(polys_out) == 1
                else {"type": "MultiPolygon", "coordinates": polys_out})
        result.append({**f, "geometry": geom})
    return result


# ── 2. province outlines ──────────────────────────────────────────────────

def province_outlines(features: list[dict], tol: float = OUTLINE_TOL) -> dict:
    """FeatureCollection of MultiLineString outlines, one per province."""
    prov = [f["properties"].get("province") for f in features]
    edge_owners: dict[tuple[Pt, Pt], list[int]] = defaultdict(list)
    for i, f in enumerate(features):
        for ring in _rings(f["geometry"]):
            pts = [_key(p) for p in ring]
            for a, b in zip(pts, pts[1:]):
                if a != b:
                    edge_owners[(a, b) if a < b else (b, a)].append(i)

    # spatial index of every zone edge, for the tolerant "interior" test
    grid: dict[tuple[int, int], list[tuple[Pt, Pt, int]]] = defaultdict(list)
    for (a, b), own in edge_owners.items():
        for i in own:
            cx0, cx1 = sorted((int(a[0] // CELL), int(b[0] // CELL)))
            cy0, cy1 = sorted((int(a[1] // CELL), int(b[1] // CELL)))
            for cx in range(cx0, cx1 + 1):
                for cy in range(cy0, cy1 + 1):
                    grid[(cx, cy)].append((a, b, i))

    def near_same_province_zone(mid: Pt, zone: int) -> bool:
        p = prov[zone]
        cx, cy = int(mid[0] // CELL), int(mid[1] // CELL)
        candidates = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for a, b, j in grid.get((cx + dx, cy + dy), ()):
                    if j != zone and prov[j] == p:
                        if _seg_dist(mid, a, b) <= SNAP_TOL:
                            return True
                        candidates.add(j)
        # the edge may also lie inside an overlapping neighbour
        return any(_point_in_geom(mid, features[j]["geometry"]) for j in candidates)

    border: dict[str, list[tuple[Pt, Pt]]] = defaultdict(list)
    for (a, b), own in edge_owners.items():
        provs = {prov[i] for i in own}
        for p in provs:
            mine = [i for i in own if prov[i] == p]
            if len(mine) >= 2:
                continue  # exactly shared inside the province
            mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            if len(provs) == 1 and near_same_province_zone(mid, mine[0]):
                continue  # almost-shared inside the province (overlap / offset)
            border[p].append((a, b))

    out = []
    for p in sorted(border):
        lines = _chain(border[p])
        lines = [[_round(q) for q in _douglas_peucker(l, tol)] for l in lines]
        # drop tiny leftovers (sub-kilometre fragments)
        lines = [l for l in lines if _length(l) > 3 * SNAP_TOL]
        if lines:
            out.append({"type": "Feature", "properties": {"province": p},
                        "geometry": {"type": "MultiLineString", "coordinates": lines}})
    return {"type": "FeatureCollection", "features": out}


def _length(line: list) -> float:
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(line, line[1:]))


def _chain(edges: list[tuple[Pt, Pt]]) -> list[list[Pt]]:
    """Join edges into the longest possible polylines."""
    adj: dict[Pt, list[Pt]] = defaultdict(list)
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    used: set[tuple[Pt, Pt]] = set()

    def take(a, b):
        used.add((a, b) if a < b else (b, a))

    def free(a, b):
        return ((a, b) if a < b else (b, a)) not in used

    lines = []
    # start from ends/junctions first, then close remaining loops
    starts = [v for v, n in adj.items() if len(n) != 2] + list(adj)
    for s in starts:
        for nxt in adj[s]:
            if not free(s, nxt):
                continue
            line = [s, nxt]
            take(s, nxt)
            cur, prev = nxt, s
            while len(adj[cur]) == 2:
                cand = [v for v in adj[cur] if free(cur, v)]
                if not cand:
                    break
                prev, cur = cur, cand[0]
                take(prev, cur)
                line.append(cur)
            lines.append(line)
    return lines


# ── loading: shapefile (preferred) or GeoJSON ─────────────────────────────

PRE_GRID = 1e-3  # ~110 m: the raw shapefile has ~4.1 M vertices; snapping to this
                 # grid first is deterministic, so neighbours sharing a border
                 # still share the snapped vertices exactly.

# shapefile column -> property used by the dashboard (same renames as
# BDBV2026-Data's tools: Nom = canonical zone name, PROVINCE, ZSCode)
SHP_FIELDS = {"nom": ("Nom", "nom"), "province": ("PROVINCE", "province"), "zscode": ("ZSCode", "zscode")}


def _snap_geometry(geom: dict, grid: float) -> dict | None:
    def ring(r):
        out = []
        for x, y in r:
            p = [round(round(x / grid) * grid, 6), round(round(y / grid) * grid, 6)]
            if not out or p != out[-1]:
                out.append(p)
        if out and out[0] != out[-1]:
            out.append(out[0])
        return out if len(out) >= 4 else None

    polys = []
    for poly in _polys(geom):
        rings = [ring(r) for r in poly]
        if rings and rings[0]:
            polys.append([r for r in rings if r])
    if not polys:
        return None
    return {"type": "Polygon", "coordinates": polys[0]} if len(polys) == 1 else \
        {"type": "MultiPolygon", "coordinates": polys}


def load_zone_features(source: Path) -> list[dict]:
    """Zone features with properties {nom, province, zscode}.

    `source` is BDBV2026-Data's shapefile (data/shapefiles/DRC_Health_zones.shp,
    read with the standard-library reader in shapefile_reader.py) or, as a
    fallback, a GeoJSON with the same columns (build/drc_health_zones.geojson).
    """
    source = Path(source)
    if source.suffix.lower() == ".shp":
        from common.shapefile_reader import read_shapefile
        raw = read_shapefile(source)
    else:
        raw = json.loads(source.read_text(encoding="utf-8")).get("features", [])

    def pick(props, key):
        for col in SHP_FIELDS[key]:
            if props.get(col) not in (None, ""):
                return props[col]
        return None

    feats = []
    for f in raw:
        props = f.get("properties") or {}
        nom = pick(props, "nom")
        if not f.get("geometry") or not nom:
            continue
        geom = _snap_geometry(f["geometry"], PRE_GRID)
        if geom is None:
            continue
        feats.append({"type": "Feature", "geometry": geom,
                      "properties": {"nom": nom, "province": pick(props, "province"),
                                     "zscode": pick(props, "zscode")}})
    return feats


# ── public entry point ─────────────────────────────────────────────────────

def _bounds_of(features: list[dict]) -> list[float] | None:
    b = None
    for f in features:
        g = f["geometry"]
        rings = _rings(g) if g["type"] in ("Polygon", "MultiPolygon") else g["coordinates"]
        for ring in rings:
            for x, y in ring:
                if b is None:
                    b = [x, y, x, y]
                b[0], b[1], b[2], b[3] = min(b[0], x), min(b[1], y), max(b[2], x), max(b[3], y)
    return [round(v, 3) for v in b] if b else None


def build_geo(source: Path, provinces_with_zones: set[str] | None = None) -> dict:
    """Map geometry for assets/geo.js.

    - 'zones' / 'provinces': zone polygons and province outlines of the
      provinces in the data (`provinces_with_zones`), drawn and coloured;
    - 'bounds' / 'labels': per concerned province (cropping, labels);
    - 'country': the DRC silhouette for the general view -- the zones of the
      other provinces (coarse, uncoloured backdrop) and every other province's
      outline, plus the DRC bounds. The province pages do not draw it: they
      show their own province only.
    """
    feats = load_zone_features(source)
    every_outline = province_outlines(feats)
    concerned = (provinces_with_zones if provinces_with_zones is not None
                 else {f["properties"]["province"] for f in feats})

    outlines = {"type": "FeatureCollection",
                "features": [f for f in every_outline["features"] if f["properties"]["province"] in concerned]}
    simplified = [f for f in simplify_zones(feats) if f["properties"]["province"] in concerned]

    # DRC backdrop: the other provinces' zones (outer rings only, coarse)
    backdrop = []
    for f in simplify_zones(feats, BACKDROP_TOL):
        prov = f["properties"]["province"]
        if prov in concerned:
            continue
        polys = [[[[round(x, BACKDROP_DECIMALS), round(y, BACKDROP_DECIMALS)] for x, y in poly[0]]]
                 for poly in _polys(f["geometry"]) if poly and _ring_area(poly[0]) > 1e-5]
        if polys:
            backdrop.append({"type": "Feature", "properties": {"province": prov},
                             "geometry": {"type": "MultiPolygon", "coordinates": polys}})
    other_outlines = []
    for f in every_outline["features"]:
        if f["properties"]["province"] in concerned:
            continue
        lines = [[[round(x, BACKDROP_DECIMALS), round(y, BACKDROP_DECIMALS)]
                  for x, y in _douglas_peucker([tuple(c) for c in l], BACKDROP_OUTLINE_TOL)]
                 for l in f["geometry"]["coordinates"]]
        other_outlines.append({"type": "Feature", "properties": f["properties"],
                               "geometry": {"type": "MultiLineString", "coordinates": lines}})

    # label anchor per province: area-weighted centroid of its zones, snapped to
    # the nearest zone centroid so it always lands inside the province
    acc: dict[str, list[float]] = {}
    zone_centres: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for f in simplified:
        p = f["properties"]["province"]
        for poly in _polys(f["geometry"]):
            ring = poly[0]
            a = _ring_area(ring)
            if a <= 0:
                continue
            cx = sum(x for x, _ in ring[:-1]) / (len(ring) - 1)
            cy = sum(y for _, y in ring[:-1]) / (len(ring) - 1)
            t = acc.setdefault(p, [0.0, 0.0, 0.0])
            t[0] += a * cx
            t[1] += a * cy
            t[2] += a
            zone_centres[p].append((cx, cy))
    labels = {}
    for p, (sx, sy, a) in acc.items():
        gx, gy = sx / a, sy / a
        best = min(zone_centres[p], key=lambda c: (c[0] - gx) ** 2 + (c[1] - gy) ** 2)
        labels[p] = [round(best[0], 3), round(best[1], 3)]

    bounds = {}
    for p in sorted({f["properties"]["province"] for f in simplified}):
        bounds[p] = _bounds_of([f for f in simplified if f["properties"]["province"] == p])
    return {
        "zones": {"type": "FeatureCollection", "features": simplified},
        "provinces": outlines,
        "bounds": bounds,
        "labels": labels,
        "country": {
            "name": "République démocratique du Congo",
            "zones": {"type": "FeatureCollection", "features": backdrop},
            "outlines": {"type": "FeatureCollection", "features": other_outlines},
            "bounds": _bounds_of(simplified + backdrop),
        },
    }
