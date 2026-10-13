"""Figures of the `goal-functions` page (D-032), after the founder's NHC 2026 talk.

One figure per model and pcorr setting (the page's selectors):
- `goal-generalism`: a 2 by 3 grid (KGE, KGE(1/Q), NSE interannual, NSE seasonal, NSE irregular,
  Pbias), one box per calibration goal, KGE family in blue and NSE family in red.
- `bias-variability`: the KGE components r, alpha and beta, one box per goal.

A panel's cohort is the catchments finite for that metric under every goal, so the goals are
compared on the same catchments (one axis, bench.compare.matched). Boxes are drawn at the Lean
box percentiles from every catchment; the axis range never drops a catchment. Seeds are never
pooled: a model with seeds is refused until the page declares how to show them.
"""
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import canon
from .figures import goal_label, save_svg
from .summaries import PERIOD_KIND, summary_percents

GENERALISM_PANELS = (
    ("kge_gupta_2009", "KGE (Gupta et al., 2009)"),
    ("kge_1_over_q", "KGE(1/Q)"),
    ("nse_interannual", "NSE interannual"),
    ("nse_seasonal", "NSE seasonal"),
    ("nse_irregular", "NSE irregular"),
    ("pbias", "Pbias (%), positive = simulation too low"),
)
COMPONENT_PANELS = (
    ("kge_r", "r: correlation"),
    ("kge_alpha", "alpha: variability ratio σ_sim / σ_obs"),
    ("kge_beta", "beta: bias ratio μ_sim / μ_obs"),
)
# Reference line per metric: the ideal value where one exists.
REFERENCE = {"pbias": 0.0, "kge_r": 1.0, "kge_alpha": 1.0, "kge_beta": 1.0}
# The goal families of the talk; a goal belongs to the one family its key names (kge, lkge,
# bckge, kge_lkge and kge_bckge are KGE; nse, lnse, bcnse, nse_lnse and nse_bcnse are NSE).
FAMILY_COLOUR = {"kge": "#4393c3", "nse": "#d6604d"}


def family(goal: str) -> str:
    names = [name for name in FAMILY_COLOUR if name in goal]
    if len(names) != 1:
        raise ValueError(f"goal {goal!r} must name exactly one family, found {names}")
    return names[0]


def goal_table(table: pd.DataFrame, spec: dict, metrics) -> pd.DataFrame:
    """Box statistics per goal and metric for the spec's model and pcorr, over each metric's
    catchments finite under every goal."""
    known = {m["key"] for m in canon.load()["metrics"]}
    if set(metrics) - known:
        raise ValueError(f"metrics not in the Lean vocabulary: {sorted(set(metrics) - known)}")
    rows = table[(table["model"] == spec["model"]) & (table["pcorr"] == spec["pcorr"])
                 & (table["forcing"] == spec["forcing"]) & (table["optimizer"] == spec["optimizer"])
                 & (table["period_kind"] == PERIOD_KIND) & table["metric"].isin(metrics)]
    if spec["direction"] is not None:
        rows = rows[rows["direction"] == spec["direction"]]
    if rows["seed"].notna().any():
        raise ValueError("goal-functions figures never pool seeds; seeded runs need a declared view")
    goals = [g for g in canon.load()["goals"] if g in set(rows["goal"])]
    percents = summary_percents("box")
    out = []
    for metric in metrics:
        sub = rows[rows["metric"] == metric]
        wide = sub.pivot_table(index="station", columns="goal", values="value", aggfunc="first")
        wide = wide.reindex(columns=goals).dropna()
        for goal in goals:
            values = wide[goal].to_numpy(dtype=float)
            if not len(values):
                continue
            row = {"model": spec["model"], "pcorr": spec["pcorr"], "goal": goal, "metric": metric,
                   "n": len(values)}
            row.update({f"p{p:02d}": v for p, v in zip(percents, np.percentile(values, percents))})
            out.append(row)
    return pd.DataFrame(out)


def generalism_table(table: pd.DataFrame, spec: dict) -> pd.DataFrame:
    return goal_table(table, spec, [m for m, _ in GENERALISM_PANELS])


def components_table(table: pd.DataFrame, spec: dict) -> pd.DataFrame:
    return goal_table(table, spec, [m for m, _ in COMPONENT_PANELS])


def _panel(ax, frame: pd.DataFrame, metric: str, title: str) -> None:
    panel = frame[frame["metric"] == metric]
    goals = [g for g in canon.load()["goals"] if g in set(panel["goal"])]
    p = [f"p{x:02d}" for x in summary_percents("box")]
    for i, goal in enumerate(goals):
        s = panel[panel["goal"] == goal].iloc[0]
        artist = ax.bxp([{"whislo": s[p[0]], "q1": s[p[1]], "med": s[p[2]], "q3": s[p[3]],
                          "whishi": s[p[4]], "fliers": []}],
                        positions=[i], widths=0.6, showfliers=False, patch_artist=True,
                        manage_ticks=False)
        for patch in artist["boxes"]:
            patch.set(facecolor=FAMILY_COLOUR[family(goal)], alpha=0.65, edgecolor="#333333",
                      linewidth=0.7)
        for line in artist["medians"]:
            line.set(color="white", linewidth=1.6)
        ax.text(i, s[p[2]], f"{s[p[2]]:.2f}", ha="center", va="bottom", fontsize=6.5,
                fontweight="bold", color="#111111")
    families = [family(g) for g in goals]
    split = next((i for i in range(1, len(goals)) if families[i] != families[i - 1]), None)
    if split is not None:
        ax.axvline(split - 0.5, color="#999999", linewidth=0.7, linestyle=":")
    if metric in REFERENCE:
        ax.axhline(REFERENCE[metric], color="#555555", linewidth=0.7, linestyle="--")
    ax.set_xticks(range(len(goals)), [goal_label(g) for g in goals], rotation=40, ha="right",
                  fontsize=7)
    n = sorted(set(panel["n"].astype(int)))
    ax.set_title(f"{title} · n = {n[0] if len(n) == 1 else f'{n[0]}–{n[-1]}'} catchments",
                 fontsize=9)
    ax.grid(axis="x", visible=False)


def _suptitle(fig, spec: dict, what: str) -> None:
    fig.suptitle(f"{what} · {spec['model'].upper()} · pcorr {'on' if spec['pcorr'] else 'off'} · "
                 f"forcing {spec['forcing']} · {spec['direction']} · {spec['optimizer'].upper()} · "
                 f"{PERIOD_KIND} period · boxes at percentiles "
                 f"{', '.join(map(str, summary_percents('box')))}; KGE family blue, NSE family red",
                 fontsize=8)


def render_generalism(frame: pd.DataFrame, spec: dict) -> bytes:
    if frame.empty:
        raise ValueError("goal-generalism view has no catchments")
    fig, axes = plt.subplots(2, 3, figsize=(13, 7.5))
    for ax, (metric, title) in zip(axes.ravel(), GENERALISM_PANELS):
        _panel(ax, frame, metric, title)
    _suptitle(fig, spec, "Goal-function generalism")
    return save_svg(fig)


def render_components(frame: pd.DataFrame, spec: dict) -> bytes:
    if frame.empty:
        raise ValueError("bias-variability view has no catchments")
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))
    for ax, (metric, title) in zip(axes, COMPONENT_PANELS):
        _panel(ax, frame, metric, title)
    _suptitle(fig, spec, "Bias and variability (KGE components, Gupta et al. 2009)")
    return save_svg(fig)
