"""Efficiency metrics by hydroeval; Ruzzante decomposition by `pipeline.ruzzante`.

hydroeval 0.1.0 (read in its source): `kge` is Gupta et al. (2009), `kgeprime` is Kling et
al. (2012), `pbias` is 100 * sum(obs - sim) / sum(obs) (positive = underestimation).
"""
import warnings

import hydroeval as he
import numpy as np

from . import canon
from .ruzzante import LEAN_KEYS, compute_ruzzante

EFFICIENCY_KEYS = ("nse", "kge_gupta_2009", "kge_kling_2012", "pbias", "kge_1_over_q")
LOW_FLOW_EPSILON_FACTOR = 0.01


def _scalar(result) -> float:
    value = float(np.asarray(result).reshape(-1)[0])
    return value if np.isfinite(value) else float("nan")


def efficiency_metrics(obs, sim) -> dict[str, float]:
    """The hydroeval metrics on the paired, finite days; zero-flow days are kept."""
    obs = np.asarray(obs, dtype=float)
    sim = np.asarray(sim, dtype=float)
    keep = np.isfinite(obs) & np.isfinite(sim)
    obs, sim = obs[keep], sim[keep]
    if obs.size < 2:
        return {k: float("nan") for k in EFFICIENCY_KEYS}
    eps = LOW_FLOW_EPSILON_FACTOR * float(np.mean(obs))
    with warnings.catch_warnings(), np.errstate(all="ignore"):
        warnings.simplefilter("ignore")
        out = {
            "nse": _scalar(he.evaluator(he.nse, sim, obs)),
            "kge_gupta_2009": _scalar(he.evaluator(he.kge, sim, obs)[0]),
            "kge_kling_2012": _scalar(he.evaluator(he.kgeprime, sim, obs)[0]),
            "pbias": _scalar(he.evaluator(he.pbias, sim, obs)),
        }
        # eps is passed explicitly; hydroeval would otherwise recompute it from the same data.
        out["kge_1_over_q"] = (_scalar(he.evaluator(he.kge, sim, obs, transform="inv",
                                                    epsilon=eps)[0]) if eps > 0 else float("nan"))
    return out


def all_metrics(obs, sim, dates) -> dict[str, float]:
    """Every metric of the Lean vocabulary for one station and period."""
    out = efficiency_metrics(obs, sim)
    old = compute_ruzzante(obs, sim, dates)
    out.update({LEAN_KEYS[k]: v for k, v in old.items()})
    expected = {m["key"] for m in canon.load()["metrics"]}
    if set(out) != expected:
        raise AssertionError(f"metric keys differ from Lean: {set(out) ^ expected}")
    return out
