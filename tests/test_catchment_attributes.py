"""bench.catchments.attributes (D-032): pinned catchment attributes and Norway outline."""
import csv
import json
import math
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import catchment_attributes as ca  # noqa: E402

MAX_OUTLINE_BYTES = 200 * 1024


def meridian_arc(lat_deg: float) -> float:
    """Meridian distance on GRS80 from the equator, by direct numerical integration."""
    a, f = 6378137.0, 1 / 298.257222101
    e2 = f * (2 - f)
    steps, total = 20000, 0.0
    phi_end = math.radians(lat_deg)
    for i in range(steps):
        phi = (i + 0.5) * phi_end / steps
        total += a * (1 - e2) / (1 - e2 * math.sin(phi) ** 2) ** 1.5 * phi_end / steps
    return total


class CatchmentAttributesTest(unittest.TestCase):
    def test_bench_catchments_attributes_lean_module_is_current(self):
        proc = subprocess.run([sys.executable, str(ROOT / "scripts/catchment_attributes.py"),
                               "--check"], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_bench_catchments_attributes_cover_the_regime_table(self):
        with ca.ATTRIBUTES.open(newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual([r["station"] for r in rows], ca.regime_stations())
        self.assertEqual(len(rows), 109)
        for r in rows:
            self.assertTrue(all(r[k] for k in ("lat", "lon", "elev_mean_m", "area_km2")), r)
            self.assertTrue(57 <= float(r["lat"]) <= 72 and 4 <= float(r["lon"]) <= 32, r)

    def test_bench_catchments_outline_is_small_mainland_and_public_domain(self):
        self.assertLessEqual(ca.OUTLINE.stat().st_size, MAX_OUTLINE_BYTES)
        geometry = json.loads(ca.OUTLINE.read_text())["features"][0]["geometry"]
        self.assertEqual(geometry["type"], "MultiPolygon")
        for polygon in geometry["coordinates"]:
            for lon, lat in polygon[0]:
                self.assertTrue(4 <= lon <= 32 and 57 <= lat <= 72, (lon, lat))
        sources = ca.SOURCES.read_text()
        self.assertIn("public domain", sources)
        self.assertIn("Natural Earth", sources)

    def test_bench_catchments_utm33_inverse_on_the_central_meridian(self):
        for lat in (58.0, 62.5, 69.7):
            got_lat, got_lon = ca.utm33_to_wgs84(500000.0, 0.9996 * meridian_arc(lat))
            self.assertAlmostEqual(got_lon, 15.0, places=9)
            self.assertAlmostEqual(got_lat, lat, places=6)  # about 0.1 m

    def test_bench_catchments_utm33_inverse_off_the_meridian_is_symmetric(self):
        north = 0.9996 * meridian_arc(61.0)
        west = ca.utm33_to_wgs84(400000.0, north)
        east = ca.utm33_to_wgs84(600000.0, north)
        self.assertAlmostEqual(west[0], east[0], places=9)
        self.assertAlmostEqual(15.0 - west[1], east[1] - 15.0, places=9)

    def test_bench_catchments_centroid_of_a_square_with_a_hole(self):
        outer = [(0, 0), (0, 4), (4, 4), (4, 0)]          # clockwise, as in shapefiles
        hole = [(0, 0), (1, 0), (1, 1), (0, 1)]           # counter-clockwise hole in a corner
        x, y = ca.polygon_centroid([outer, hole])
        self.assertAlmostEqual(x, (16 * 2 - 1 * 0.5) / 15)
        self.assertAlmostEqual(y, (16 * 2 - 1 * 0.5) / 15)

    def test_bench_catchments_douglas_peucker_keeps_corners_drops_noise(self):
        line = [(0, 0), (1, 0.001), (2, 0), (2, 1), (2.001, 2), (2, 3)]
        self.assertEqual(ca.douglas_peucker(line, 0.01), [(0, 0), (2, 0), (2, 3)])


if __name__ == "__main__":
    unittest.main()
