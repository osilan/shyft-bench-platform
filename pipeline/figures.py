"""Scoreboard figure: models x goals, median over the matched cohort.

Matched cohort (D-018, pcorr axis): a catchment counts for a (model, goal) cell only if its
headline metric is finite in both pcorr arms. Both figures of a pair therefore use the same
catchments. The headline metric is KGE (Gupta et al., 2009), computed on the validation period.
"""
import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from . import canon  # noqa: E402
from .metrics import EFFICIENCY_KEYS  # noqa: E402

HEADLINE = "kge_gupta_2009"
HEADLINE_LABEL = "KGE (Gupta et al., 2009)"
PERIOD_KIND = "validation"

plt.rcParams.update({
    "svg.fonttype": "path", "svg.hashsalt": "shyft-bench", "font.family": "DejaVu Sans",
    "font.size": 8, "axes.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "xtick.major.width": 0.6, "ytick.major.width": 0.6, "axes.grid": True, "axes.axisbelow": True,
    "grid.color": "#dddddd", "grid.linewidth": 0.5,
})


def goal_label(goal: str) -> str:
    return goal.upper().replace("_", "+")


def matched_cohort(table: pd.DataFrame, model: str, goal: str) -> list[str]:
    """Stations with a finite headline value in every pcorr arm."""
    sub = table[(table["model"] == model) & (table["goal"] == goal)
                & (table["metric"] == HEADLINE) & (table["period_kind"] == PERIOD_KIND)]
    sub = sub[np.isfinite(sub["value"])]
    arms = sorted(table["pcorr"].unique())
    stations = None
    for arm in arms:
        found = set(sub.loc[sub["pcorr"] == arm, "station"])
        stations = found if stations is None else stations & found
    return sorted(stations or [])


def scoreboard_table(table: pd.DataFrame, pcorr: bool) -> pd.DataFrame:
    """One row per (model, goal) for one pcorr arm, over the matched cohort."""
    keys = {k: f"median_{k}" for k in EFFICIENCY_KEYS}
    rows = []
    for model in [m["key"] for m in canon.load()["models"] if m["key"] in set(table["model"])]:
        for goal in canon.load()["goals"]:
            cohort = matched_cohort(table, model, goal)
            sub = table[(table["model"] == model) & (table["goal"] == goal)
                        & (table["pcorr"] == pcorr) & (table["period_kind"] == PERIOD_KIND)
                        & table["station"].isin(cohort)]
            if sub.empty:
                continue
            row = {"model": model, "goal": goal, "forcing": sub["forcing"].iloc[0],
                   "direction": sub["direction"].iloc[0], "pcorr": "on" if pcorr else "off",
                   "optimizer": sub["optimizer"].iloc[0], "period_kind": PERIOD_KIND,
                   "n_matched": len(cohort)}
            wide = sub.pivot(index="station", columns="metric", values="value")
            for metric, column in keys.items():
                row[column] = float(np.nanmedian(wide[metric]))
            row[f"p25_{HEADLINE}"] = float(np.nanpercentile(wide[HEADLINE], 25))
            row[f"p75_{HEADLINE}"] = float(np.nanpercentile(wide[HEADLINE], 75))
            rows.append(row)
    return pd.DataFrame(rows)


def table_csv(frame: pd.DataFrame) -> bytes:
    return frame.to_csv(index=False, float_format="%.6f", lineterminator="\n").encode()


def render_scoreboard(frame: pd.DataFrame) -> bytes:
    colours = canon.model_colours()
    goals = canon.load()["goals"]
    models = list(dict.fromkeys(frame["model"]))
    first = frame.iloc[0]
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    width = 0.7 / max(len(models), 1)
    for i, model in enumerate(models):
        sub = frame[frame["model"] == model].set_index("goal")
        present = [g for g in goals if g in sub.index]
        x = np.array([goals.index(g) for g in present], dtype=float)
        x += (i - (len(models) - 1) / 2) * width
        med = sub.loc[present, f"median_{HEADLINE}"].to_numpy()
        lo = sub.loc[present, f"p25_{HEADLINE}"].to_numpy()
        hi = sub.loc[present, f"p75_{HEADLINE}"].to_numpy()
        ax.vlines(x, lo, hi, color=colours[model], linewidth=1.4, alpha=0.55)
        ax.plot(x, med, "o", color=colours[model], markersize=5, markeredgecolor="white",
                markeredgewidth=0.5, label=model.upper())
    ax.axhline(0, color="#888888", linewidth=0.6, linestyle="--")
    ax.set_xticks(range(len(goals)), [goal_label(g) for g in goals], rotation=30, ha="right")
    ax.set_xlabel("Calibration goal function")
    ax.set_ylabel(f"{HEADLINE_LABEL}\nmedian and interquartile range")
    ax.grid(axis="x", visible=False)
    ax.legend(frameon=False, title="Model", loc="lower left", ncols=len(models))
    cohort = int(frame["n_matched"].min()), int(frame["n_matched"].max())
    n = str(cohort[0]) if cohort[0] == cohort[1] else f"{cohort[0]}-{cohort[1]}"
    ax.set_title(f"{first['forcing']}, {first['direction']}, {first['optimizer'].upper()}, "
                 f"precipitation correction {first['pcorr']}; {PERIOD_KIND} period; "
                 f"matched cohort n = {n} catchments", fontsize=7.5, loc="left")
    fig.tight_layout()
    buffer = io.BytesIO()
    fig.savefig(buffer, format="svg", metadata={"Date": None, "Creator": "shyft-bench-platform"})
    plt.close(fig)
    return buffer.getvalue()
