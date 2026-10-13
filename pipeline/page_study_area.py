"""Figures of the `study-area` page (D-032), after the founder's NHC 2026 talk.

- `regime-map`: every catchment of the frozen regime table at its pinned location, coloured by
  regime, with each regime's count.
- `variance-by-regime`: per regime, the median share of the observed discharge variance in its
  seasonal, interannual and irregular components (Ruzzante et al. 2025 decomposition).

The variance shares describe the observed flow: the decomposition computes them from observed
discharge only, and they are the same in every run of a catchment. The table takes that one
value per catchment and stops if two runs disagree.
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import canon, maps
from .figures import save_svg
from .summaries import PERIOD_KIND

SHARES = (
    ("variance_share_seasonal", "Seasonal", "#e5a73a"),
    ("variance_share_interannual", "Interannual", "#5a9fd0"),
    ("variance_share_irregular", "Irregular", "#6abf69"),
)
SAME_VALUE = 1e-9


def regime_map_table(table: pd.DataFrame, spec: dict) -> pd.DataFrame:
    """One row per catchment of the regime table: regime and pinned location."""
    location = maps.load_attributes()
    stations = canon.load()["stations"]
    missing = sorted(s["id"] for s in stations if s["id"] not in location)
    if missing:
        raise ValueError(f"stations without pinned attributes: {missing}")
    return pd.DataFrame([{"station": s["id"], "regime": s["regime"],
                          "lat": location[s["id"]][0], "lon": location[s["id"]][1]}
                         for s in stations])


def render_regime_map(frame: pd.DataFrame, spec: dict) -> bytes:
    regimes = canon.load()["regimes"]
    fig, ax = plt.subplots(figsize=(5.4, 7.6))
    maps.draw_outline(ax)
    for regime in regimes:
        rows = frame[frame["regime"] == regime["name"]]
        if rows.empty:
            continue
        ax.scatter(rows["lon"], rows["lat"], s=30, color=regime["colour"], edgecolors="white",
                   linewidths=0.5, zorder=3, label=f"{regime['name']} ({len(rows)})")
    ax.legend(frameon=False, loc="lower right", title="Hydrological regime", fontsize=8,
              title_fontsize=8)
    ax.set_title(f"{len(frame)} catchments by hydrological regime\n"
                 "(calc_hydrological_regime.r, frozen table, D-003)", fontsize=9)
    return save_svg(fig)


def variance_table(table: pd.DataFrame, spec: dict) -> pd.DataFrame:
    """Per regime: the median of each variance share over the catchments that have all three."""
    keys = [k for k, _, _ in SHARES]
    rows = table[(table["forcing"] == spec["forcing"]) & (table["period_kind"] == PERIOD_KIND)
                 & table["metric"].isin(keys)].copy()
    rows["value"] = pd.to_numeric(rows["value"], errors="coerce")
    rows = rows[np.isfinite(rows["value"])]
    spread = rows.groupby(["station", "metric"])["value"].agg(lambda s: s.max() - s.min())
    if (spread > SAME_VALUE).any():
        raise ValueError("variance shares differ between runs of one catchment; they must be "
                         "properties of the observed flow")
    shares = rows.groupby(["station", "metric"])["value"].first().unstack().reindex(columns=keys)
    shares = shares.dropna()
    regime_of = {s["id"]: s["regime"] for s in canon.load()["stations"]}
    shares["regime"] = shares.index.map(regime_of)
    out = []
    for regime in [r["name"] for r in canon.load()["regimes"]]:
        group = shares[shares["regime"] == regime]
        if group.empty:
            continue
        row = {"regime": regime, "n_catchments": len(group)}
        row.update({f"median_{k}": float(np.median(group[k])) for k in keys})
        out.append(row)
    return pd.DataFrame(out)


def render_variance(frame: pd.DataFrame, spec: dict) -> bytes:
    if frame.empty:
        raise ValueError("variance-by-regime view has no catchments")
    fig, ax = plt.subplots(figsize=(7.5, 5))
    x = np.arange(len(frame))
    bottom = np.zeros(len(frame))
    for key, label, colour in SHARES:
        values = frame[f"median_{key}"].to_numpy(dtype=float)
        ax.bar(x, values, bottom=bottom, width=0.6, color=colour, edgecolor="white", label=label)
        for xi, b, v in zip(x, bottom, values):
            if v >= 0.04:
                ax.text(xi, b + v / 2, f"{v:.2f}", ha="center", va="center", fontsize=8,
                        color="white", fontweight="bold")
        bottom += values
    for xi, top, n in zip(x, bottom, frame["n_catchments"]):
        ax.text(xi, top + 0.015, f"n = {n}", ha="center", va="bottom", fontsize=8, color="#555555")
    ax.set_xticks(x, frame["regime"])
    ax.set_ylabel("Median share of observed discharge variance")
    ax.set_ylim(0, 1.12)
    ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, loc="upper right", ncols=3, fontsize=8)
    ax.set_title("Variance decomposition of observed discharge by regime (Ruzzante et al. 2025) · "
                 f"forcing {spec['forcing']} · {PERIOD_KIND} period\nmedians per component, so a bar "
                 "need not sum to exactly 1", fontsize=8.5)
    return save_svg(fig)
