import csv
import random
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class SmokeDrawTest(unittest.TestCase):
    def test_seeded_mountain_draw_matches_lean_station(self):
        with (ROOT / "data/regime/mon_Q_regime.csv").open(newline="") as source:
            rows = csv.DictReader(source, delimiter=" ", skipinitialspace=True)
            mountain_stations = [
                row["st_id"] for row in rows if row["regime"] == "1"
            ]

        chosen_station = random.Random(20261008).choice(mountain_stations)
        catalog = (ROOT / "ShyftBench/Catalog.lean").read_text()
        match = re.search(
            r'^def smokeStation : StationId := "([^"]+)"$',
            catalog,
            re.MULTILINE,
        )
        self.assertIsNotNone(match, "Lean smokeStation declaration is missing")
        self.assertEqual(chosen_station, match.group(1))


if __name__ == "__main__":
    unittest.main()
