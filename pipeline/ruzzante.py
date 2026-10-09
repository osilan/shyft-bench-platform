"""Ruzzante et al. NSE decomposition (seasonal, interannual, irregular).

Port of `decomp_utils.decompose_pair` and `compute_ruzzante_metrics.compute_ruzzante` from
../shyft-hydro-benchmarking/catchments_simulation/service_based/analysis/ (legacy commit
4d386fb31266e88f8c87d8c8f17f69fdb2a4c298). The arithmetic is kept as in the old code; the
characterisation test pins its output. `nse_cb` is not ported: no Lean metric names it.
"""
import numpy as np
import pandas as pd

MIN_YEARS = 10  # minimum consecutive years for the FFT
FFT_CUTOFF = 2.0  # cycles/year separating interannual from irregular

# Old result key -> Lean `Metric.key`.
LEAN_KEYS = {
    "nse_seas": "nse_seasonal", "r_seas": "r_seasonal", "alpha_seas": "alpha_seasonal",
    "var_seas": "variance_share_seasonal",
    "nseinter": "nse_interannual", "r_inter": "r_interannual",
    "alpha_inter": "alpha_interannual", "var_inter": "variance_share_interannual",
    "nse_irr": "nse_irregular", "r_irr": "r_irregular", "alpha_irr": "alpha_irregular",
    "var_irr": "variance_share_irregular",
}


def _doy_climatology(q: np.ndarray, doys: np.ndarray) -> np.ndarray:
    doys_c = np.minimum(doys, 365)
    return pd.DataFrame({"q": q, "d": doys_c}).groupby("d")["q"].transform("mean").values


def _longest_run(valid: np.ndarray, dates: pd.DatetimeIndex) -> tuple[int, int]:
    days = dates.values.astype("datetime64[D]").astype(np.int64)
    best_s, best_n = 0, 0
    cur_s, cur_n = 0, 0
    for i in range(len(valid)):
        if not valid[i]:
            cur_s, cur_n = i + 1, 0
            continue
        if i == 0 or (valid[i - 1] and days[i] - days[i - 1] == 1):
            cur_n += 1
        else:
            cur_s, cur_n = i, 1
        if cur_n > best_n:
            best_s, best_n = cur_s, cur_n
    return int(best_s), int(best_s + best_n)


def decompose_pair(qobs, qsim, dates, min_years=MIN_YEARS, fft_cutoff=FFT_CUTOFF):
    """Decompose obs and sim jointly on their longest shared continuous daily run."""
    valid = np.isfinite(qobs) & np.isfinite(qsim)
    s, e = _longest_run(valid, dates)
    if (e - s) < min_years * 365:
        return None

    q_obs, q_sim, dates_ = qobs[s:e], qsim[s:e], dates[s:e]
    doys = np.minimum(dates_.dayofyear, 365)
    n = e - s

    seas_obs = _doy_climatology(q_obs, doys)
    seas_sim = _doy_climatology(q_sim, doys)
    clim_obs = pd.Series(q_obs, index=doys).groupby(level=0).mean().sort_index().values
    clim_sim = pd.Series(q_sim, index=doys).groupby(level=0).mean().sort_index().values

    freq = np.fft.fftfreq(n) * 365.0
    lo_mask = (np.abs(freq) <= fft_cutoff).astype(float)
    hi_mask = (np.abs(freq) > fft_cutoff).astype(float)

    def split(x):
        f = np.fft.fft(x - _doy_climatology(x, doys))
        return np.fft.ifft(f * lo_mask).real, np.fft.ifft(f * hi_mask).real

    inter_obs, irr_obs = split(q_obs)
    inter_sim, irr_sim = split(q_sim)

    var_q = float(np.var(q_obs))
    if var_q < 1e-12:
        return None

    return {
        "seas_obs": seas_obs, "seas_sim": seas_sim,
        "seas_clim_obs": clim_obs, "seas_clim_sim": clim_sim,
        "inter_obs": inter_obs, "inter_sim": inter_sim,
        "irr_obs": irr_obs, "irr_sim": irr_sim,
        "var_seas": float(np.var(seas_obs) / var_q),
        "var_inter": float(np.var(inter_obs) / var_q),
        "var_irr": float(np.var(irr_obs) / var_q),
    }


def _nse(obs, sim) -> float:
    denom = np.sum((obs - np.mean(obs)) ** 2)
    if denom < 1e-12:
        return np.nan
    return float(1.0 - np.sum((obs - sim) ** 2) / denom)


def _pearson_r(obs, sim) -> float:
    mask = np.isfinite(obs) & np.isfinite(sim)
    if mask.sum() < 3:
        return np.nan
    r = float(np.corrcoef(obs[mask], sim[mask])[0, 1])
    return r if np.isfinite(r) else np.nan


def _alpha(obs, sim) -> float:
    s_obs = float(np.std(obs[np.isfinite(obs)]))
    s_sim = float(np.std(sim[np.isfinite(sim)]))
    if s_obs < 1e-12:
        return np.nan
    return s_sim / s_obs


OLD_KEYS = tuple(LEAN_KEYS)


def compute_ruzzante(qobs, qsim, dates) -> dict:
    """Old-code result keys (see LEAN_KEYS); all NaN if there is no 10-year continuous run."""
    p = decompose_pair(np.asarray(qobs, dtype=float), np.asarray(qsim, dtype=float),
                       pd.DatetimeIndex(dates))
    if p is None:
        return {k: np.nan for k in OLD_KEYS}
    return {
        "nseinter": _nse(p["inter_obs"], p["inter_sim"]),
        "nse_seas": _nse(p["seas_clim_obs"], p["seas_clim_sim"]),
        "nse_irr": _nse(p["irr_obs"], p["irr_sim"]),
        "r_seas": _pearson_r(p["seas_obs"], p["seas_sim"]),
        "r_inter": _pearson_r(p["inter_obs"], p["inter_sim"]),
        "r_irr": _pearson_r(p["irr_obs"], p["irr_sim"]),
        "alpha_seas": _alpha(p["seas_obs"], p["seas_sim"]),
        "alpha_inter": _alpha(p["inter_obs"], p["inter_sim"]),
        "alpha_irr": _alpha(p["irr_obs"], p["irr_sim"]),
        "var_seas": p["var_seas"], "var_inter": p["var_inter"], "var_irr": p["var_irr"],
    }
