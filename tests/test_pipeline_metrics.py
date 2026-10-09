import math
import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import canon, importer  # noqa: E402
from pipeline.metrics import EFFICIENCY_KEYS, all_metrics, efficiency_metrics  # noqa: E402
from pipeline.ruzzante import LEAN_KEYS, compute_ruzzante  # noqa: E402

# Eight days with three zero-flow days. Reference values from plain numpy formulas
# (Gupta 2009, Kling 2012, Nash-Sutcliffe, hydroeval's PBIAS sign), not from hydroeval.
OBS = np.array([0.0, 0.0, 1.0, 2.0, 3.0, 0.5, 4.0, 0.0])
SIM = np.array([0.1, 0.0, 0.8, 2.2, 2.5, 0.7, 3.0, 0.4])
REF = {
    "nse": 0.9064895635673624,
    "kge_gupta_2009": 0.7516570878101492,
    "kge_kling_2012": 0.8103537822442387,
    "pbias": 7.619047619047618,
    "kge_1_over_q": 0.18133857990340208,
}
# The same series with the zero-flow days dropped (the old LSTM rule, q <= 0).
KGE_1_OVER_Q_ZERO_DAYS_DROPPED = 0.7161455015127699

# Output of the OLD code (compute_ruzzante_metrics.compute_ruzzante, legacy commit
# 4d386fb31266e88f8c87d8c8f17f69fdb2a4c298), captured before this port existed.
OLD_SYNTHETIC = {
    "nseinter": -0.18734905041690042, "nse_seas": 0.9555637733611377,
    "nse_irr": -1.54663657022635, "r_seas": 0.9896047548522604,
    "r_inter": -0.2573138395797225, "r_irr": -0.006308750441025625,
    "alpha_seas": 0.8773791427054476, "alpha_inter": 0.2462330425039221,
    "alpha_irr": 1.2373456913387146, "var_seas": 0.931702920308629,
    "var_inter": 0.016452929838486827, "var_irr": 0.05184414985288403,
}
OLD_REAL = {  # ptgsk_bc, goal kge, BOBYQA, 2001-01-01..2020-06-12
    "177.4": {
        "nseinter": 0.3781627396070488, "nse_seas": -1.7678105059705782,
        "nse_irr": -0.7914758482921034, "r_seas": -0.17492179345269476,
        "r_inter": 0.6625929540475926, "r_irr": 0.41299892705571967,
        "alpha_seas": 1.163992377302724, "alpha_inter": 0.9093046950460041,
        "alpha_irr": 1.3938373245714768, "var_seas": 0.1717199437837722,
        "var_inter": 0.09635024707451981, "var_irr": 0.7319298091417081},
    "178.1": {
        "nseinter": -0.09611093639529766, "nse_seas": -2.568662548873111,
        "nse_irr": -0.7166001562782687, "r_seas": -0.3909154436978911,
        "r_inter": 0.5320328290234044, "r_irr": 0.4547145172728921,
        "alpha_seas": 1.2274514373806968, "alpha_inter": 1.1478005348621767,
        "alpha_irr": 1.4156335817611492, "var_seas": 0.17770864505390077,
        "var_inter": 0.09492719623005294, "var_irr": 0.7273641587160462},
}


def synthetic_pair():
    rng = np.random.default_rng(42)
    dates = pd.date_range("2001-01-01", periods=365 * 12 + 3, freq="D")
    t = np.arange(len(dates))
    obs = (5 + 4 * np.sin(2 * np.pi * t / 365.25) + 0.5 * np.sin(2 * np.pi * t / (365.25 * 4))
           + rng.gamma(2, 0.5, len(t)))
    sim = 4.5 + 3.5 * np.sin(2 * np.pi * (t - 5) / 365.25) + rng.gamma(2, 0.6, len(t))
    obs[100:110] = np.nan
    return obs, sim, dates


class MetricReferenceTest(unittest.TestCase):
    """bench.metrics.canonical: one reference value per metric."""

    def setUp(self):
        self.metrics = efficiency_metrics(OBS, SIM)

    def test_bench_metrics_canonical_nse(self):
        self.assertAlmostEqual(self.metrics["nse"], REF["nse"], places=12)

    def test_bench_metrics_canonical_kge_is_gupta_2009(self):
        self.assertAlmostEqual(self.metrics["kge_gupta_2009"], REF["kge_gupta_2009"], places=12)

    def test_bench_metrics_canonical_kge_is_kling_2012(self):
        self.assertAlmostEqual(self.metrics["kge_kling_2012"], REF["kge_kling_2012"], places=12)
        self.assertNotAlmostEqual(self.metrics["kge_kling_2012"], self.metrics["kge_gupta_2009"],
                                  places=3)

    def test_bench_metrics_canonical_pbias(self):
        self.assertAlmostEqual(self.metrics["pbias"], REF["pbias"], places=10)

    def test_bench_metrics_canonical_kge_inverse_flow_keeps_zero_flow_days(self):
        self.assertAlmostEqual(self.metrics["kge_1_over_q"], REF["kge_1_over_q"], places=12)
        keep = OBS > 0
        dropped = efficiency_metrics(OBS[keep], SIM[keep])["kge_1_over_q"]
        self.assertAlmostEqual(dropped, KGE_1_OVER_Q_ZERO_DAYS_DROPPED, places=12)
        self.assertGreater(abs(dropped - self.metrics["kge_1_over_q"]), 0.5)

    def test_bench_metrics_canonical_epsilon_is_a_hundredth_of_mean_observed_flow(self):
        # Epsilon follows the mean of the kept observations: scaling both series by 10
        # scales epsilon by 10 and must leave KGE(1/Q) unchanged.
        scaled = efficiency_metrics(10 * OBS, 10 * SIM)["kge_1_over_q"]
        self.assertAlmostEqual(scaled, REF["kge_1_over_q"], places=10)

    def test_bench_metrics_canonical_missing_observations_are_deleted_pairwise(self):
        obs = np.append(OBS, np.nan)
        sim = np.append(SIM, 9.0)
        self.assertEqual(efficiency_metrics(obs, sim), self.metrics)

    def test_bench_metrics_canonical_keys_are_the_lean_vocabulary(self):
        self.assertEqual(set(EFFICIENCY_KEYS) | set(LEAN_KEYS.values()),
                         {m["key"] for m in canon.load()["metrics"]})

    def test_bench_metrics_canonical_constant_observations_give_nan(self):
        values = efficiency_metrics(np.ones(5), np.arange(5.0))
        self.assertTrue(math.isnan(values["nse"]))


class RuzzanteCharacterisationTest(unittest.TestCase):
    """bench.metrics.canonical: the port reproduces the old code's output."""

    def assert_matches(self, got, pinned):
        self.assertEqual(set(got), set(pinned))
        for key, value in pinned.items():
            self.assertAlmostEqual(got[key], value, places=10, msg=key)

    def test_bench_metrics_canonical_ruzzante_synthetic_series(self):
        obs, sim, dates = synthetic_pair()
        self.assert_matches(compute_ruzzante(obs, sim, dates), OLD_SYNTHETIC)

    @unittest.skipUnless(importer.legacy_output_dir().is_dir(), "legacy results not available")
    def test_bench_metrics_canonical_ruzzante_real_stations(self):
        path = importer.series_path("ptgsk", "seNorge", False, "kge", "bobyqa")
        frame, _ = importer.read_series(path)
        # The old loader compared 06:00 UTC stamps with the string "2020-06-12" (midnight),
        # which dropped that last day.
        frame = frame[frame["date"] < "2020-06-12"]
        for station, pinned in OLD_REAL.items():
            one = frame[frame["station"] == station].sort_values("date")
            got = compute_ruzzante(one["qobs"], one["qsim"], one["date"])
            self.assert_matches(got, pinned)

    def test_bench_metrics_canonical_ruzzante_needs_ten_continuous_years(self):
        obs, sim, dates = synthetic_pair()
        got = compute_ruzzante(obs[:365 * 5], sim[:365 * 5], dates[:365 * 5])
        self.assertTrue(all(math.isnan(v) for v in got.values()))

    def test_bench_metrics_canonical_all_metrics_cover_the_lean_vocabulary(self):
        obs, sim, dates = synthetic_pair()
        self.assertEqual(set(all_metrics(obs, sim, dates)),
                         {m["key"] for m in canon.load()["metrics"]})


if __name__ == "__main__":
    unittest.main()
