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


def long_table(values_off: dict, values_on: dict) -> pd.DataFrame:
    """Headline KGE per station for pcorr off/on of one model and one goal."""
    rows = []
    for pcorr, values in ((False, values_off), (True, values_on)):
        for station, value in values.items():
            for metric in ("nse", "kge_gupta_2009", "kge_kling_2012", "pbias", "kge_1_over_q"):
                rows.append(("e", "ptgsk", "kge", "seNorge", "forward", pcorr, "bobyqa", None,
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
    def test_bench_export_build_publishes_canon_and_catalogue(self):
        spec = {"id": "scoreboard-test", "view": "scoreboard", "forcing": "seNorge",
                "direction": "forward", "pcorr": True, "optimizer": "bobyqa"}
        with tempfile.TemporaryDirectory() as tmp:
            dist = Path(tmp) / "dist"
            with (patch.object(cli.canon, "declared_figures", return_value=[spec]),
                  patch.object(cli, "experiment_for", return_value={"id": "experiment"}),
                  patch.object(cli.table, "build", return_value=(pd.DataFrame(), {})),
                  patch.object(cli, "parquet_bytes", return_value=b"parquet"),
                  patch.object(cli.figures, "scoreboard_table", return_value=pd.DataFrame()),
                  patch.object(cli.figures, "render_scoreboard", return_value=b"<svg/>"),
                  patch.object(cli.figures, "table_csv", return_value=b"csv"),
                  patch.object(cli.export, "manifest", return_value={}),
                  patch.object(cli.export, "check_dist", return_value=[]),
                  patch.object(cli, "INTERNAL", Path(tmp) / "internal")):
                self.assertEqual(cli.build(dist), 0)
            self.assertEqual((dist / "canon.json").read_bytes(), canon.CANON_PATH.read_bytes())
            self.assertEqual(json.loads((dist / "catalogue.json").read_text()),
                             canon.load()["catalogue"])


class ScoreboardTest(unittest.TestCase):
    def test_bench_dashboard_scoreboard_uses_only_the_matched_cohort(self):
        data = long_table({"a": 0.1, "b": 0.3, "c": 0.5, "d": 0.9}, {"a": 0.2, "b": 0.4, "c": 0.6})
        off = figures.scoreboard_table(data, False)
        on = figures.scoreboard_table(data, True)
        self.assertEqual(off["n_matched"].tolist(), [3])
        self.assertAlmostEqual(off["median_kge_gupta_2009"].iloc[0], 0.3)  # d (0.9) is excluded
        self.assertAlmostEqual(on["median_kge_gupta_2009"].iloc[0], 0.4)

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
    def test_bench_export_first_slice_builds_and_matches_the_declared_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = cli.INTERNAL
            cli.INTERNAL = Path(tmp) / "metrics"
            try:
                self.assertEqual(cli.build(Path(tmp) / "dist"), 0)
            finally:
                cli.INTERNAL = old
            index = json.loads((Path(tmp) / "dist" / "figure-index.json").read_text())
            self.assertEqual([f["id"] for f in index["figures"]], canon.load()["firstSlice"])


if __name__ == "__main__":
    unittest.main()
