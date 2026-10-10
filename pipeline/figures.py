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
DIAGNOSTIC_METRICS = {
    "kge-compass": ("kge_gupta_2009", "kge_kling_2012"),
    "low-flow": ("kge_1_over_q",),
    "ruzzante": (
        "nse_seasonal", "r_seasonal", "alpha_seasonal", "variance_share_seasonal",
        "nse_interannual", "r_interannual", "alpha_interannual", "variance_share_interannual",
        "nse_irregular", "r_irregular", "alpha_irregular", "variance_share_irregular",
    ),
}
DIAGNOSTIC_LABELS = {
    "kge-compass": "KGE formulation comparison",
    "low-flow": "Low-flow KGE",
    "ruzzante": "Ruzzante decomposition",
}


def canonical_metric_order(view: str) -> tuple[str, ...]:
    keys = set(DIAGNOSTIC_METRICS[view])
    return tuple(metric["key"] for metric in canon.load()["metrics"] if metric["key"] in keys)


def canonical_model_order() -> dict[str, int]:
    return {model["key"]: i for i, model in enumerate(canon.load()["models"])}


plt.rcParams.update({
    "svg.fonttype": "path", "svg.hashsalt": "shyft-bench", "font.family": "DejaVu Sans",
    "font.size": 8, "axes.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
    "xtick.major.width": 0.6, "ytick.major.width": 0.6, "axes.grid": True, "axes.axisbelow": True,
    "grid.color": "#dddddd", "grid.linewidth": 0.5,
})


def goal_label(goal: str) -> str:
    return goal.upper().replace("_", "+")


def matched_cohort(table: pd.DataFrame, models: list[str], goal: str) -> list[str]:
    """Stations with finite headline values for every model and both pcorr arms."""
    sub = table[table["model"].isin(models) & (table["goal"] == goal)
                & (table["metric"] == HEADLINE) & (table["period_kind"] == PERIOD_KIND)]
    sub = sub[np.isfinite(sub["value"])]
    required = {(model, pcorr) for model in models for pcorr in (False, True)}
    return sorted(
        station for station, rows in sub.groupby("station")
        if required.issubset(set(zip(rows["model"], rows["pcorr"])))
    )


def scoreboard_table(table: pd.DataFrame, pcorr: bool) -> pd.DataFrame:
    """One row per (model, goal) for one pcorr arm, over the matched cohort."""
    keys = {k: f"median_{k}" for k in EFFICIENCY_KEYS}
    rows = []
    models = [m["key"] for m in canon.load()["models"] if m["key"] in set(table["model"])]
    cohorts = {goal: matched_cohort(table, models, goal) for goal in canon.load()["goals"]}
    for model in models:
        for goal in canon.load()["goals"]:
            cohort = cohorts[goal]
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


def diagnostic_table(table: pd.DataFrame, spec: dict) -> pd.DataFrame:
    """Select one Lean-declared diagnostic view without collapsing its variants or seeds."""
    view = spec["view"]
    if view not in DIAGNOSTIC_METRICS:
        raise ValueError(f"unsupported diagnostic view: {view}")
    required = {"model", "goal", "forcing", "direction", "pcorr", "optimizer", "seed",
                "station", "metric", "value"}
    missing = required - set(table.columns)
    if missing:
        raise ValueError(f"metric table is missing columns: {sorted(missing)}")
    rows = table
    for column in ("forcing", "direction", "pcorr", "optimizer"):
        value = spec[column]
        rows = rows[rows[column].isna()] if value is None else rows[rows[column] == value]
    rows = rows[rows["metric"].isin(DIAGNOSTIC_METRICS[view])]
    model_order = canonical_model_order()
    metric_order = {metric: i for i, metric in enumerate(canonical_metric_order(view))}
    rows = rows.assign(_model_rank=rows["model"].map(model_order.get),
                       _metric_rank=rows["metric"].map(metric_order.get)).sort_values(
        ["_model_rank", "model", "goal", "station", "seed", "_metric_rank", "metric"],
        kind="stable", na_position="first", ignore_index=True)
    return rows.drop(columns=["_model_rank", "_metric_rank"])


def _sample_columns(frame: pd.DataFrame) -> list[str]:
    return [column for column in frame.columns if column not in {"metric", "value"}]


def _sample_label(row: pd.Series) -> str:
    fields = [str(row[column]) for column in ("model", "goal", "station") if column in row]
    seed = row["seed"] if "seed" in row else None
    fields.append(f"seed={seed if pd.notna(seed) else 'none'}")
    if "experiment_id" in row:
        fields.insert(0, str(row["experiment_id"]))
    return " / ".join(fields)


def _diagnostic_title(spec: dict) -> str:
    pcorr = "on" if spec["pcorr"] else "off"
    direction = spec["direction"] if spec["direction"] is not None else "all"
    return (f"{DIAGNOSTIC_LABELS[spec['view']]} — forcing {spec['forcing']}; "
            f"direction {direction}; pcorr {pcorr}; optimizer {spec['optimizer']}")


def _save_diagnostic(fig) -> bytes:
    fig.tight_layout()
    buffer = io.BytesIO()
    fig.savefig(buffer, format="svg", metadata={"Date": None, "Creator": "shyft-bench-platform"})
    plt.close(fig)
    return buffer.getvalue()


def render_diagnostic(frame: pd.DataFrame, spec: dict) -> bytes:
    """Render a diagnostic view, keeping individual stations, goals and seeds visible."""
    view = spec["view"]
    if view not in DIAGNOSTIC_METRICS:
        raise ValueError(f"unsupported diagnostic view: {view}")
    if frame.empty:
        raise ValueError(f"{view} view has no metric rows")

    identity = _sample_columns(frame)
    fig, ax = plt.subplots(figsize=(max(7.2, min(18, len(frame) * 0.28)), 4.2))
    colors = canon.model_colours()
    if view == "kge-compass":
        metrics = list(canonical_metric_order(view))
        wide = frame.pivot(index=identity, columns="metric", values="value")
        points = wide.loc[:, metrics].dropna()
        for row in points.reset_index().to_dict("records"):
            model = row.get("model")
            color = colors.get(model, "#000000")
            x, y = row[metrics[0]], row[metrics[1]]
            ax.scatter(x, y, color=color, s=22)
            ax.annotate(_sample_label(pd.Series(row)), (x, y), fontsize=5, alpha=0.7)
        ax.set_xlabel("KGE (Gupta et al., 2009)")
        ax.set_ylabel("KGE (Kling et al., 2012)")
    elif view == "low-flow":
        labels = [_sample_label(row) for _, row in frame.iterrows()]
        for index, row in frame.iterrows():
            color = colors.get(row["model"], "#000000")
            ax.scatter(index, row["value"], color=color, s=22)
        ax.set_xticks(range(len(frame)), labels, rotation=90, ha="center", fontsize=6)
        ax.set_ylabel("KGE(1/Q)")
        ax.set_xlabel("Model / goal / station / seed")
    else:
        metrics = list(canonical_metric_order(view))
        positions = np.arange(len(metrics))
        groups = frame.groupby(identity, sort=False, dropna=False)
        for _, sample in groups:
            values = sample.set_index("metric")["value"].reindex(metrics)
            label = _sample_label(sample.iloc[0])
            model = sample.iloc[0]["model"]
            color = colors.get(model, "#000000")
            ax.plot(positions, values, marker="o", markersize=2.5, linewidth=0.7,
                    color=color, label=label)
        ax.set_xticks(positions, [metric.replace("_", " ") for metric in metrics],
                      rotation=45, ha="right", fontsize=6)
        ax.set_ylabel("Characterized metric value")
        ax.set_xlabel("Ruzzante component")
        ax.legend(frameon=False, fontsize=5, title="Model / goal / station / seed")
    ax.set_title(_diagnostic_title(spec), fontsize=7.5, loc="left")
    ax.grid(axis="x", visible=False)
    return _save_diagnostic(fig)
