import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import canon, table  # noqa: E402
from pipeline.summaries import percentile_table, summary_percents  # noqa: E402


class PercentileTableTest(unittest.TestCase):
    def setUp(self):
        self.spec = {
            "forcing": "seNorge", "direction": "forward", "pcorr": False,
            "optimizer": "bobyqa",
        }

    def rows(self, values):
        return pd.DataFrame([
            ("synthetic", model, goal, "seNorge", "forward", False, "bobyqa", seed,
             station, "validation", metric, value, 10, "2001-01-01", "2001-01-10")
            for model, goal, metric, station, seed, value in values
        ], columns=table.COLUMNS)

    def test_percentiles_use_linear_interpolation_and_shared_finite_cohort(self):
        values = []
        for model, station_values in (
                ("ptgsk", {"a": 0, "b": 10, "c": 20, "missing": 100, "infinite": 200}),
                ("lstm", {"a": 30, "b": 40, "c": 50, "infinite": float("inf")})):
            values.extend((model, "kge", "kge_gupta_2009", station, None, value)
                          for station, value in station_values.items())
        data = self.rows(values)
        distractor = data.iloc[[0, 5]].copy()
        distractor["forcing"] = "other"
        distractor["station"] = "other-forcing"
        distractor["value"] = [1000, 2000]
        data = pd.concat([data, distractor], ignore_index=True)
        result = percentile_table(data, self.spec, ["kge_gupta_2009"], [25, 75])

        self.assertEqual(result[["model", "n"]].values.tolist(), [["ptgsk", 3], ["lstm", 3]])
        self.assertTrue(result["seed"].isna().all())
        self.assertEqual(result.columns.tolist(),
                         ["model", "goal", "metric", "seed", "n", "p25", "p75"])
        ptgsk = result[result["model"] == "ptgsk"].iloc[0]
        self.assertEqual((ptgsk["p25"], ptgsk["p75"]), (5, 15))
        lstm = result[result["model"] == "lstm"].iloc[0]
        self.assertEqual((lstm["p25"], lstm["p75"]), (35, 45))

    def test_seeds_are_summarized_separately(self):
        values = [
            (model, "kge", "kge_gupta_2009", station, seed, value)
            for model, base in (("ptgsk", 0), ("lstm", 10))
            for seed, offset in (("seed-1", 0), ("seed-2", 100))
            for station, step in (("a", 0), ("b", 10), ("c", 20))
            for value in (base + offset + step,)
        ]
        result = percentile_table(self.rows(values), self.spec, ["kge_gupta_2009"], [50])
        self.assertEqual(len(result), 4)
        values_by_group = result.set_index(["model", "seed"])["p50"]
        self.assertEqual(values_by_group[("ptgsk", "seed-1")], 10)
        self.assertEqual(values_by_group[("ptgsk", "seed-2")], 110)
        self.assertEqual(values_by_group[("lstm", "seed-1")], 20)
        self.assertEqual(values_by_group[("lstm", "seed-2")], 120)
        self.assertEqual(set(result["n"]), {3})

    def test_matched_cohort_requires_every_seed_to_be_finite_at_each_station(self):
        values = [
            ("ptgsk", "kge", "kge_gupta_2009", station, seed, value)
            for seed, station_values in (
                ("seed-1", {"a": 0, "b": 10, "c": 20, "d": float("nan")}),
                ("seed-2", {"a": float("nan"), "b": 110, "c": 120, "d": 130}),
            )
            for station, value in station_values.items()
        ]
        values.extend(
            ("lstm", "kge", "kge_gupta_2009", station, None, value)
            for station, value in (("a", 200), ("b", 210), ("c", 220), ("d", 230))
        )
        result = percentile_table(self.rows(values), self.spec, ["kge_gupta_2009"], [25, 50, 75])

        expected = {
            ("ptgsk", "seed-1"): (2, 12.5, 15, 17.5),
            ("ptgsk", "seed-2"): (2, 112.5, 115, 117.5),
            ("lstm", None): (2, 212.5, 215, 217.5),
        }
        self.assertEqual(len(result), len(expected))
        observed = set()
        for row in result.itertuples(index=False):
            key = (row.model, None if pd.isna(row.seed) else row.seed)
            observed.add(key)
            self.assertEqual((row.n, row.p25, row.p50, row.p75), expected[key])
        self.assertEqual(observed, set(expected))

    def test_percent_columns_follow_exported_cdf_list(self):
        exported = canon.load()["summaryPercents"]["cdf"]
        self.assertEqual(summary_percents("cdf"), tuple(exported))
        result = percentile_table(
            self.rows([("ptgsk", "kge", "kge_gupta_2009", "a", None, 1)]),
            self.spec, ["kge_gupta_2009"], list(summary_percents("cdf")),
        )
        self.assertEqual(result.columns.tolist(),
                         ["model", "goal", "metric", "seed", "n"]
                         + [f"p{percent:02d}" for percent in exported])


if __name__ == "__main__":
    unittest.main()
