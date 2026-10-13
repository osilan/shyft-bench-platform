#!/usr/bin/env python3
"""Pinned catchment attributes and Norway outline (bench.catchments.attributes, D-032).

Two steps, standard library only:

    python3 scripts/catchment_attributes.py extract   # once, locally: legacy GIS -> data/catchments/
    python3 scripts/catchment_attributes.py           # data/catchments/ -> ShyftBench/Generated/Catchments.lean
    python3 scripts/catchment_attributes.py --check   # fail if the Lean module is stale

`extract` reads, from ../shyft-hydro-benchmarking (or $SHYFT_LEGACY_ROOT):
  - the NVE catchment polygons (shyft-data/Data/GIS/*_all_attributes.shp, ETRS89 / UTM 33N):
    latitude and longitude of each polygon's centroid, and NVE's `areal_km2`;
  - lstm_baseline/data/attributes/attributes.csv: mean elevation, the only source for it; its
    latitude, longitude and area are checked against the polygons;
  - Natural Earth 1:10m admin-0 countries (shyft-data/Data/GIS/ne_10m_countries): Norway's
    mainland polygons, simplified.
It writes data/catchments/attributes.csv (regime-table order), norway_outline.geojson and
SOURCES.md. The generator step reads only those committed files, so CI can check it.
"""
import csv
import hashlib
import json
import math
import os
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REGIME_CSV = ROOT / "data/regime/mon_Q_regime.csv"
OUT_DIR = ROOT / "data/catchments"
ATTRIBUTES = OUT_DIR / "attributes.csv"
OUTLINE = OUT_DIR / "norway_outline.geojson"
SOURCES = OUT_DIR / "SOURCES.md"
LEAN = ROOT / "ShyftBench/Generated/Catchments.lean"

NVE_LAYERS = ("calibration_catchment_86_all_attributes", "validation_catchment_26_all_attributes")
NE_LAYER = "ne_10m_countries/ne_10m_admin_0_countries"
MAX_CENTROID_KM = 0.1          # attributes.csv against the NVE polygon centroid
MAX_AREA_REL = 0.01            # attributes.csv against NVE areal_km2
MAINLAND_LAT = (57.0, 72.0)    # Norway's mainland parts: Svalbard (north) and
MAINLAND_LON = (4.0, 32.0)     # Jan Mayen (west) fall outside and are dropped
SIMPLIFY_DEG = 0.01            # Douglas-Peucker tolerance, about 1 km
MIN_RING_POINTS = 4


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def station_id(raw: str) -> str:
    """Legacy ids carry a trailing point number: `178.1.0` is station `178.1`."""
    return re.sub(r"\.0$", "", raw.strip())


def regime_stations() -> list[str]:
    with REGIME_CSV.open(newline="") as f:
        reader = csv.reader(f, delimiter=" ")
        next(reader)
        return [row[1] for row in reader]


# ── shapefile reading (dBASE + polygon shapes) ────────────────────────────────

def read_dbf(path: Path) -> list[dict[str, str]]:
    data = path.read_bytes()
    count, header_len, record_len = struct.unpack("<IHH", data[4:12])
    fields = [(data[i:i + 11].split(b"\0")[0].decode(), data[i + 16])
              for i in range(32, header_len - 1, 32)]
    records = []
    for k in range(count):
        offset = header_len + k * record_len + 1
        record = {}
        for name, length in fields:
            # Fields are padded with spaces (NVE) or NUL bytes (Natural Earth).
            record[name] = data[offset:offset + length].decode("latin1").strip(" \0")
            offset += length
        records.append(record)
    return records


def read_polygons(path: Path) -> list[list[list[tuple[float, float]]]]:
    """Each record's rings as lists of (x, y); a null shape gives no rings."""
    data = path.read_bytes()
    offset, shapes = 100, []
    while offset < len(data):
        _, length = struct.unpack(">ii", data[offset:offset + 8])
        record = data[offset + 8:offset + 8 + 2 * length]
        offset += 8 + 2 * length
        if struct.unpack("<i", record[:4])[0] == 0:
            shapes.append([])
            continue
        n_parts, n_points = struct.unpack("<ii", record[36:44])
        parts = list(struct.unpack(f"<{n_parts}i", record[44:44 + 4 * n_parts]))
        start = 44 + 4 * n_parts
        points = [struct.unpack("<2d", record[start + 16 * i:start + 16 * i + 16])
                  for i in range(n_points)]
        shapes.append([points[a:b] for a, b in zip(parts, parts[1:] + [n_points])])
    return shapes


def ring_area_centroid(ring):
    area = cx = cy = 0.0
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        cross = x0 * y1 - x1 * y0
        area += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    return area / 2, cx, cy


def polygon_centroid(rings) -> tuple[float, float]:
    """Area-weighted centroid; hole rings have the opposite winding and subtract."""
    area = cx = cy = 0.0
    for ring in rings:
        a, x, y = ring_area_centroid(ring)
        area, cx, cy = area + a, cx + x, cy + y
    return cx / (6 * area), cy / (6 * area)


def utm33_to_wgs84(easting: float, northing: float) -> tuple[float, float]:
    """Inverse transverse Mercator on GRS80 (ETRS89 / UTM zone 33N); ETRS89 equals WGS84 to
    well under a metre, far below a map marker."""
    a, f, k0, lon0 = 6378137.0, 1 / 298.257222101, 0.9996, math.radians(15)
    e2 = f * (2 - f)
    ep2 = e2 / (1 - e2)
    mu = northing / k0 / (a * (1 - e2 / 4 - 3 * e2 ** 2 / 64 - 5 * e2 ** 3 / 256))
    e1 = (1 - math.sqrt(1 - e2)) / (1 + math.sqrt(1 - e2))
    phi = (mu + (3 * e1 / 2 - 27 * e1 ** 3 / 32) * math.sin(2 * mu)
           + (21 * e1 ** 2 / 16 - 55 * e1 ** 4 / 32) * math.sin(4 * mu)
           + (151 * e1 ** 3 / 96) * math.sin(6 * mu) + (1097 * e1 ** 4 / 512) * math.sin(8 * mu))
    c, t = ep2 * math.cos(phi) ** 2, math.tan(phi) ** 2
    n = a / math.sqrt(1 - e2 * math.sin(phi) ** 2)
    r = a * (1 - e2) / (1 - e2 * math.sin(phi) ** 2) ** 1.5
    d = (easting - 500000) / (n * k0)
    lat = phi - (n * math.tan(phi) / r) * (
        d ** 2 / 2 - (5 + 3 * t + 10 * c - 4 * c ** 2 - 9 * ep2) * d ** 4 / 24
        + (61 + 90 * t + 298 * c + 45 * t ** 2 - 252 * ep2 - 3 * c ** 2) * d ** 6 / 720)
    lon = lon0 + (d - (1 + 2 * t + c) * d ** 3 / 6
                  + (5 - 2 * c + 28 * t - 3 * c ** 2 + 8 * ep2 + 24 * t ** 2) * d ** 5 / 120
                  ) / math.cos(phi)
    return math.degrees(lat), math.degrees(lon)


def distance_km(lat1, lon1, lat2, lon2) -> float:
    return 111.2 * math.hypot(lat1 - lat2, (lon1 - lon2) * math.cos(math.radians(lat1)))


# ── outline simplification ────────────────────────────────────────────────────

def douglas_peucker(points, tolerance):
    if len(points) < 3:
        return list(points)
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        first, last = stack.pop()
        (x0, y0), (x1, y1) = points[first], points[last]
        dx, dy = x1 - x0, y1 - y0
        norm = math.hypot(dx, dy)
        worst, index = 0.0, None
        for i in range(first + 1, last):
            x, y = points[i]
            dist = (abs(dy * x - dx * y + x1 * y0 - y1 * x0) / norm if norm
                    else math.hypot(x - x0, y - y0))
            if dist > worst:
                worst, index = dist, i
        if index is not None and worst > tolerance:
            keep[index] = True
            stack += [(first, index), (index, last)]
    return [p for p, k in zip(points, keep) if k]


def norway_outline(gis: Path) -> dict:
    records = read_dbf(gis / f"{NE_LAYER}.dbf")
    shapes = read_polygons(gis / f"{NE_LAYER}.shp")
    index = [i for i, r in enumerate(records) if r["ADMIN"] == "Norway"]
    if len(index) != 1:
        sys.exit(f"expected one Norway record in Natural Earth, found {len(index)}")
    polygons = []
    for ring in shapes[index[0]]:
        lat = sum(y for _, y in ring) / len(ring)
        lon = sum(x for x, _ in ring) / len(ring)
        if not (MAINLAND_LAT[0] <= lat <= MAINLAND_LAT[1] and MAINLAND_LON[0] <= lon <= MAINLAND_LON[1]):
            continue
        simplified = douglas_peucker(ring, SIMPLIFY_DEG)
        if len(simplified) >= MIN_RING_POINTS:
            polygons.append([[[round(x, 3), round(y, 3)] for x, y in simplified]])
    return {"type": "FeatureCollection", "features": [{
        "type": "Feature",
        "properties": {"name": "Norway (mainland)", "source": "Natural Earth 1:10m admin-0 countries"},
        "geometry": {"type": "MultiPolygon", "coordinates": polygons}}]}


# ── extract (local) ───────────────────────────────────────────────────────────

def extract() -> None:
    legacy = Path(os.environ.get("SHYFT_LEGACY_ROOT", ROOT.parent / "shyft-hydro-benchmarking"))
    gis = legacy / "shyft-data/Data/GIS"
    lstm_attributes = legacy / "lstm_baseline/data/attributes/attributes.csv"

    nve = {}
    for layer in NVE_LAYERS:
        for record, rings in zip(read_dbf(gis / f"{layer}.dbf"), read_polygons(gis / f"{layer}.shp")):
            lat, lon = utm33_to_wgs84(*polygon_centroid(rings))
            nve[station_id(record["stID"])] = (lat, lon, float(record["areal_km2"]))
    with lstm_attributes.open(newline="") as f:
        lstm = {station_id(r["basin_id"]): r for r in csv.DictReader(f)}

    stations = regime_stations()
    rows, problems = [], []
    for s in stations:
        if s not in nve or s not in lstm:
            problems.append(f"{s}: missing in {'NVE polygons' if s not in nve else 'attributes.csv'}")
            continue
        lat, lon, area = nve[s]
        other = lstm[s]
        km = distance_km(lat, lon, float(other["lat"]), float(other["lon"]))
        rel = abs(float(other["area_km2"]) - area) / area
        if km > MAX_CENTROID_KM:
            problems.append(f"{s}: attributes.csv location is {km:.2f} km from the NVE centroid")
        if rel > MAX_AREA_REL:
            problems.append(f"{s}: attributes.csv area differs from NVE by {rel:.1%}")
        rows.append((s, f"{lat:.5f}", f"{lon:.5f}", f"{float(other['elev_mean']):.1f}", f"{area:.2f}"))
    if problems:
        sys.exit("extract stopped:\n  " + "\n  ".join(problems))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with ATTRIBUTES.open("w", newline="") as f:
        writer = csv.writer(f, lineterminator="\n")
        writer.writerow(["station", "lat", "lon", "elev_mean_m", "area_km2"])
        writer.writerows(rows)
    OUTLINE.write_text(json.dumps(norway_outline(gis), separators=(",", ":")) + "\n")

    version = (gis / f"{NE_LAYER}.VERSION.txt").read_text().strip()
    inputs = [gis / f"{layer}.{ext}" for layer in NVE_LAYERS for ext in ("shp", "dbf")]
    inputs += [lstm_attributes, gis / f"{NE_LAYER}.shp", gis / f"{NE_LAYER}.dbf"]
    lines = "\n".join(f"| `{p.relative_to(legacy)}` | `{sha256(p)}` |" for p in inputs)
    SOURCES.write_text(f"""# Catchment attributes and Norway outline

Generated by `python3 scripts/catchment_attributes.py extract` (bench.catchments.attributes,
D-032). Do not edit by hand.

- `attributes.csv`: one row per station of the frozen regime table, in its order. Latitude and
  longitude (WGS84) are the centroid of the NVE catchment polygon (ETRS89 / UTM 33N); area is
  NVE's `areal_km2`; mean elevation comes from the LSTM baseline's `attributes.csv`, the only
  source for it. That file's location and area agree with the polygons to within
  {MAX_CENTROID_KM} km and {MAX_AREA_REL:.0%}.
- `norway_outline.geojson`: Norway's mainland parts (latitude {MAINLAND_LAT[0]:.0f} to
  {MAINLAND_LAT[1]:.0f}, longitude {MAINLAND_LON[0]:.0f} to {MAINLAND_LON[1]:.0f}) from Natural Earth 1:10m admin-0 countries, version {version}, simplified
  with Douglas-Peucker at {SIMPLIFY_DEG} degrees. Natural Earth is in the public domain
  (https://www.naturalearthdata.com/about/terms-of-use/).

Inputs, below `../shyft-hydro-benchmarking/`:

| File | SHA-256 |
|---|---|
{lines}
""")
    print(f"wrote {len(rows)} stations, {OUTLINE.stat().st_size} byte outline, {SOURCES.name}")


# ── generate (CI) ─────────────────────────────────────────────────────────────

def render() -> str:
    with ATTRIBUTES.open(newline="") as f:
        rows = list(csv.DictReader(f))
    body = ",\n".join(f'  ("{r["station"]}", {r["lat"]}, {r["lon"]}, {r["elev_mean_m"]}, {r["area_km2"]})'
                      for r in rows)
    version = re.search(r"version (\S+),", SOURCES.read_text()).group(1)
    return f"""-- GENERATED by scripts/catchment_attributes.py from data/catchments/. Do not edit.
import ShyftBench.Domain

namespace ShyftBench.Generated

/-- SHA-256 of `data/catchments/attributes.csv`. -/
def attributesCsvSha256 : String := "{sha256(ATTRIBUTES)}"

/-- SHA-256 of `data/catchments/norway_outline.geojson`. -/
def outlineSha256 : String := "{sha256(OUTLINE)}"

/-- SHA-256 of `scripts/catchment_attributes.py`, the script that produced both files. -/
def attributesScriptSha256 : String := "{sha256(Path(__file__).resolve())}"

/-- Source and licence of the outline. -/
def outlineSource : String := "Natural Earth 1:10m admin-0 countries {version}"
def outlineLicence : String := "public domain"

/-- Station id, latitude and longitude (WGS84, polygon centroid), mean elevation (m) and area
(km²), in regime-table order. -/
def attributeRows : List (String × Float × Float × Float × Float) := [
{body}
]

end ShyftBench.Generated
"""


def main() -> None:
    args = sys.argv[1:]
    if args[:1] == ["extract"]:
        extract()
        return
    text = render()
    if "--check" in args:
        if not LEAN.exists() or LEAN.read_text() != text:
            sys.exit(f"{LEAN.relative_to(ROOT)} is stale: run scripts/catchment_attributes.py")
        print("catchment attributes up to date")
        return
    LEAN.write_text(text)
    print(f"wrote {LEAN.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
