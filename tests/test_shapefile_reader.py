import pytest

from common.geo import build_geo, load_zone_features
from common.shapefile_reader import read_shapefile
from tests.shapefile_writer import ccw_square, cw_square, write_polygons


@pytest.fixture
def shp(tmp_path):
    return write_polygons(tmp_path / "DRC_Health_zones", [
        # zone with a hole
        ([cw_square(0, 0, 1, 1), ccw_square(0.4, 0.4, 0.6, 0.6)], {"Nom": "Kasaï A", "PROVINCE": "Kasaï", "ZSCode": "z1"}),
        # two-part zone (MultiPolygon)
        ([cw_square(1, 0, 2, 1), cw_square(3, 0, 3.5, 0.5)], {"Nom": "B", "PROVINCE": "Kasaï", "ZSCode": "z2"}),
        ([cw_square(0, 1, 1, 2)], {"Nom": "C", "PROVINCE": "Lomami", "ZSCode": "z3"}),
    ])


def test_reads_attributes_and_geometry(shp):
    feats = read_shapefile(shp)
    assert [f["properties"]["Nom"] for f in feats] == ["Kasaï A", "B", "C"]  # UTF-8 via .cpg
    assert feats[0]["properties"]["PROVINCE"] == "Kasaï"
    a, b, c = (f["geometry"] for f in feats)
    assert a["type"] == "Polygon" and len(a["coordinates"]) == 2      # outer + hole
    assert b["type"] == "MultiPolygon" and len(b["coordinates"]) == 2
    assert c["type"] == "Polygon"


def test_outer_rings_become_counter_clockwise(shp):
    ring = read_shapefile(shp)[2]["geometry"]["coordinates"][0]
    area = sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, ring[1:])) / 2
    assert area > 0


def test_rejects_projected_coordinates(shp):
    shp.with_suffix(".prj").write_text('PROJCS["WGS_1984_UTM_Zone_35N",GEOGCS["GCS_WGS_1984"]]')
    with pytest.raises(ValueError):
        read_shapefile(shp)


def test_columns_are_mapped_for_the_dashboard(shp):
    props = [f["properties"] for f in load_zone_features(shp)]
    assert props[0] == {"nom": "Kasaï A", "province": "Kasaï", "zscode": "z1"}


def test_build_geo_from_shapefile(shp):
    geo = build_geo(shp, {"Kasaï"})
    assert {f["properties"]["nom"] for f in geo["zones"]["features"]} == {"Kasaï A", "B"}
    # only the concerned province is drawn (no other province / country)
    assert {f["properties"]["province"] for f in geo["provinces"]["features"]} == {"Kasaï"}
