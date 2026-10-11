"""Minimal ESRI shapefile reader (standard library only).

Reads the health-zone shapefile of BDBV2026-Data
(data/shapefiles/DRC_Health_zones.{shp,dbf,shx,prj,cpg}) into GeoJSON-like
features, so the dashboard needs neither pyshp/geopandas nor the derived
build/drc_health_zones.geojson.

Supported: shape types Polygon (5), PolygonZ (15), PolygonM (25); dBASE III
attribute table; the .cpg codepage (UTF-8 for this shapefile). The .prj must
be geographic WGS84 (lon/lat degrees) -- anything else raises, because the
map projection assumes degrees.
"""

from __future__ import annotations

import struct
from pathlib import Path

POLYGON_TYPES = {5, 15, 25}


def _signed_area(ring: list[list[float]]) -> float:
    s = 0.0
    for (x1, y1), (x2, y2) in zip(ring, ring[1:]):
        s += x1 * y2 - x2 * y1
    return s / 2


def _point_in_ring(x: float, y: float, ring: list[list[float]]) -> bool:
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-300) + xi:
            inside = not inside
        j = i
    return inside


def _rings_to_geometry(rings: list[list[list[float]]]) -> dict | None:
    """Shapefile rings -> GeoJSON Polygon/MultiPolygon.

    Shapefile convention: outer rings are clockwise (negative signed area),
    holes counter-clockwise. Each hole is attached to the outer ring that
    contains its first vertex. GeoJSON wants outer rings counter-clockwise.
    """
    outers, holes = [], []
    for r in rings:
        if len(r) < 4:
            continue
        (outers if _signed_area(r) < 0 else holes).append(r)
    if not outers and holes:  # badly oriented file: treat everything as outer
        outers, holes = holes, []
    polys = [[o[::-1]] for o in outers]  # clockwise -> counter-clockwise
    for h in holes:
        x, y = h[0]
        target = next((p for p in polys if _point_in_ring(x, y, p[0])), None)
        if target is not None:
            target.append(h[::-1])  # CCW -> CW for GeoJSON holes
        else:
            polys.append([h])
    if not polys:
        return None
    if len(polys) == 1:
        return {"type": "Polygon", "coordinates": polys[0]}
    return {"type": "MultiPolygon", "coordinates": polys}


def read_dbf(path: Path, encoding: str = "utf-8") -> list[dict]:
    data = path.read_bytes()
    n_records, header_len, record_len = struct.unpack("<xxxxIHH", data[:12])
    fields = []
    pos = 32
    while data[pos] != 0x0D:
        name = data[pos:pos + 11].split(b"\0")[0].decode("ascii")
        ftype = chr(data[pos + 11])
        flen = data[pos + 16]
        fields.append((name, ftype, flen))
        pos += 32
    rows = []
    for i in range(n_records):
        rec = data[header_len + i * record_len: header_len + (i + 1) * record_len]
        if rec[:1] == b"*":  # deleted record
            rows.append(None)
            continue
        off = 1
        row = {}
        for name, ftype, flen in fields:
            raw = rec[off:off + flen].decode(encoding, errors="replace").strip()
            off += flen
            if ftype in "NF" and raw:
                try:
                    row[name] = float(raw) if "." in raw else int(raw)
                except ValueError:
                    row[name] = raw
            else:
                row[name] = raw
        rows.append(row)
    return rows


def read_shp(path: Path) -> list[dict | None]:
    data = path.read_bytes()
    file_code, = struct.unpack(">i", data[:4])
    if file_code != 9994:
        raise ValueError(f"{path}: not a shapefile (file code {file_code})")
    shape_type, = struct.unpack("<i", data[32:36])
    if shape_type not in POLYGON_TYPES:
        raise ValueError(f"{path}: shape type {shape_type} is not a polygon type")
    geoms: list[dict | None] = []
    pos = 100
    end = len(data)
    while pos + 8 <= end:
        _, content_len = struct.unpack(">ii", data[pos:pos + 8])
        content = data[pos + 8: pos + 8 + content_len * 2]
        pos += 8 + content_len * 2
        rec_type, = struct.unpack("<i", content[:4])
        if rec_type == 0:  # null shape
            geoms.append(None)
            continue
        n_parts, n_points = struct.unpack("<ii", content[36:44])
        parts = list(struct.unpack(f"<{n_parts}i", content[44:44 + 4 * n_parts]))
        pts_off = 44 + 4 * n_parts
        coords = struct.unpack(f"<{2 * n_points}d", content[pts_off:pts_off + 16 * n_points])
        xy = [[coords[2 * k], coords[2 * k + 1]] for k in range(n_points)]
        bounds = parts + [n_points]
        rings = [xy[bounds[k]:bounds[k + 1]] for k in range(n_parts)]
        geoms.append(_rings_to_geometry(rings))
    return geoms


def read_shapefile(shp_path: Path) -> list[dict]:
    """Features {'type': 'Feature', 'geometry': ..., 'properties': {dbf row}}."""
    shp_path = Path(shp_path)
    base = shp_path.with_suffix("")
    prj = base.with_suffix(".prj")
    if prj.exists():
        wkt = prj.read_text(encoding="ascii", errors="replace")
        if not wkt.startswith("GEOGCS") or "WGS" not in wkt.upper():
            raise ValueError(f"{prj}: expected geographic WGS84 coordinates, got {wkt[:60]}…")
    cpg = base.with_suffix(".cpg")
    encoding = cpg.read_text(encoding="ascii").strip() if cpg.exists() else "utf-8"
    encoding = {"UTF-8": "utf-8", "UTF8": "utf-8"}.get(encoding.upper(), encoding)
    rows = read_dbf(base.with_suffix(".dbf"), encoding)
    geoms = read_shp(shp_path)
    if len(rows) != len(geoms):
        raise ValueError(f"{shp_path}: {len(geoms)} shapes but {len(rows)} dbf records")
    return [
        {"type": "Feature", "geometry": g, "properties": r}
        for g, r in zip(geoms, rows)
        if g is not None and r is not None
    ]
