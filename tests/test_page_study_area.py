"""bench.dashboard, page study-area (D-032): regime map and variance shares by regime."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from matplotlib.colors import to_rgb

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import canon, maps, page_study_area as page, render, table  # noqa: E402
from pipeline.figures import table_csv  # noqa: E402

STATIONS = [s["id"] for s in canon.load()["stations"]]
REGIME = {s["id"]: s["regime"] for s in canon.load()["stations"]}
KEYS = [k for k, _, _ in page.SHARES]


def share(station: str, key: str) -> float:
    i = STATIONS.index(station)
    seasonal = 0.1 + 0.005 * i
    return {"variance_share_seasonal": seasonal, "variance_share_interannual": 0.1,
            "variance_share_irregular": 0.8 - seasonal}[key]


def shares_table(stations=STATIONS, override=None, models=("ptstk", "rpmstk")) -> pd.DataFrame:
    override = override or {}
    rows = [("e", model, goal, "seNorge", "forward", pcorr, "bobyqa", None, station, "validation",
             key, override.get((model, station, key), share(station, key)), 10, "", "")
            for model in models for goal in ("kge", "nse") for pcorr in (False, True)
            for station in stations for key in KEYS]
    return pd.DataFrame(rows, columns=table.COLUMNS)


def spec_for(view: str) -> dict:
    return next(f for f in canon.load()["pageFigures"] if f["view"] == view)


def axes_of(fn, *args):
    real = page.plt.subplots
    box = {}

    def capture(*a, **k):
        box["fa"] = real(*a, **k)
        return box["fa"]

    with patch.object(page.plt, "subplots", side_effect=capture):
        svg = fn(*args)
    return svg, box["fa"][1]


class RegimeMapTest(unittest.TestCase):
    def test_bench_dashboard_regime_map_marks_every_regime_station_once_in_regime_colours(self):
        spec = spec_for("regime-map")
        frame = page.regime_map_table(pd.DataFrame(columns=table.COLUMNS), spec)
        self.assertEqual(list(frame["station"]), STATIONS)
        location = maps.load_attributes()
        self.assertTrue(all((r.lat, r.lon) == location[r.station] for r in frame.itertuples()))
        svg, ax = axes_of(page.render_regime_map, frame, spec)
        markers = ax.collections
        regimes = canon.load()["regimes"]
        self.assertEqual(sum(len(c.get_offsets()) for c in markers), len(STATIONS))
        for collection, regime in zip(markers, regimes):
            self.assertTrue(np.allclose(collection.get_facecolor()[0][:3], to_rgb(regime["colour"])),
                            regime["name"])
        labels = [t.get_text() for t in ax.get_legend().get_texts()]
        counts = {r["name"]: sum(REGIME[s] == r["name"] for s in STATIONS) for r in regimes}
        self.assertEqual(labels, [f"{r['name']} ({counts[r['name']]})" for r in regimes])
        self.assertTrue(all(s not in t.get_text() for t in ax.texts for s in STATIONS))
        self.assertLessEqual(len(svg), canon.load()["sizeLimits"]["svgBytes"])


class VarianceTest(unittest.TestCase):
    def test_bench_dashboard_variance_medians_per_regime_from_the_observed_value(self):
        frame = page.variance_table(shares_table(), spec_for("variance-by-regime"))
        order = [r["name"] for r in canon.load()["regimes"]]
        self.assertEqual(list(frame["regime"]), order)
        mountain = [s for s in STATIONS if REGIME[s] == "Mountain"]
        row = frame[frame["regime"] == "Mountain"].iloc[0]
        self.assertEqual(row["n_catchments"], len(mountain))
        self.assertAlmostEqual(row["median_variance_share_seasonal"],
                               float(np.median([share(s, "variance_share_seasonal") for s in mountain])))
        self.assertNotIn("station", frame.columns)

    def test_bench_dashboard_variance_drops_catchments_without_all_three_shares(self):
        first = [s for s in STATIONS if REGIME[s] == "Inland"][0]
        override = {(m, first, "variance_share_interannual"): np.nan for m in ("ptstk", "rpmstk")}
        frame = page.variance_table(shares_table(override=override), spec_for("variance-by-regime"))
        inland = sum(REGIME[s] == "Inland" for s in STATIONS)
        self.assertEqual(frame[frame["regime"] == "Inland"]["n_catchments"].iloc[0], inland - 1)

    def test_bench_dashboard_variance_stops_when_runs_disagree(self):
        override = {("rpmstk", STATIONS[0], "variance_share_seasonal"): 0.9}
        with self.assertRaises(ValueError):
            page.variance_table(shares_table(override=override), spec_for("variance-by-regime"))

    def test_bench_dashboard_variance_bars_stack_the_three_medians(self):
        spec = spec_for("variance-by-regime")
        frame = page.variance_table(shares_table(), spec)
        svg, ax = axes_of(page.render_variance, frame, spec)
        bars = ax.patches
        self.assertEqual(len(bars), 3 * len(frame))
        first = frame.iloc[0]
        heights = [bars[i * len(frame)].get_height() for i in range(3)]
        np.testing.assert_allclose(heights, [first[f"median_{k}"] for k in KEYS])
        self.assertEqual(svg, page.render_variance(frame, spec), "deterministic")
        self.assertLessEqual(len(svg), canon.load()["sizeLimits"]["svgBytes"])
        self.assertLessEqual(len(table_csv(frame)), canon.load()["sizeLimits"]["csvBytes"])


class DispatchTest(unittest.TestCase):
    def test_bench_dashboard_every_published_page_view_has_a_renderer(self):
        by_id = {f["id"]: f for f in canon.load()["pageFigures"]}
        views = {by_id[i]["view"] for p in canon.load()["pages"] if p["status"] == "published"
                 for i in p["figures"]}
        self.assertLessEqual(views, set(render.RENDERERS))


if __name__ == "__main__":
    unittest.main()
