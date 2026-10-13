import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import canon, table  # noqa: E402
from pipeline.summaries import matched_cohort, summary_percents  # noqa: E402


def rows(values, pcorr=False):
    return pd.DataFrame([
        ("synthetic", model, goal, "seNorge", "forward", pcorr, "bobyqa", seed,
         station, "validation", metric, value, 10, "2001-01-01", "2001-01-10")
        for model, goal, metric, station, seed, value in values
    ], columns=table.COLUMNS)


class MatchedCohortTest(unittest.TestCase):
    def test_cohort_is_the_stations_finite_for_every_model(self):
        values = []
        for model, station_values in (
                ("ptgsk", {"a": 0, "b": 10, "c": 20, "missing": 100, "infinite": 200}),
                ("lstm", {"a": 30, "b": 40, "c": 50, "infinite": float("inf")})):
            values.extend((model, "kge", "kge_gupta_2009", station, None, value)
                          for station, value in station_values.items())
        cohort = matched_cohort(rows(values), ["ptgsk", "lstm"], "kge", pcorrs=(False,))
        self.assertEqual(cohort, ["a", "b", "c"])

    def test_cohort_requires_every_seed_to_be_finite_at_each_station(self):
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
        cohort = matched_cohort(rows(values), ["ptgsk", "lstm"], "kge", pcorrs=(False,))
        self.assertEqual(cohort, ["b", "c"])

    def test_cohort_requires_every_requested_pcorr_arm(self):
        off = rows([("ptgsk", "kge", "kge_gupta_2009", s, None, 0.5) for s in "abc"], pcorr=False)
        on = rows([("ptgsk", "kge", "kge_gupta_2009", s, None, 0.5) for s in "ab"], pcorr=True)
        data = pd.concat([off, on], ignore_index=True)
        self.assertEqual(matched_cohort(data, ["ptgsk"], "kge"), ["a", "b"])
        self.assertEqual(matched_cohort(data, ["ptgsk"], "kge", pcorrs=(False,)), ["a", "b", "c"])


class SummaryPercentsTest(unittest.TestCase):
    def test_box_percents_follow_the_lean_export(self):
        self.assertEqual(summary_percents("box"), tuple(canon.load()["summaryPercents"]["box"]))
        with self.assertRaises(ValueError):
            summary_percents("cdf")


if __name__ == "__main__":
    unittest.main()
