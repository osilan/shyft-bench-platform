import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import canon, export, figures, importer, table  # noqa: E402
from pipeline import __main__ as cli  # noqa: E402


def long_table(values_off: dict, values_on: dict, model: str = "ptgsk") -> pd.DataFrame:
    """Headline KGE per station for pcorr off/on of one model and one goal."""
    rows = []
    for pcorr, values in ((False, values_off), (True, values_on)):
        for station, value in values.items():
            for metric in ("nse", "kge_gupta_2009", "kge_kling_2012", "pbias", "kge_1_over_q"):
                rows.append(("e", model, "kge", "seNorge", "forward", pcorr, "bobyqa", None,
                             station, "validation", metric,
                             value if metric == "kge_gupta_2009" else 0.5, 10, "", ""))
    return pd.DataFrame(rows, columns=table.COLUMNS)


class CanonTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("lake"), "lake not available")
    def test_bench_export_canon_is_generated_from_lean_and_up_to_date(self):
        self.assertEqual(canon.CANON_PATH.read_text(), canon.run_lean_export())

    def test_bench_dashboard_model_colours_come_from_lean(self):
        self.assertEqual(canon.model_colours()["lstm"], "#e31a1c")
        self.assertEqual(canon.model_colours()["ptgsk"], "#f4a582")

    def test_bench_experiment_catalogue_validation_is_simulation_minus_calibration(self):
        entry = canon.catalogue_entry("legacy-ptgsk-senorge")
        self.assertEqual(entry["direction"], "forward")
        day = lambda s: int(np.datetime64(s, "D").astype(np.int64))  # noqa: E731
        self.assertEqual(entry["validation"], [{"startDay": day("2001-01-01"),
                                                "endDay": day("2021-01-01")}])

    def test_bench_experiment_catalogue_validation_mask_uses_the_lean_intervals(self):
        entry = canon.catalogue_entry("legacy-ptgsk-senorge")
        dates = pd.Series(pd.to_datetime(["2000-12-31", "2001-01-01", "2020-12-31", "2021-01-01"]))
        self.assertEqual(table.validation_mask(dates, entry["validation"]).tolist(),
                         [False, True, True, False])


class BuildTest(unittest.TestCase):
    def test_bench_dashboard_export_builds_scoreboards_for_all_legacy_stacks(self):
        specs = canon.declared_figures("first-slice")
        models = cli.slice_models(specs[0])
        catalogue = canon.load()["catalogue"]
        expected_models = [
            model["key"] for model in canon.load()["models"]
            if any(experiment["provenance"] == "zenodo-import"
                   and experiment["forcing"] == specs[0]["forcing"]
                   and experiment["direction"] == specs[0]["direction"]
                   and experiment["optimizer"] == specs[0]["optimizer"]
                   and model["key"] in experiment["models"]
                   for experiment in catalogue)
        ]
        self.assertEqual(models, expected_models)
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp) / "dist"
            built_models, rendered_boards, manifest_artifacts = [], [], []

            def build_table(experiment_id, model, optimizer):
                built_models.append(model)
                frame = long_table({"a": 0.1, "b": 0.3}, {"a": 0.2, "b": 0.4}, model)
                sources = {
                    (False, "kge"): importer.Source(f"{model}/off.csv", f"{model}-off"),
                    (True, "kge"): importer.Source(f"{model}/on.csv", f"{model}-on"),
                }
                return frame, sources

            def capture_manifest(artifacts):
                manifest_artifacts.extend(artifacts)
                return {"artifacts": artifacts}

            with (patch.object(cli.table, "build", side_effect=build_table),
                patch.object(cli.canon, "declared_figures", return_value=specs),
                  patch.object(cli, "parquet_bytes", return_value=b"parquet"),
                  patch.object(cli.figures, "render_scoreboard",
                               side_effect=lambda board: rendered_boards.append(board) or b"<svg/>"),
                  patch.object(cli.export, "manifest", side_effect=capture_manifest),
                  patch.object(cli.export, "check_dist", return_value=[]),
                  patch.object(cli, "INTERNAL", Path(tmp) / "internal")):
                self.assertEqual(cli.build(dist), 0)
            self.assertEqual(built_models, models)
            self.assertEqual(len(rendered_boards), 2)
            for board in rendered_boards:
                self.assertEqual(set(board["model"]), set(models))
                self.assertTrue({"median_nse", "median_kge_gupta_2009", "median_kge_kling_2012",
                                 "median_pbias", "median_kge_1_over_q"}.issubset(board.columns))
            self.assertEqual(len(list((Path(tmp) / "internal").glob("*.parquet"))), len(models))
            expected_experiments = {
                cli.experiment_for(specs[0], model)["id"] for model in models
            }
            self.assertEqual(len(manifest_artifacts), 4)
            for artifact in manifest_artifacts:
                self.assertEqual(set(artifact["experiment_ids"]), expected_experiments)
                self.assertEqual(
                    {source["experiment_id"] for source in artifact["sources"]},
                    expected_experiments,
                )
                self.assertEqual(len(artifact["sources"]), len(models) * 2)
            self.assertEqual((dist / "canon.json").read_bytes(), canon.CANON_PATH.read_bytes())
            self.assertEqual(json.loads((dist / "catalogue.json").read_text()),
                             canon.load()["catalogue"])
            manifest = json.loads((dist / "manifest.json").read_text())
            self.assertEqual(manifest["artifacts"], manifest_artifacts)

    def test_bench_export_builds_all_published_figures_from_lean_ids(self):
        specs = canon.declared_figures("published")
        expected = canon.load()["published"]
        self.assertEqual(len(expected), 10)
        self.assertEqual([spec["id"] for spec in specs], expected)
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp) / "dist"
            rendered = []
            def build_table(experiment_id, model, optimizer):
                return long_table({"a": 0.1, "b": 0.3}, {"a": 0.2, "b": 0.4}, model), {}

            with (patch.object(cli.table, "build", side_effect=build_table),
                  patch.object(cli, "parquet_bytes", return_value=b"parquet"),
                  patch.object(cli.render, "render",
                               side_effect=lambda data, spec: rendered.append(spec["view"]) or (data, b"<svg/>")),
                  patch.object(cli.export, "manifest", side_effect=lambda artifacts: {"artifacts": artifacts}),
                  patch.object(cli, "INTERNAL", Path(tmp) / "internal")):
                self.assertEqual(cli.build(dist), 0)
            index = json.loads((dist / "figure-index.json").read_text())["figures"]
            self.assertEqual([entry["id"] for entry in index], expected)
            self.assertEqual(len(rendered), len(specs))
            self.assertEqual(rendered.count("scoreboard"), 2)
            self.assertEqual(rendered.count("cdf"), 2)
            self.assertEqual(rendered.count("kge-compass"), 2)
            self.assertEqual(rendered.count("low-flow"), 2)
            self.assertEqual(rendered.count("ruzzante"), 2)
            self.assertEqual(len(list((dist / "figures").glob("*.svg"))), len(specs))
            self.assertEqual(len(list((dist / "tables").glob("*.csv"))), len(specs))
            self.assertEqual(export.check_dist(dist, "published"), [])


class ScoreboardTest(unittest.TestCase):
    def test_bench_dashboard_scoreboard_uses_only_the_matched_cohort(self):
        data = long_table({"a": 0.1, "b": 0.3, "c": 0.5, "d": 0.9}, {"a": 0.2, "b": 0.4, "c": 0.6})
        off = figures.scoreboard_table(data, False)
        on = figures.scoreboard_table(data, True)
        self.assertEqual(off["n_matched"].tolist(), [3])
        self.assertAlmostEqual(off["median_kge_gupta_2009"].iloc[0], 0.3)  # d (0.9) is excluded
        self.assertAlmostEqual(on["median_kge_gupta_2009"].iloc[0], 0.4)

    def test_bench_dashboard_scoreboard_matches_models_and_pcorr_arms(self):
        ptgsk = long_table({"a": 0.1, "b": 0.2, "c": 0.3},
                           {"a": 0.2, "b": 0.4, "c": 0.6}, "ptgsk")
        ptstk = long_table({"b": 0.8, "c": 0.9, "d": 1.0},
                           {"b": float("nan"), "c": 0.7, "d": 0.5}, "ptstk")
        data = pd.concat([ptgsk, ptstk], ignore_index=True)

        off = figures.scoreboard_table(data, False).set_index("model")
        on = figures.scoreboard_table(data, True).set_index("model")

        self.assertEqual(off["n_matched"].to_dict(), {"ptgsk": 1, "ptstk": 1})
        self.assertEqual(on["n_matched"].to_dict(), {"ptgsk": 1, "ptstk": 1})
        self.assertEqual(off["median_kge_gupta_2009"].to_dict(), {"ptgsk": 0.3, "ptstk": 0.9})
        self.assertEqual(on["median_kge_gupta_2009"].to_dict(), {"ptgsk": 0.6, "ptstk": 0.7})

    def test_bench_dashboard_scoreboard_drops_stations_without_a_finite_value_in_either_arm(self):
        data = long_table({"a": 0.1, "b": 0.3, "c": float("nan")}, {"a": 0.2, "b": float("nan"),
                                                                    "c": 0.6})
        off = figures.scoreboard_table(data, False)
        self.assertEqual(off["n_matched"].tolist(), [1])
        self.assertAlmostEqual(off["median_kge_gupta_2009"].iloc[0], 0.1)

    def test_bench_dashboard_scoreboard_svg_uses_the_canonical_colour(self):
        data = long_table({"a": 0.1, "b": 0.3}, {"a": 0.2, "b": 0.4})
        svg = figures.render_scoreboard(figures.scoreboard_table(data, True)).decode()
        self.assertIn(canon.model_colours()["ptgsk"], svg)

    def test_bench_dashboard_scoreboard_rendering_is_deterministic(self):
        data = long_table({"a": 0.1, "b": 0.3}, {"a": 0.2, "b": 0.4})
        board = figures.scoreboard_table(data, False)
        self.assertEqual(figures.render_scoreboard(board), figures.render_scoreboard(board))


class DiagnosticFigureTest(unittest.TestCase):
    def setUp(self):
        self.required_metrics = {
            "kge-compass": ("kge_gupta_2009", "kge_kling_2012"),
            "low-flow": ("kge_1_over_q",),
            "ruzzante": (
                "nse_seasonal", "r_seasonal", "alpha_seasonal", "variance_share_seasonal",
                "nse_interannual", "r_interannual", "alpha_interannual",
                "variance_share_interannual", "nse_irregular", "r_irregular", "alpha_irregular",
                "variance_share_irregular",
            ),
        }
        self.metrics = pd.DataFrame([
            (f"synthetic-{model}-{goal}", model, goal, forcing, direction, pcorr, optimizer, seed,
             "station-a", "validation", metric, float(i), 10, "2001-01-01", "2001-01-10")
            for forcing in ("seNorge", "other")
            for direction in ("forward", "reverse")
            for pcorr in (False, True)
            for optimizer in ("bobyqa", "sceua")
            for model in ("ptgsk", "lstm")
            for goal in ("kge", "nse")
            for seed in ("seed-11", "seed-22", None)
            for i, metric in enumerate(dict.fromkeys(
                    metric for values in self.required_metrics.values() for metric in values))
        ], columns=table.COLUMNS)
        self.specs = {
            view: next(spec for spec in canon.declared_figures("grid")
                       if spec["view"] == view and spec["pcorr"] is False)
            for view in self.required_metrics
        }

    def test_bench_kge_compass_table_uses_one_finite_cohort_for_both_metrics(self):
        values = [
            (f"synthetic-{model}-{goal}", model, goal, "seNorge", "forward", False,
             "bobyqa", seed, station, "validation", metric, value, 10,
             "2001-01-01", "2001-01-10")
            for goal in ("kge",)
            for seed, seed_offset in (("seed-1", 0), ("seed-2", 5000))
            for model, model_offset in (("ptgsk", 0), ("ptstk", 100))
            for metric, metric_offset in (("kge_gupta_2009", 0), ("kge_kling_2012", 1000))
            for station, station_offset in zip("abcde", (0, 10, 20, 30, 40))
            for value in (
                float("nan") if (seed, model, metric, station) ==
                ("seed-2", "ptstk", "kge_kling_2012", "c") else
                model_offset + metric_offset + seed_offset + station_offset,
            )
        ]
        raw = pd.DataFrame(values, columns=table.COLUMNS)
        result = figures.diagnostic_table(raw, self.specs["kge-compass"])
        self.assertEqual(result.columns.tolist(), [
            "model", "goal", "metric", "seed", "n", "p05", "p25", "p50", "p75", "p95",
        ])
        self.assertNotIn("station", result.columns)
        self.assertEqual(len(result), 2 * 2 * 2)
        self.assertFalse(result.duplicated(["model", "goal", "metric", "seed"]).any())
        self.assertEqual(set(result["n"]), {4})
        expected = {
            ("ptgsk", "kge_gupta_2009", "seed-1"): (7.5, 20, 32.5),
            ("ptgsk", "kge_kling_2012", "seed-1"): (1007.5, 1020, 1032.5),
            ("ptstk", "kge_gupta_2009", "seed-1"): (107.5, 120, 132.5),
            ("ptstk", "kge_kling_2012", "seed-1"): (1107.5, 1120, 1132.5),
        }
        expected.update({
            (model, metric, "seed-2"): tuple(value + 5000 for value in percentiles)
            for (model, metric, _), percentiles in expected.copy().items()
        })
        for row in result.itertuples(index=False):
            self.assertEqual(
                (row.p25, row.p50, row.p75),
                expected[(row.model, row.metric, row.seed)],
            )
        csv = figures.table_csv(result)
        self.assertNotIn(b"station", csv.splitlines()[0])
        self.assertIn(b"seed-2", csv)

    def test_bench_kge_compass_renders_ordered_median_iqr_markers_within_svg_limit(self):
        models = [model["key"] for model in canon.load()["models"][:5]]
        goals = canon.load()["goals"]
        values = [
            (f"synthetic-{model}", model, goal, "seNorge", "forward", False, "bobyqa", None,
             f"station-{station}", "validation", metric,
             float(model_index + goal_index + station + (100 if metric == "kge_kling_2012" else 0)),
             10, "2001-01-01", "2001-01-10")
            for goal_index, goal in enumerate(goals)
            for model_index, model in enumerate(models)
            for metric in ("kge_gupta_2009", "kge_kling_2012")
            for station in range(12)
        ]
        raw = pd.DataFrame(values, columns=table.COLUMNS)
        result = figures.diagnostic_table(raw, self.specs["kge-compass"])
        csv = figures.table_csv(result)
        real_subplots = figures.plt.subplots
        captured = {}

        def capture_subplots(*args, **kwargs):
            captured["fig_axes"] = real_subplots(*args, **kwargs)
            return captured["fig_axes"]

        with patch.object(figures.plt, "subplots", side_effect=capture_subplots):
            svg = figures.render_diagnostic(result, self.specs["kge-compass"])
        axes = captured["fig_axes"][1]
        self.assertEqual(axes.shape, (2, 5))
        first_panel = axes.flat[0]
        self.assertEqual(len(first_panel.containers), len(models))
        self.assertFalse(any(isinstance(collection, figures.plt.matplotlib.collections.PathCollection)
                             for collection in first_panel.collections))
        for model_index, (model, container) in enumerate(zip(models, first_panel.containers)):
            line, _, barlinecols = container.lines
            self.assertAlmostEqual(line.get_xdata()[0], model_index + 5.5)
            self.assertAlmostEqual(line.get_ydata()[0], model_index + 105.5)
            self.assertEqual(line.get_color(), canon.model_colours()[model])
            x_segment = barlinecols[0].get_segments()[0][[0, -1], 0]
            y_segment = barlinecols[1].get_segments()[0][[0, -1], 1]
            np.testing.assert_allclose(x_segment, [model_index + 2.75, model_index + 8.25])
            np.testing.assert_allclose(y_segment, [model_index + 102.75, model_index + 108.25])
        self.assertEqual([ax.get_title() for ax in axes.flat],
                         [f"{figures.goal_label(goal)} (n = 12)" for goal in goals])
        self.assertEqual(svg, figures.render_diagnostic(result, self.specs["kge-compass"]))
        self.assertNotIn(b"station-", svg)
        limits = canon.load()["sizeLimits"]
        self.assertLessEqual(len(svg), limits["svgBytes"])
        self.assertLessEqual(len(csv), limits["csvBytes"])

    def test_bench_kge_compass_titles_use_summary_seed_cohort_ranges(self):
        goals = canon.load()["goals"]
        rows = pd.DataFrame([
            ("ptgsk", goal, metric, seed, n, 0.1, 0.2, 0.3)
            for goal, sizes in zip(goals[:2], ((85, 80, 82), (7, 7, 7)))
            for seed, n in zip((None, "seed-1", "seed-2"), sizes)
            for metric in figures.DIAGNOSTIC_METRICS["kge-compass"]
        ], columns=["model", "goal", "metric", "seed", "n", "p25", "p50", "p75"])
        real_subplots = figures.plt.subplots
        captured = {}

        def capture_subplots(*args, **kwargs):
            captured["fig_axes"] = real_subplots(*args, **kwargs)
            return captured["fig_axes"]

        with patch.object(figures.plt, "subplots", side_effect=capture_subplots):
            figures.render_diagnostic(rows, self.specs["kge-compass"])
        axes = captured["fig_axes"][1]
        self.assertEqual([ax.get_title() for ax in axes.flat], [
            f"{figures.goal_label(goals[0])} (n = 80–85)",
            f"{figures.goal_label(goals[1])} (n = 7)",
            *[figures.goal_label(goal) for goal in goals[2:]],
        ])

    def test_bench_low_flow_table_uses_box_percentiles_and_keeps_seed_cohorts(self):
        models = ["ptgsk", "ptstk"]
        values = []
        for model in reversed(models):
            for seed, shift in (("seed-1", 0), ("seed-2", 100)):
                for station, value in zip("abcde", (0, 10, 20, 30, 40)):
                    values.append((
                        f"{model}-{seed}", model, "kge", "seNorge", "forward", False,
                        "bobyqa", seed, station, "validation", "kge_1_over_q",
                        value + shift, 10, "2001-01-01", "2001-01-10",
                    ))
        data = pd.DataFrame(values, columns=table.COLUMNS)
        result = figures.diagnostic_table(data, self.specs["low-flow"])
        self.assertEqual(result.columns.tolist(), [
            "model", "goal", "seed", "n", "p05", "p25", "p50", "p75", "p95",
        ])
        self.assertEqual(len(result), len(models) * 2)
        self.assertFalse(result.duplicated(["model", "goal", "seed"]).any())
        self.assertEqual(result["n"].tolist(), [5] * 4)
        self.assertEqual(result["model"].tolist(), ["ptstk", "ptstk", "ptgsk", "ptgsk"])
        ptstk = result[result["model"] == "ptstk"].set_index("seed")
        self.assertEqual(ptstk.loc["seed-1", ["p05", "p25", "p50", "p75", "p95"]].tolist(),
                         [2, 10, 20, 30, 38])
        self.assertEqual(ptstk.loc["seed-2", "p50"], 120)
        csv = figures.table_csv(result)
        self.assertNotIn(b"station", csv.splitlines()[0])
        self.assertIn(b",5,", csv)

    def test_bench_low_flow_boxes_use_canonical_order_colours_and_no_raw_points(self):
        models = [model["key"] for model in canon.load()["models"][:5]]
        goals = canon.load()["goals"]
        rows = pd.DataFrame([
            (model, goal, "kge_1_over_q", None, 12, 2, 10, 20, 30, 38)
            for goal in goals for model in reversed(models)
        ], columns=["model", "goal", "metric", "seed", "n",
                    "p05", "p25", "p50", "p75", "p95"])
        real_subplots = figures.plt.subplots
        captured = {}

        def capture_subplots(*args, **kwargs):
            captured["fig_axes"] = real_subplots(*args, **kwargs)
            return captured["fig_axes"]

        with patch.object(figures.plt, "subplots", side_effect=capture_subplots):
            svg = figures.render_diagnostic(rows, self.specs["low-flow"])
        ax = captured["fig_axes"][1]
        boxes = [patch for patch in ax.patches if isinstance(patch, figures.plt.Rectangle)
                 and patch is not ax.patch]
        self.assertEqual(len(boxes), len(models) * len(goals))
        model_boxes = boxes[::len(goals)]
        self.assertEqual([box.get_edgecolor()[:3] for box in model_boxes],
                         [tuple(int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
                          for colour in [canon.model_colours()[model] for model in models]])
        goal_zero_centers = [box.get_x() + box.get_width() / 2 for box in boxes[:len(models)]]
        self.assertEqual(goal_zero_centers, sorted(goal_zero_centers))
        for box in boxes:
            self.assertAlmostEqual(box.get_y(), 10)
            self.assertAlmostEqual(box.get_height(), 20)
        self.assertFalse(any(isinstance(collection, figures.plt.matplotlib.collections.PathCollection)
                             for collection in ax.collections))
        self.assertEqual([tick.get_text() for tick in ax.get_xticklabels()],
                         [figures.goal_label(goal) for goal in goals])
        self.assertIn("cohort n = 12 catchments", ax.get_title(loc="left"))
        self.assertNotIn("station", svg.decode().lower())
        self.assertEqual(svg, figures.render_diagnostic(rows, self.specs["low-flow"]))

    def test_bench_low_flow_full_grid_svg_fits_lean_size_limit(self):
        models = [model["key"] for model in canon.load()["models"][:5]]
        goals = canon.load()["goals"]
        values = [
            (f"synthetic-{model}", model, goal, "seNorge", "forward", False, "bobyqa", None,
             f"station-{station}", "validation", "kge_1_over_q", float(model_index + goal_index
             + station), 10, "2001-01-01", "2001-01-10")
            for goal_index, goal in enumerate(goals)
            for model_index, model in enumerate(models)
            for station in range(12)
        ]
        raw = pd.DataFrame(values, columns=table.COLUMNS)
        result = figures.diagnostic_table(raw, self.specs["low-flow"])
        csv = figures.table_csv(result)
        svg = figures.render_diagnostic(result, self.specs["low-flow"])
        limits = canon.load()["sizeLimits"]
        self.assertEqual(len(result), 5 * 10)
        self.assertLessEqual(len(svg), limits["svgBytes"])
        self.assertLessEqual(len(csv), limits["csvBytes"])

    def test_bench_ruzzante_table_and_grid_use_canonical_medians_and_iqrs(self):
        models = [model["key"] for model in canon.load()["models"][:5]]
        goals = canon.load()["goals"]
        metrics = figures.canonical_metric_order("ruzzante")
        station_values = (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 40)
        values = [
            (f"synthetic-{model}", model, goal, "seNorge", "forward", False, "bobyqa",
             None, f"station-{station}", "validation", metric,
             float(metric_index * 1000 + model_index * 100 + goal_index * 10 + station_value),
             10, "2001-01-01", "2001-01-10")
            for metric_index, metric in enumerate(metrics)
            for goal_index, goal in enumerate(goals)
            for model_index, model in enumerate(models)
            for station, station_value in enumerate(station_values)
        ]
        raw = pd.DataFrame(values, columns=table.COLUMNS)
        result = figures.diagnostic_table(raw, self.specs["ruzzante"])
        expected_columns = [
            "model", "goal", "metric", "seed", "n", "p05", "p25", "p50", "p75", "p95",
        ]
        self.assertEqual(result.columns.tolist(), expected_columns)
        self.assertEqual(len(result), 5 * 10 * 12)
        self.assertNotIn("station", result.columns)
        self.assertEqual(result["metric"].drop_duplicates().tolist(), list(metrics))
        selected = result[
            (result["model"] == models[2]) & (result["goal"] == goals[0])
            & (result["metric"] == metrics[0])
        ].iloc[0]
        self.assertEqual(selected["n"], 12)
        self.assertEqual((selected["p25"], selected["p50"], selected["p75"]),
                         (202.75, 205.5, 208.25))
        csv = figures.table_csv(result)
        self.assertEqual(csv.splitlines()[0].decode().split(","), expected_columns)
        self.assertNotIn(b"station", csv.splitlines()[0])

        real_subplots = figures.plt.subplots
        captured = {}

        def capture_subplots(*args, **kwargs):
            captured["fig_axes"] = real_subplots(*args, **kwargs)
            return captured["fig_axes"]

        with patch.object(figures.plt, "subplots", side_effect=capture_subplots):
            svg = figures.render_diagnostic(result, self.specs["ruzzante"])
        axes = captured["fig_axes"][1]
        self.assertEqual(axes.shape, (3, 4))
        expected_titles = [
            f"{metric.removesuffix('_' + scale).replace('_', ' ')} {scale} (n = 12)"
            for scale in ("seasonal", "interannual", "irregular")
            for metric in metrics if metric.endswith(f"_{scale}")
        ]
        self.assertEqual([ax.get_title() for ax in axes.flat], expected_titles)
        for ax in axes.flat:
            self.assertEqual([tick.get_text() for tick in ax.get_xticklabels()],
                             [figures.goal_label(goal) for goal in goals])
        first_panel = axes[0, 0]
        self.assertEqual(len(first_panel.containers), len(models) * len(goals))
        self.assertFalse(any(isinstance(collection, figures.plt.matplotlib.collections.PathCollection)
                             for collection in first_panel.collections))
        marker, _, barlinecols = first_panel.containers[2 * len(goals)].lines
        self.assertEqual(marker.get_color(), canon.model_colours()[models[2]])
        self.assertAlmostEqual(marker.get_xdata()[0], 0)
        self.assertAlmostEqual(marker.get_ydata()[0], 205.5)
        np.testing.assert_allclose(barlinecols[0].get_segments()[0][[0, -1], 1],
                                   [202.75, 208.25])
        legend = captured["fig_axes"][0].legends
        self.assertEqual(len(legend), 1)
        self.assertEqual([text.get_text() for text in legend[0].get_texts()],
                         [model.upper() for model in models])
        self.assertEqual(svg, figures.render_diagnostic(result, self.specs["ruzzante"]))
        limits = canon.load()["sizeLimits"]
        self.assertLessEqual(len(svg), limits["svgBytes"])
        self.assertLessEqual(len(csv), limits["csvBytes"])

    def test_bench_ruzzante_keeps_each_seed_median_in_its_model_slot(self):
        metrics = figures.canonical_metric_order("ruzzante")
        model = canon.load()["models"][0]["key"]
        goal = canon.load()["goals"][0]
        rows = pd.DataFrame([
            (model, goal, metric, seed, 4, median - 5, median - 2, median,
             median + 2, median + 5)
            for metric in metrics
            for seed, median in (("seed-1", 10), ("seed-2", 100))
        ], columns=["model", "goal", "metric", "seed", "n",
                    "p05", "p25", "p50", "p75", "p95"])
        real_subplots = figures.plt.subplots
        captured = {}

        def capture_subplots(*args, **kwargs):
            captured["fig_axes"] = real_subplots(*args, **kwargs)
            return captured["fig_axes"]

        with patch.object(figures.plt, "subplots", side_effect=capture_subplots):
            figures.render_diagnostic(rows, self.specs["ruzzante"])
        first_panel = captured["fig_axes"][1][0, 0]
        self.assertEqual(len(first_panel.containers), 2)
        markers = [container.lines[0] for container in first_panel.containers]
        self.assertEqual([marker.get_ydata()[0] for marker in markers], [10, 100])
        np.testing.assert_allclose([marker.get_xdata()[0] for marker in markers],
                                   [-0.175, 0.175])

    def test_bench_diagnostic_functions_reject_unhandled_views(self):
        invalid = {**self.specs["ruzzante"], "view": "other"}
        with self.assertRaisesRegex(ValueError, "unsupported diagnostic view"):
            figures.diagnostic_table(self.metrics, invalid)
        with self.assertRaisesRegex(ValueError, "unsupported diagnostic view"):
            figures.render_diagnostic(pd.DataFrame({"metric": ["test"]}), invalid)

    def test_bench_dashboard_diagnostic_views_keep_metric_variant_and_seed_rows(self):
        for view, spec in self.specs.items():
            with self.subTest(view=view):
                rows = figures.diagnostic_table(self.metrics, spec)
                if view == "low-flow":
                    self.assertNotIn("metric", rows.columns)
                elif view == "kge-compass":
                    self.assertEqual(set(rows["metric"]), set(self.required_metrics[view]))
                    self.assertNotIn("station", rows.columns)
                    self.assertNotIn("forcing", rows.columns)
                elif view == "ruzzante":
                    self.assertEqual(set(rows["metric"]), set(self.required_metrics[view]))
                    self.assertNotIn("station", rows.columns)
                    self.assertNotIn("forcing", rows.columns)
                else:
                    self.assertEqual(set(rows["metric"]), set(self.required_metrics[view]))
                expected_rows = (2 * 2 * 3 * len(self.required_metrics[view])
                                 if view == "kge-compass"
                                 else 12 * len(self.required_metrics[view]))
                self.assertEqual(len(rows), expected_rows)
                self.assertEqual(set(rows["seed"].dropna()), {"seed-11", "seed-22"})
                self.assertTrue(rows["seed"].isna().any())
                self.assertEqual(set(rows["model"]), {"ptgsk", "lstm"})
                self.assertEqual(set(rows["goal"]), {"kge", "nse"})
                csv = figures.table_csv(rows)
                if view == "low-flow":
                    self.assertNotIn("station", rows.columns)
                    self.assertEqual(csv.splitlines()[0].decode().split(","),
                                     ["model", "goal", "seed", "n", "p05", "p25",
                                      "p50", "p75", "p95"])
                else:
                    if view == "kge-compass":
                        self.assertEqual(csv.decode().splitlines()[0].split(","),
                                         rows.columns.tolist())
                        self.assertNotIn("station", rows.columns)
                    elif view == "ruzzante":
                        self.assertEqual(csv.decode().splitlines()[0].split(","),
                                         rows.columns.tolist())
                        self.assertNotIn("station", rows.columns)
                self.assertIn(b"seed-11", csv)
                self.assertIn(b"seed-22", csv)

    def test_bench_dashboard_diagnostic_svg_and_csv_rendering_is_deterministic(self):
        for view, spec in self.specs.items():
            with self.subTest(view=view):
                rows = figures.diagnostic_table(self.metrics, spec)
                self.assertEqual(figures.table_csv(rows), figures.table_csv(rows))
                first = figures.render_diagnostic(rows, spec)
                self.assertEqual(first, figures.render_diagnostic(rows, spec))
                self.assertIn(b"<svg", first)
                svg = first.decode()
                expected_model_labels = ("PTGSK", "LSTM")
                self.assertIn(expected_model_labels[0], svg)
                self.assertIn(expected_model_labels[1], svg)
                labels = {
                    "kge-compass": ["KGE (Gupta et al., 2009)", "KGE (Kling et al., 2012)"],
                    "low-flow": ["KGE(1/Q)"],
                    "ruzzante": ["nse seasonal", "r seasonal", "alpha seasonal",
                                 "variance share seasonal", "nse interannual",
                                 "r interannual", "alpha interannual",
                                 "variance share interannual", "nse irregular",
                                 "r irregular", "alpha irregular",
                                 "variance share irregular"],
                }
                for label in labels[view]:
                    self.assertIn(label, svg)


class WriteOnceTest(unittest.TestCase):
    def test_bench_export_results_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "x" / "result.csv"
            self.assertTrue(export.write_once(path, b"a"))
            self.assertFalse(export.write_once(path, b"a"))
            with self.assertRaises(export.WriteOnceError):
                export.write_once(path, b"b")
            self.assertEqual(path.read_bytes(), b"a")


class GridCheckTest(unittest.TestCase):
    def fake_dist(self, tmp: Path, ids: list[str]) -> None:
        by_id = {f["id"]: f for f in canon.declared_figures("grid")}
        artifacts, entries = [], []
        for i in ids:
            spec = by_id.get(i, {"id": i, "view": "scoreboard", "forcing": "seNorge",
                                 "direction": "forward", "pcorr": True, "optimizer": "bobyqa"})
            entry = export.index_entry(spec)
            entries.append(entry)
            for kind, rel in (("figure", entry["svg"]), ("table", entry["csv"])):
                (tmp / rel).parent.mkdir(parents=True, exist_ok=True)
                (tmp / rel).write_bytes(rel.encode())
                artifacts.append({"id": i, "kind": kind, "path": rel,
                                  "sha256": export.sha256(rel.encode())})
        (tmp / "figure-index.json").write_bytes(export.dumps({"figures": entries}))
        (tmp / "manifest.json").write_bytes(export.dumps({"artifacts": artifacts}))
        (tmp / "canon.json").write_bytes(b"{}")
        (tmp / "catalogue.json").write_bytes(b"[]")

    def first_slice_ids(self):
        return [f["id"] for f in canon.declared_figures("first-slice")]

    def test_bench_export_published_ids_equal_the_declared_grid(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.fake_dist(Path(tmp), self.first_slice_ids())
            self.assertEqual(export.check_dist(Path(tmp), "first-slice"), [])

    def test_bench_export_published_set_matches_the_declaration(self):
        published = canon.load()["published"]
        with tempfile.TemporaryDirectory() as tmp:
            self.fake_dist(Path(tmp), published)
            self.assertEqual(export.check_dist(Path(tmp), "published"), [])

    def test_bench_export_published_set_missing_a_figure_fails(self):
        published = canon.load()["published"]
        with tempfile.TemporaryDirectory() as tmp:
            self.fake_dist(Path(tmp), published[:-1])
            problems = export.check_dist(Path(tmp), "published")
            self.assertTrue(any(f"declared figure missing: {published[-1]}" in p for p in problems))

    def test_bench_export_published_set_with_an_extra_figure_fails(self):
        extra = next(f["id"] for f in canon.declared_figures("grid")
                     if f["id"] not in canon.load()["published"])
        with tempfile.TemporaryDirectory() as tmp:
            self.fake_dist(Path(tmp), canon.load()["published"] + [extra])
            problems = export.check_dist(Path(tmp), "published")
            self.assertTrue(any(f"undeclared figure published: {extra}" in p for p in problems))

    def test_bench_export_the_first_slice_alone_is_not_the_published_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.fake_dist(Path(tmp), self.first_slice_ids())
            self.assertTrue(export.check_dist(Path(tmp), "published"))

    def test_bench_export_requires_canon_and_catalogue(self):
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp)
            self.fake_dist(dist, self.first_slice_ids())
            for name in ("canon.json", "catalogue.json"):
                (dist / name).unlink()
                problems = export.check_dist(dist, "first-slice")
                self.assertTrue(any(f"{name} is missing" in p for p in problems), problems)
                (dist / name).write_bytes(b"{}")

    def test_bench_export_a_missing_declared_figure_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.fake_dist(Path(tmp), self.first_slice_ids()[:1])
            problems = export.check_dist(Path(tmp), "first-slice")
            self.assertTrue(any("declared figure missing" in p for p in problems), problems)

    def test_bench_export_an_undeclared_figure_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.fake_dist(Path(tmp), self.first_slice_ids() + ["scoreboard-made-up"])
            problems = export.check_dist(Path(tmp), "first-slice")
            self.assertTrue(any("undeclared figure published" in p for p in problems), problems)

    def test_bench_export_a_file_missing_from_the_index_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.fake_dist(Path(tmp), self.first_slice_ids())
            (Path(tmp) / "figures" / "stray.svg").write_bytes(b"<svg/>")
            problems = export.check_dist(Path(tmp), "first-slice")
            self.assertTrue(any("not in the figure index" in p for p in problems), problems)

    def test_bench_export_a_tampered_file_fails_the_manifest_checksum(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.fake_dist(Path(tmp), self.first_slice_ids())
            svg = Path(tmp) / export.figure_paths(self.first_slice_ids()[0])[0]
            svg.write_bytes(b"changed")
            self.assertTrue(any("checksum" in p for p in export.check_dist(Path(tmp), "first-slice")))

    def test_bench_export_the_first_slice_alone_is_not_the_whole_grid(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.fake_dist(Path(tmp), self.first_slice_ids())
            self.assertTrue(export.check_dist(Path(tmp), "grid"))

    def test_bench_export_index_has_only_the_agreed_fields(self):
        entry = export.index_entry(canon.declared_figures("first-slice")[0])
        self.assertEqual(set(entry), {"id", "view", "forcing", "direction", "pcorr", "optimizer",
                                      "svg", "csv"})


@unittest.skipUnless(os.environ.get("SHYFT_BENCH_SLOW") == "1" and
                     importer.legacy_output_dir().is_dir(),
                     "set SHYFT_BENCH_SLOW=1 with the legacy results available")
class FirstSliceTest(unittest.TestCase):
    def test_bench_export_published_figures_build_and_match_declared_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = cli.INTERNAL
            cli.INTERNAL = Path(tmp) / "metrics"
            try:
                self.assertEqual(cli.build(Path(tmp) / "dist"), 0)
            finally:
                cli.INTERNAL = old
            index = json.loads((Path(tmp) / "dist" / "figure-index.json").read_text())
            self.assertEqual([f["id"] for f in index["figures"]],
                             canon.load()["published"])
            metrics_files = sorted((Path(tmp) / "metrics").glob("*.parquet"))
            self.assertEqual(len(metrics_files), len(cli.slice_models(canon.declared_figures("first-slice")[0])))
            expected_metrics = {metric["key"] for metric in canon.load()["metrics"]}
            for path in metrics_files:
                metrics = pd.read_parquet(path)
                self.assertEqual(set(metrics["metric"]), expected_metrics)
                self.assertEqual(metrics["model"].nunique(), 1)


if __name__ == "__main__":
    unittest.main()
