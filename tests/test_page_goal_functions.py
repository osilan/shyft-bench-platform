"""bench.dashboard, page goal-functions (D-032): generalism boxes and KGE components per goal."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import canon, page_goal_functions as page, render, table  # noqa: E402
from pipeline.figures import goal_label, table_csv  # noqa: E402

GOALS = canon.load()["goals"]
STATIONS = [s["id"] for s in canon.load()["stations"]][:15]
METRICS = [m for m, _ in page.GENERALISM_PANELS] + [m for m, _ in page.COMPONENT_PANELS]


def value(model, goal, station, metric, pcorr) -> float:
    return round(0.05 * GOALS.index(goal) + 0.01 * STATIONS.index(station) + 0.001 * METRICS.index(metric)
                 + (0.3 if model == "rpmstk" else 0.0) + (0.02 if pcorr else 0.0), 6)


def metrics_table(override=None, seed=None, models=("ptstk", "rpmstk")) -> pd.DataFrame:
    override = override or {}
    rows = [("e", model, goal, "seNorge", "forward", pcorr, "bobyqa", seed, station, "validation",
             metric, override.get((model, goal, station, metric, pcorr), value(model, goal, station, metric, pcorr)),
             10, "", "")
            for model in models for goal in GOALS for station in STATIONS for metric in METRICS
            for pcorr in (False, True)]
    return pd.DataFrame(rows, columns=table.COLUMNS)


def spec_for(view, model="rpmstk", pcorr=True) -> dict:
    return next(f for f in canon.load()["pageFigures"]
                if f["view"] == view and f["model"] == model and f["pcorr"] == pcorr)


def axes_of(fn, *args):
    real = page.plt.subplots
    box = {}

    def capture(*a, **k):
        box["fa"] = real(*a, **k)
        return box["fa"]

    with patch.object(page.plt, "subplots", side_effect=capture):
        svg = fn(*args)
    return svg, np.atleast_1d(box["fa"][1]).ravel()


class GeneralismTest(unittest.TestCase):
    def test_bench_dashboard_generalism_boxes_hold_only_the_selected_model_and_pcorr(self):
        result = page.generalism_table(metrics_table(), spec_for("goal-generalism"))
        self.assertEqual(set(result["model"]), {"rpmstk"})
        self.assertEqual(set(result["pcorr"]), {True})
        kge_rows = result[result["metric"] == "kge_gupta_2009"]
        self.assertEqual(list(kge_rows["goal"]), GOALS, "table rows in canonical goal order")
        row = result[(result["goal"] == "kge") & (result["metric"] == "kge_gupta_2009")].iloc[0]
        values = [value("rpmstk", "kge", s, "kge_gupta_2009", True) for s in STATIONS]
        for p in canon.load()["summaryPercents"]["box"]:
            self.assertAlmostEqual(row[f"p{p:02d}"], float(np.percentile(values, p)))
        self.assertEqual(row["n"], len(STATIONS))
        self.assertNotIn("station", result.columns)

    def test_bench_dashboard_generalism_compares_goals_on_the_same_catchments(self):
        override = {("rpmstk", "lnse", STATIONS[2], "kge_gupta_2009", True): np.nan}
        result = page.generalism_table(metrics_table(override), spec_for("goal-generalism"))
        kge = result[result["metric"] == "kge_gupta_2009"]
        self.assertEqual(set(kge["n"]), {len(STATIONS) - 1}, "dropped under every goal")
        self.assertEqual(set(result[result["metric"] == "pbias"]["n"]), {len(STATIONS)})

    def test_bench_dashboard_generalism_draws_six_panels_with_goals_in_order_and_family_colours(self):
        spec = spec_for("goal-generalism")
        frame = page.generalism_table(metrics_table(), spec)
        svg, axes = axes_of(page.render_generalism, frame, spec)
        self.assertEqual(len(axes), 6)
        self.assertEqual([t.get_text() for t in axes[0].get_xticklabels()], [goal_label(g) for g in GOALS])
        colours = [patch.get_facecolor()[:3] for patch in axes[0].patches]
        blue, red = (np.array(matplotlib_rgb(c)) for c in ("#4393c3", "#d6604d"))
        self.assertTrue(all(np.allclose(c, blue) for c in colours[:5]))
        self.assertTrue(all(np.allclose(c, red) for c in colours[5:]))
        medians = [float(t.get_text()) for t in axes[0].texts]
        expected = [round(float(np.median([value("rpmstk", g, s, "kge_gupta_2009", True) for s in STATIONS])), 2)
                    for g in GOALS]
        np.testing.assert_allclose(medians, expected)
        self.assertEqual(svg, page.render_generalism(frame, spec), "deterministic")

    def test_bench_dashboard_goal_figures_refuse_to_pool_seeds(self):
        with self.assertRaises(ValueError):
            page.generalism_table(metrics_table(seed="v00"), spec_for("goal-generalism"))


class FamilyTest(unittest.TestCase):
    def test_bench_dashboard_every_lean_goal_has_exactly_one_family(self):
        self.assertEqual([page.family(g) for g in GOALS], ["kge"] * 5 + ["nse"] * 5)
        with self.assertRaises(ValueError):
            page.family("rmse")


class ComponentsTest(unittest.TestCase):
    def test_bench_dashboard_bias_variability_has_r_alpha_beta_with_reference_at_one(self):
        spec = spec_for("bias-variability", model="ptstk", pcorr=False)
        frame = page.components_table(metrics_table(), spec)
        self.assertEqual(list(dict.fromkeys(frame["metric"])), ["kge_r", "kge_alpha", "kge_beta"])
        self.assertEqual(set(frame["model"]), {"ptstk"})
        _, axes = axes_of(page.render_components, frame, spec)
        self.assertEqual(len(axes), 3)
        for ax in axes:
            references = [l.get_ydata()[0] for l in ax.lines if l.get_linestyle() == "--"]
            self.assertEqual(references, [1.0])

    def test_bench_dashboard_goal_function_figures_fit_the_limits_for_every_model(self):
        data = metrics_table(models=("ptstk", "rpmstk", "ptgsk", "rpmgsk", "ptsthbv"))
        limits = canon.load()["sizeLimits"]
        page_spec = next(p for p in canon.load()["pages"] if p["key"] == "goal-functions")
        by_id = {f["id"]: f for f in canon.load()["pageFigures"]}
        for figure_id in page_spec["figures"]:
            frame, svg = render.render(data, by_id[figure_id])
            self.assertLessEqual(len(svg), limits["svgBytes"], figure_id)
            self.assertLessEqual(len(table_csv(frame)), limits["csvBytes"], figure_id)


def matplotlib_rgb(hex_colour):
    from matplotlib.colors import to_rgb
    return to_rgb(hex_colour)


if __name__ == "__main__":
    unittest.main()
