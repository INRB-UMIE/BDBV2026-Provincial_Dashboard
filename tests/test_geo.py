"""Geometry helpers: province outlines and arc-consistent simplification."""

import json

from common.geo import build_geo, province_outlines, simplify_zones


def sq(x0, y0, x1, y1, extra=()):
    ring = [[x0, y0], [x1, y0], *extra, [x1, y1], [x0, y1], [x0, y0]]
    return {"type": "Polygon", "coordinates": [ring]}


def feat(nom, prov, geom):
    return {"type": "Feature", "properties": {"nom": nom, "province": prov}, "geometry": geom}


def segments(fc, prov):
    f = next(f for f in fc["features"] if f["properties"]["province"] == prov)
    return [tuple(map(tuple, (a, b))) for line in f["geometry"]["coordinates"] for a, b in zip(line, line[1:])]


def test_shared_edge_inside_a_province_is_not_an_outline():
    fc = province_outlines([feat("A", "P", sq(0, 0, 1, 1)), feat("B", "P", sq(1, 0, 2, 1))])
    segs = segments(fc, "P")
    # no outline segment on the shared x=1 border
    assert not any(a[0] == 1 and b[0] == 1 for a, b in segs)


def test_edge_between_two_provinces_is_kept_for_both():
    fc = province_outlines([feat("A", "P", sq(0, 0, 1, 1)), feat("B", "Q", sq(1, 0, 2, 1))])
    for prov in ("P", "Q"):
        assert any(a[0] == 1 and b[0] == 1 for a, b in segments(fc, prov))


def test_slightly_offset_interior_edge_is_dropped():
    # B's left edge sits 0.0005 deg (~55 m) inside A: not an exact duplicate
    fc = province_outlines([feat("A", "P", sq(0, 0, 1, 1)), feat("B", "P", sq(0.9995, 0, 2, 1))])
    segs = segments(fc, "P")
    assert not any(0.99 < a[0] < 1.01 and 0.99 < b[0] < 1.01 for a, b in segs)


def test_shared_arc_is_simplified_identically_on_both_sides():
    # a wiggly shared border (x≈1) between two zones
    wiggle = [[1.0, y / 10] for y in range(1, 10)]
    wiggle = [[1.0 + (0.0003 if i % 2 else 0), y] for i, (_, y) in enumerate(wiggle)]
    a = {"type": "Polygon", "coordinates": [[[0, 0], [1, 0], *wiggle, [1, 1], [0, 1], [0, 0]]]}
    b = {"type": "Polygon", "coordinates": [[[1, 0], [2, 0], [2, 1], [1, 1], *wiggle[::-1], [1, 0]]]}
    za, zb = simplify_zones([feat("A", "P", a), feat("B", "P", b)])
    border_a = {tuple(p) for p in za["geometry"]["coordinates"][0] if 0.99 < p[0] < 1.01}
    border_b = {tuple(p) for p in zb["geometry"]["coordinates"][0] if 0.99 < p[0] < 1.01}
    assert border_a == border_b


def test_build_geo_keeps_only_the_concerned_provinces(tmp_path):
    src = tmp_path / "z.geojson"
    src.write_text(json.dumps({"type": "FeatureCollection", "features": [
        {**feat("A", "P", sq(0, 0, 1, 1)), "properties": {"nom": "A", "province": "P", "zscode": "x"}},
        {**feat("B", "Q", sq(1, 0, 2, 1)), "properties": {"nom": "B", "province": "Q", "zscode": "y"}},
    ]}))
    geo = build_geo(src, {"P"})
    assert [f["properties"]["nom"] for f in geo["zones"]["features"]] == ["A"]
    assert {f["properties"]["province"] for f in geo["provinces"]["features"]} == {"P"}
    # the outline of P still includes its border with the (not drawn) province Q
    assert any(a[0] == 1 and b[0] == 1 for a, b in segments(geo["provinces"], "P"))
    assert geo["bounds"]["P"] == [0, 0, 1, 1]
    assert "P" in geo["labels"]
    # the rest of the DRC is only a backdrop (general view silhouette)
    country = geo["country"]
    assert [f["properties"]["province"] for f in country["zones"]["features"]] == ["Q"]
    assert "nom" not in country["zones"]["features"][0]["properties"]
    assert {f["properties"]["province"] for f in country["outlines"]["features"]} == {"Q"}
    assert country["bounds"] == [0, 0, 2, 1]
