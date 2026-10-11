"""Tiny polygon-shapefile writer used only by the tests (inverse of the reader)."""

import struct
from pathlib import Path

WGS84 = ('GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],'
         'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]')


def write_polygons(base: Path, records: list[tuple[list[list[list[float]]], dict]]) -> Path:
    """records: [(rings in shapefile orientation (outer CW, holes CCW), {Nom, PROVINCE, ZSCode})]."""
    shp_recs, shx = [], []
    offset = 50  # 16-bit words, after the 100-byte header
    all_x = [x for rings, _ in records for r in rings for x, _ in r]
    all_y = [y for rings, _ in records for r in rings for _, y in r]
    bbox = (min(all_x), min(all_y), max(all_x), max(all_y))
    for i, (rings, _) in enumerate(records, start=1):
        pts = [p for r in rings for p in r]
        parts, k = [], 0
        for r in rings:
            parts.append(k)
            k += len(r)
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        content = struct.pack("<i4d2i", 5, min(xs), min(ys), max(xs), max(ys), len(rings), len(pts))
        content += struct.pack(f"<{len(parts)}i", *parts)
        content += struct.pack(f"<{2 * len(pts)}d", *[c for p in pts for c in p])
        shp_recs.append(struct.pack(">2i", i, len(content) // 2) + content)
        shx.append(struct.pack(">2i", offset, len(content) // 2))
        offset += 4 + len(content) // 2

    def header(length_words):
        return (struct.pack(">7i", 9994, 0, 0, 0, 0, 0, length_words)
                + struct.pack("<2i", 1000, 5) + struct.pack("<4d", *bbox) + struct.pack("<4d", 0, 0, 0, 0))

    body = b"".join(shp_recs)
    base.with_suffix(".shp").write_bytes(header(50 + len(body) // 2) + body)
    base.with_suffix(".shx").write_bytes(header(50 + 4 * len(shx)) + b"".join(shx))

    fields = [("Nom", 40), ("PROVINCE", 30), ("ZSCode", 15)]
    rec_len = 1 + sum(n for _, n in fields)
    hdr_len = 32 + 32 * len(fields) + 1
    dbf = struct.pack("<B3BIHH20x", 3, 126, 10, 3, len(records), hdr_len, rec_len)
    for name, n in fields:
        dbf += name.encode().ljust(11, b"\0") + b"C" + b"\0" * 4 + bytes([n, 0]) + b"\0" * 14
    dbf += b"\r"
    for _, props in records:
        dbf += b" " + b"".join(str(props.get(name, "")).encode("utf-8")[:n].ljust(n, b" ") for name, n in fields)
    dbf += b"\x1a"
    base.with_suffix(".dbf").write_bytes(dbf)
    base.with_suffix(".prj").write_text(WGS84)
    base.with_suffix(".cpg").write_text("UTF-8")
    return base.with_suffix(".shp")


def cw_square(x0, y0, x1, y1):
    """Clockwise closed square (shapefile outer-ring orientation)."""
    return [[x0, y0], [x0, y1], [x1, y1], [x1, y0], [x0, y0]]


def ccw_square(x0, y0, x1, y1):
    return cw_square(x0, y0, x1, y1)[::-1]
