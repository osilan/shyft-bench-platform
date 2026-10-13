"""bench.dashboard, page models-pcorr (D-032): per-catchment CDFs, pcorr comparison, regime boxes, map."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import canon, maps, page_models_pcorr as page, render, table  # noqa: E402
from pipeline.figures import table_csv  # noqa: E402

STATIONS = [s["id"] for s in canon.load()["stations"]]
REGIME = {s["id"]: s["regime"] for s in canon.load()["stations"]}
METRICS = ("kge_gupta_2009", "kge_1_over_q", "nse_interannual", "nse_seasonal", "pbias")
MODELS = ("ptstk", "rpmstk", "ptgsk", "rpmgsk", "ptsthbv")


def value(model: str, station: str, metric: str, pcorr: bool) -> float:
    """A deterministic synthetic value, distinct per model, station, metric and arm."""
    m, s, k = MODELS.index(model), STATIONS.index(station), METRICS.index(metric)
    return round(0.1 * m + 0.004 * s + 0.01 * k + (0.05 if pcorr else 0.0), 6)


def metrics_table(stations=STATIONS[:12], models=MODELS, override=None, seed=None) -> pd.DataFrame:
    override = override or {}
    rows = []
    for model in models:
        for station in stations:
            for metric in METRICS:
                for pcorr in (False, True):
                    v = override.get((model, station, metric, pcorr), value(model, station, metric, pcorr))
                    rows.append(("e", model, "kge", "seNorge", "forward", pcorr, "bobyqa", seed,
                                 station, "validation", metric, v, 10, "", ""))
    return pd.DataFrame(rows, columns=table.COLUMNS)


def spec_for(view: str, pcorr=None) -> dict:
    return next(f for f in canon.load()["pageFigures"] if f["view"] == view and f["pcorr"] == pcorr)


def captured_axes(fn, *args):
    """Run a renderer and return its SVG and the axes of its figure."""
    real = page.plt.subplots
    box = {}

    def capture(*a, **k):
        box["fig_axes"] = real(*a, **k)
        return box["fig_axes"]

    with patch.object(page.plt, "subplots", side_effect=capture):
        svg = fn(*args)
    return svg, np.atleast_1d(box["fig_axes"][1]).ravel()


class CdfTest(unittest.TestCase):
    def test_bench_dashboard_cdf_rows_are_the_cohort_finite_for_every_model_and_both_arms(self):
        data = metrics_table(override={("rpmstk", STATIONS[3], "kge_gupta_2009", True): np.nan})
        result = page.cdf_table(data, spec_for("cdf", False))
        kge = result[result["metric"] == "kge_gupta_2009"]
        self.assertNotIn(STATIONS[3], set(kge["station"]), "dropped for every model")
        self.assertEqual(kge.groupby("model")["station"].nunique().unique().tolist(), [11])
        other = result[result["metric"] == "nse_seasonal"]
        self.assertIn(STATIONS[3], set(other["station"]), "other panels keep it")
        self.assertEqual(set(result["pcorr"]), {False})
        self.assertEqual(list(result.columns), ["pcorr", "metric", "model", "seed", "station", "value"])

    def test_bench_dashboard_cdf_draws_full_ecdf_steps_per_model_in_four_panels(self):
        data = metrics_table()
        frame = page.cdf_table(data, spec_for("cdf", True))
        svg, axes = captured_axes(page.render_cdf, frame, spec_for("cdf", True))
        self.assertEqual([ax.get_title() for ax in axes],
                         [f"{t} · n = 12 catchments" for _, t, _ in page.CDF_PANELS])
        kge_axis = axes[0]
        self.assertEqual(len(kge_axis.lines) - 1, len(MODELS), "one step line per model plus the zero line")
        expected = sorted(value("ptstk", s, "kge_gupta_2009", True) for s in STATIONS[:12])
        ptstk = kge_axis.lines[0]
        np.testing.assert_allclose(ptstk.get_xdata(), expected)
        np.testing.assert_allclose(ptstk.get_ydata(), np.arange(1, 13) / 12)
        labels = [t.get_text() for t in kge_axis.get_legend().get_texts()]
        self.assertEqual(labels[0], f"PTSTK (med={np.median(expected):.2f})")
        self.assertIn("n = 12 catchments", kge_axis.get_title())
        self.assertTrue(all(s not in t.get_text() for ax in axes for t in ax.texts for s in STATIONS))
        self.assertEqual(svg, page.render_cdf(frame, spec_for("cdf", True)), "deterministic")

    def test_bench_dashboard_cdf_counts_values_outside_the_axis_range(self):
        override = {(m, STATIONS[0], "kge_gupta_2009", True): -5.0 for m in MODELS}
        frame = page.cdf_table(metrics_table(override=override), spec_for("cdf", True))
        _, axes = captured_axes(page.render_cdf, frame, spec_for("cdf", True))
        ys = axes[0].lines[0].get_ydata()
        self.assertAlmostEqual(ys[0], 1 / 12, msg="the clipped catchment still counts")

    def test_bench_dashboard_pcorr_compare_rows_are_off_then_on(self):
        frame = page.compare_table(metrics_table(), spec_for("pcorr-compare"))
        _, axes = captured_axes(page.render_pcorr_compare, frame, spec_for("pcorr-compare"))
        self.assertEqual(len(axes), 4)
        off = sorted(value("ptstk", s, "kge_gupta_2009", False) for s in STATIONS[:12])
        on = sorted(value("ptstk", s, "kge_gupta_2009", True) for s in STATIONS[:12])
        np.testing.assert_allclose(axes[0].lines[0].get_xdata(), off)
        np.testing.assert_allclose(axes[2].lines[0].get_xdata(), on)


class RegimeTest(unittest.TestCase):
    def test_bench_dashboard_pcorr_by_regime_boxes_pool_three_stacks_in_canonical_order(self):
        stations = STATIONS[:30]
        result = page.regime_table(metrics_table(stations=stations), spec_for("pcorr-by-regime"))
        order = [r["name"] for r in canon.load()["regimes"]]
        present = list(dict.fromkeys(result["regime"]))
        self.assertEqual(present, [r for r in order if r in present])
        mountain = [s for s in stations if REGIME[s] == "Mountain"]
        row = result[(result["regime"] == "Mountain") & (result["quantity"] == "pbias_off")].iloc[0]
        pooled = [value(m, s, "pbias", False) for m in page.REGIME_MODELS for s in mountain]
        self.assertEqual(row["n_catchments"], len(mountain))
        self.assertEqual(row["n_pairs"], len(pooled))
        self.assertAlmostEqual(row["p50"], float(np.median(pooled)))
        gain = result[(result["regime"] == "Mountain") & (result["quantity"] == "kge_gain")].iloc[0]
        self.assertAlmostEqual(gain["p50"], 0.05, msg="gain is KGE on minus KGE off")
        self.assertNotIn("station", result.columns)

    def test_bench_dashboard_pcorr_by_regime_uses_catchments_complete_for_all_three_stacks(self):
        stations = STATIONS[:30]
        mountain = [s for s in stations if REGIME[s] == "Mountain"]
        gap = {("ptsthbv", mountain[0], "pbias", True): np.nan}
        result = page.regime_table(metrics_table(stations=stations, override=gap), spec_for("pcorr-by-regime"))
        rows = result[result["regime"] == "Mountain"]
        self.assertEqual(set(rows["n_catchments"]), {len(mountain) - 1}, "dropped for every stack")
        self.assertEqual(set(rows["n_pairs"]), {3 * (len(mountain) - 1)}, "each catchment weighs the same")

    def test_bench_dashboard_pcorr_by_regime_refuses_to_pool_seeds(self):
        with self.assertRaises(ValueError):
            page.regime_table(metrics_table(seed="v00"), spec_for("pcorr-by-regime"))

    def test_bench_dashboard_pcorr_by_regime_renders_within_limits(self):
        frame = page.regime_table(metrics_table(stations=STATIONS[:30]), spec_for("pcorr-by-regime"))
        svg = page.render_pcorr_by_regime(frame, spec_for("pcorr-by-regime"))
        self.assertLessEqual(len(svg), canon.load()["sizeLimits"]["svgBytes"])


class MapTest(unittest.TestCase):
    def test_bench_dashboard_pcorr_map_marks_each_paired_catchment_at_its_pinned_location(self):
        stations = STATIONS[:20]
        override = {("rpmstk", stations[5], "kge_gupta_2009", False): np.nan}
        frame = page.map_table(metrics_table(stations=stations, override=override), spec_for("pcorr-map"))
        self.assertEqual(len(frame), 19)
        location = maps.load_attributes()
        for row in frame.itertuples():
            self.assertEqual((row.lat, row.lon), location[row.station])
        svg, axes = captured_axes(page.render_pcorr_map, frame, spec_for("pcorr-map"))
        points = axes[0].collections[-1]
        self.assertEqual(len(points.get_offsets()), 19)
        self.assertEqual(points.norm.vcenter, 0.0)
        self.assertEqual(points.norm.vmin, -points.norm.vmax, "colour scale centred and symmetric")
        self.assertTrue(all(s not in t.get_text() for t in axes[0].texts for s in STATIONS))
        self.assertLessEqual(len(svg), canon.load()["sizeLimits"]["svgBytes"])

    def test_bench_dashboard_colour_limit_ignores_a_few_extremes(self):
        gains = np.concatenate([np.linspace(-0.2, 0.3, 99), [380.0]])
        self.assertAlmostEqual(page.colour_limit(gains), 0.3)
        self.assertAlmostEqual(page.colour_limit(np.array([0.0])), 0.05)


class DispatchTest(unittest.TestCase):
    def test_bench_dashboard_every_published_and_models_pcorr_view_has_a_renderer(self):
        page_spec = next(p for p in canon.load()["pages"] if p["key"] == "models-pcorr")
        by_id = {f["id"]: f for f in canon.load()["pageFigures"]}
        views = {by_id[i]["view"] for i in page_spec["figures"]}
        views |= {f["view"] for f in canon.declared_figures("published")}
        self.assertLessEqual(views, set(render.RENDERERS))

    def test_bench_dashboard_unknown_view_is_refused(self):
        with self.assertRaises(NotImplementedError):
            render.render(metrics_table(), {"id": "x", "view": "no-such-view"})

    def test_bench_dashboard_full_size_models_pcorr_outputs_fit_the_limits(self):
        data = metrics_table(stations=STATIONS)
        limits = canon.load()["sizeLimits"]
        for view, pcorr in (("cdf", True), ("pcorr-compare", None), ("pcorr-by-regime", None),
                            ("pcorr-map", None)):
            spec = spec_for(view, pcorr)
            frame, svg = render.render(data, spec)
            self.assertLessEqual(len(svg), limits["svgBytes"], view)
            self.assertLessEqual(len(table_csv(frame)), limits["csvBytes"], view)


if __name__ == "__main__":
    unittest.main()
