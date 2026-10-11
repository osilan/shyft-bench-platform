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
                  patch.object(cli.figures, "render_scoreboard",
                               side_effect=lambda frame: rendered.append("scoreboard") or b"<svg/>"),
                  patch.object(cli.figures, "cdf_table", side_effect=lambda data, spec: data),
                  patch.object(cli.figures, "render_cdf",
                               side_effect=lambda frame, spec: rendered.append("cdf") or b"<svg/>"),
                  patch.object(cli.figures, "diagnostic_table", side_effect=lambda data, spec: data),
                  patch.object(cli.figures, "render_diagnostic",
                               side_effect=lambda frame, spec: rendered.append(spec["view"]) or b"<svg/>"),
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

    def test_bench_dashboard_diagnostic_views_keep_metric_variant_and_seed_rows(self):
        for view, spec in self.specs.items():
            with self.subTest(view=view):
                rows = figures.diagnostic_table(self.metrics, spec)
                self.assertEqual(set(rows["metric"]), set(self.required_metrics[view]))
                self.assertEqual(len(rows), 12 * len(self.required_metrics[view]))
                self.assertEqual(set(rows["seed"].dropna()), {"seed-11", "seed-22"})
                self.assertTrue(rows["seed"].isna().any())
                self.assertEqual(set(rows["model"]), {"ptgsk", "lstm"})
                self.assertEqual(set(rows["goal"]), {"kge", "nse"})
                for column in ("forcing", "direction", "pcorr", "optimizer"):
                    self.assertEqual(set(rows[column]), {spec[column]})
                self.assertEqual(set(rows["forcing"]), {spec["forcing"]})
                csv = figures.table_csv(rows)
                self.assertTrue(set(self.required_metrics[view]).issubset(
                    {line.split(",")[10] for line in csv.decode().splitlines()[1:]}))
                self.assertIn(b"seed-11", csv)
                self.assertIn(b"seed-22", csv)
                self.assertTrue(csv.startswith(b"experiment_id,"))

    def test_bench_dashboard_diagnostic_svg_and_csv_rendering_is_deterministic(self):
        for view, spec in self.specs.items():
            with self.subTest(view=view):
                rows = figures.diagnostic_table(self.metrics, spec)
                self.assertEqual(figures.table_csv(rows), figures.table_csv(rows))
                first = figures.render_diagnostic(rows, spec)
                self.assertEqual(first, figures.render_diagnostic(rows, spec))
                self.assertIn(b"<svg", first)
                svg = first.decode()
                self.assertIn("ptgsk", svg)
                self.assertIn("lstm", svg)
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


class CdfFigureTest(unittest.TestCase):
    def setUp(self):
        self.spec = next(spec for spec in canon.declared_figures("grid")
                         if spec["view"] == "cdf" and spec["pcorr"] is False)

    def rows(self, values):
        return pd.DataFrame([
            ("synthetic", model, goal, "seNorge", "forward", False, "bobyqa", seed, station,
             "validation", metric, value, 10, "2001-01-01", "2001-01-10", variant)
            for metric, goal, model, station, seed, value, variant in values
        ], columns=[*table.COLUMNS, "variant"])

    def test_bench_dashboard_cdf_uses_metric_goal_matched_cohorts_and_tie_ranks(self):
        values = []
        for model, station_values in (
                ("ptgsk", {"a": 1, "b": 1, "c": 2, "d": 3, "e": 5}),
                ("lstm", {"a": 0, "b": 1, "c": 2, "d": 3, "e": float("inf")})):
            values.extend(("kge_gupta_2009", "kge", model, station, None, value, "base")
                          for station, value in station_values.items())
        values.extend([
            ("kge_kling_2012", "kge", "ptgsk", "a", None, 0.1, "base"),
            ("kge_kling_2012", "kge", "ptgsk", "b", None, 0.2, "base"),
            ("kge_kling_2012", "kge", "lstm", "a", None, 0.3, "base"),
            ("kge_kling_2012", "kge", "lstm", "b", None, float("nan"), "base"),
            ("kge_kling_2012", "nse", "ptgsk", "x", None, 0.4, "base"),
            ("kge_kling_2012", "nse", "ptgsk", "y", None, 0.5, "base"),
            ("kge_kling_2012", "nse", "lstm", "y", None, 0.6, "base"),
        ])
        with patch.object(figures, "matched_cohort", wraps=figures.matched_cohort) as cohort:
            result = figures.cdf_table(self.rows(values), self.spec)
        self.assertTrue(any(
            call.args[2] == "kge"
            and call.kwargs == {"metric": "kge_gupta_2009", "pcorrs": (False,)}
            for call in cohort.call_args_list
        ))
        panel = result[(result["metric"] == "kge_gupta_2009") & (result["goal"] == "kge")]
        self.assertEqual(set(panel["station"]), {"a", "b", "c", "d"})
        ptgsk = panel[panel["model"] == "ptgsk"].set_index("station")
        self.assertEqual(ptgsk.loc[["a", "b"], "cumulative_probability"].tolist(), [0.5, 0.5])
        self.assertEqual(ptgsk.loc["d", "cumulative_probability"], 1.0)
        self.assertFalse((panel["station"] == "e").any())

        second_metric = result[result["metric"] == "kge_kling_2012"]
        kge_panel = second_metric[second_metric["goal"] == "kge"]
        self.assertEqual(set(kge_panel["station"]), {"a"})
        nse_panel = second_metric[second_metric["goal"] == "nse"]
        self.assertEqual(set(nse_panel["station"]), {"y"})

    def test_bench_dashboard_cdf_preserves_seed_and_variant_observations(self):
        values = [
            ("kge_1_over_q", "kge", "ptgsk", "a", "seed-1", 0.2, "variant-1"),
            ("kge_1_over_q", "kge", "ptgsk", "a", "seed-2", 0.4, "variant-2"),
            ("kge_1_over_q", "kge", "lstm", "a", "seed-1", 0.3, "variant-1"),
            ("kge_1_over_q", "kge", "lstm", "a", "seed-2", 0.5, "variant-2"),
        ]
        result = figures.cdf_table(self.rows(values), self.spec)
        self.assertEqual(len(result), 4)
        self.assertEqual(set(result["seed"]), {"seed-1", "seed-2"})
        self.assertEqual(set(result["variant"]), {"variant-1", "variant-2"})
        self.assertEqual(set(result["cumulative_probability"]), {0.5, 1.0})
        self.assertTrue({"metric", "goal", "model", "station", "value",
                         "variant", "seed", "cumulative_probability"}.issubset(result.columns))

    def test_bench_dashboard_cdf_requires_finite_values_from_each_model(self):
        values = [
            ("kge_gupta_2009", "kge", "ptgsk", "a", None, 0.2, "base"),
            ("kge_gupta_2009", "kge", "lstm", "a", None, float("nan"), "base"),
        ]
        result = figures.cdf_table(self.rows(values), self.spec)
        self.assertTrue(result.empty)
        with self.assertRaisesRegex(ValueError, "no matched finite metric rows"):
            figures.render_cdf(result, self.spec)

    def test_bench_dashboard_declared_cdf_svg_and_csv_are_deterministic(self):
        values = [
            (metric, goal, model, station, "seed-1", float(index), "variant-1")
            for index, metric in enumerate(figures.CDF_METRICS)
            for goal in ("kge", "nse")
            for model in ("ptgsk", "lstm")
            for station in ("a", "b")
        ]
        result = figures.cdf_table(self.rows(values), self.spec)
        csv = figures.table_csv(result)
        svg = figures.render_cdf(result, self.spec)
        self.assertEqual(csv, figures.table_csv(result))
        self.assertEqual(svg, figures.render_cdf(result, self.spec))
        self.assertTrue(csv.startswith(b"experiment_id,"))
        self.assertIn(b"cumulative_probability", csv)
        self.assertIn(b"seed-1", csv)
        self.assertIn(b"<svg", svg)


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
