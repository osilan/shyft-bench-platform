"""Figures of the `models-pcorr` page (D-032), after the founder's NHC 2026 talk.

- `cdf`: four panels (KGE, KGE(1/Q), NSE interannual, NSE seasonal), one per-catchment empirical
  CDF per model, for one pcorr setting.
- `pcorr-compare`: KGE and NSE seasonal CDFs, rows pcorr off and on.
- `pcorr-by-regime`: Pbias without and with pcorr, and the KGE gain from pcorr, by regime.
- `pcorr-map`: the KGE gain from pcorr for RPMSTK on the pinned map.

All figures use the Shyft runs calibrated to KGE, as in the talk. The cohort of a panel is the
catchments finite for every model and both pcorr settings, so switching the pcorr selector
compares the same catchments. Catchments are unlabelled (D-032); seeds are never pooled.
"""
import csv
import json

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm

from . import canon
from .figures import canonical_model_order, save_svg
from .summaries import PERIOD_KIND, matched_cohort, summary_percents

GOAL = "kge"
KGE = "kge_gupta_2009"
PBIAS = "pbias"
# (metric key, axis label, x range shown). The range only limits the axis: every catchment
# counts in the CDF.
CDF_PANELS = (
    (KGE, "KGE (Gupta et al., 2009)", (-0.5, 1.0)),
    ("kge_1_over_q", "KGE(1/Q)", (-1.5, 1.0)),
    ("nse_interannual", "NSE interannual", (-1.0, 1.0)),
    ("nse_seasonal", "NSE seasonal", (-2.0, 1.0)),
)
COMPARE_PANELS = (CDF_PANELS[0], CDF_PANELS[3])
# The stacks of the talk's undercatch figure: snow-tiles stacks with and without Penman-Monteith.
REGIME_MODELS = ("ptstk", "ptsthbv", "rpmstk")
MAP_MODEL = "rpmstk"
SEED_STYLES = ("-", "--", ":", "-.")
ATTRIBUTES = canon.ROOT / "data/catchments/attributes.csv"
OUTLINE = canon.ROOT / "data/catchments/norway_outline.geojson"


def _check_metrics(keys) -> None:
    known = {m["key"] for m in canon.load()["metrics"]}
    unknown = set(keys) - known
    if unknown:
        raise ValueError(f"metrics not in the Lean vocabulary: {sorted(unknown)}")


def _select(table: pd.DataFrame, spec: dict, metrics) -> pd.DataFrame:
    """Validation rows of the spec's forcing, direction and optimiser, goal KGE."""
    _check_metrics(metrics)
    rows = table[(table["forcing"] == spec["forcing"]) & (table["optimizer"] == spec["optimizer"])
                 & (table["period_kind"] == PERIOD_KIND) & (table["goal"] == GOAL)
                 & table["metric"].isin(metrics)]
    if spec["direction"] is not None:
        rows = rows[rows["direction"] == spec["direction"]]
    rows = rows.copy()
    rows["value"] = pd.to_numeric(rows["value"], errors="coerce")
    return rows


def _models(rows: pd.DataFrame) -> list[str]:
    return [m for m in canonical_model_order() if m in set(rows["model"])]


def _seed_key(seed) -> str:
    return "" if pd.isna(seed) else str(seed)


# ── per-catchment CDFs ────────────────────────────────────────────────────────

def per_catchment(table: pd.DataFrame, spec: dict, metrics, pcorrs) -> pd.DataFrame:
    """One row per catchment, model, seed, metric and pcorr setting, over each metric's cohort."""
    rows = _select(table, spec, metrics)
    models = _models(rows)
    order = canonical_model_order()
    parts = []
    for metric in metrics:
        cohort = matched_cohort(rows, models, GOAL, metric=metric, pcorrs=(False, True))
        parts.append(rows[(rows["metric"] == metric) & rows["station"].isin(cohort)
                          & rows["pcorr"].isin(pcorrs)])
    frame = pd.concat(parts, ignore_index=True)[["pcorr", "metric", "model", "seed", "station", "value"]]
    rank = {m: i for i, m in enumerate(metrics)}
    return (frame.assign(_m=frame["metric"].map(rank), _o=frame["model"].map(order),
                         _s=frame["seed"].map(_seed_key))
            .sort_values(["pcorr", "_m", "_o", "_s", "station"], kind="stable")
            .drop(columns=["_m", "_o", "_s"]).reset_index(drop=True))


def cdf_table(table: pd.DataFrame, spec: dict) -> pd.DataFrame:
    return per_catchment(table, spec, [m for m, _, _ in CDF_PANELS], (spec["pcorr"],))


def compare_table(table: pd.DataFrame, spec: dict) -> pd.DataFrame:
    return per_catchment(table, spec, [m for m, _, _ in COMPARE_PANELS], (False, True))


def _ecdf_panel(ax, panel: pd.DataFrame, title: str, xlim) -> None:
    colours = canon.model_colours()
    for model in [m for m in canonical_model_order() if m in set(panel["model"])]:
        rows = panel[panel["model"] == model]
        for index, (seed, sample) in enumerate(rows.groupby(rows["seed"].map(_seed_key), sort=True)):
            values = np.sort(sample["value"].to_numpy(dtype=float))
            fraction = np.arange(1, len(values) + 1) / len(values)
            label = f"{model.upper()} (med={np.median(values):.2f})" if index == 0 else None
            ax.step(values, fraction, where="post", color=colours[model], linewidth=1.3,
                    linestyle=SEED_STYLES[index % len(SEED_STYLES)], label=label)
    ax.axvline(0, color="#999999", linewidth=0.6, linestyle="--")
    ax.set_xlim(*xlim)
    ax.set_ylim(0, 1.0)
    ax.set_title(f"{title} · n = {panel['station'].nunique()} catchments", fontsize=9)
    ax.set_xlabel(title)
    ax.legend(frameon=False, loc="upper left", fontsize=6.5)


def _subtitle(spec: dict, pcorr_text: str) -> str:
    return (f"Forcing {spec['forcing']} · {spec['direction'] or 'all directions'} · "
            f"{spec['optimizer'].upper()} · calibrated to {GOAL.upper()} · {pcorr_text} · "
            f"{PERIOD_KIND} period · catchments matched across models and both pcorr settings")


def render_cdf(frame: pd.DataFrame, spec: dict) -> bytes:
    if frame.empty:
        raise ValueError("cdf view has no matched catchments")
    fig, axes = plt.subplots(1, len(CDF_PANELS), figsize=(14, 3.8), sharey=True)
    for ax, (metric, title, xlim) in zip(axes, CDF_PANELS):
        _ecdf_panel(ax, frame[frame["metric"] == metric], title, xlim)
    axes[0].set_ylabel("Cumulative fraction of catchments")
    fig.suptitle(_subtitle(spec, f"precipitation correction {'on' if spec['pcorr'] else 'off'}"),
                 fontsize=8)
    return save_svg(fig)


def render_pcorr_compare(frame: pd.DataFrame, spec: dict) -> bytes:
    if frame.empty:
        raise ValueError("pcorr-compare view has no matched catchments")
    fig, axes = plt.subplots(2, len(COMPARE_PANELS), figsize=(11, 7), sharey=True, squeeze=False)
    for row, pcorr in enumerate((False, True)):
        for column, (metric, title, xlim) in enumerate(COMPARE_PANELS):
            ax = axes[row, column]
            _ecdf_panel(ax, frame[(frame["pcorr"] == pcorr) & (frame["metric"] == metric)], title, xlim)
        axes[row, 0].set_ylabel(f"Pcorr {'on' if pcorr else 'off'}\ncumulative fraction")
    fig.suptitle(_subtitle(spec, "rows: precipitation correction off and on"), fontsize=8)
    return save_svg(fig)


# ── Pbias and KGE gain by regime ──────────────────────────────────────────────

def _paired(table: pd.DataFrame, spec: dict, models) -> pd.DataFrame:
    """Per (model, station): Pbias and KGE off and on, finite in both arms, and the KGE gain."""
    rows = _select(table, spec, [PBIAS, KGE])
    rows = rows[rows["model"].isin(models)]
    if rows["seed"].notna().any():
        raise ValueError("pcorr-by-regime pools catchments across models, never across seeds")
    wide = rows.pivot_table(index=["model", "station"], columns=["metric", "pcorr"], values="value",
                            aggfunc="first")
    columns = [(PBIAS, False), (PBIAS, True), (KGE, False), (KGE, True)]
    wide = wide.reindex(columns=pd.MultiIndex.from_tuples(columns)).dropna()
    paired = pd.DataFrame({
        "pbias_off": wide[(PBIAS, False)], "pbias_on": wide[(PBIAS, True)],
        "kge_gain": wide[(KGE, True)] - wide[(KGE, False)],
    }).reset_index()
    return paired


def regime_table(table: pd.DataFrame, spec: dict) -> pd.DataFrame:
    """Box statistics per regime of Pbias off, Pbias on and the KGE gain, pooled over REGIME_MODELS."""
    paired = _paired(table, spec, REGIME_MODELS)
    regime_of = {s["id"]: s["regime"] for s in canon.load()["stations"]}
    paired["regime"] = paired["station"].map(regime_of)
    percents = summary_percents("box")
    rows = []
    for regime in [r["name"] for r in canon.load()["regimes"]]:
        group = paired[paired["regime"] == regime]
        if group.empty:
            continue
        for quantity in ("pbias_off", "pbias_on", "kge_gain"):
            values = group[quantity].to_numpy(dtype=float)
            row = {"regime": regime, "quantity": quantity, "models": "+".join(REGIME_MODELS),
                   "n_catchments": group["station"].nunique(), "n_pairs": len(values)}
            row.update({f"p{p:02d}": v for p, v in zip(percents, np.percentile(values, percents))})
            rows.append(row)
    return pd.DataFrame(rows)


def _box(ax, stats: pd.Series, position: float, colour: str, hatch: str = "", alpha: float = 0.6):
    p = [f"p{x:02d}" for x in summary_percents("box")]
    box = {"whislo": stats[p[0]], "q1": stats[p[1]], "med": stats[p[2]], "q3": stats[p[3]],
           "whishi": stats[p[4]], "fliers": []}
    artist = ax.bxp([box], positions=[position], widths=0.34, showfliers=False, patch_artist=True,
                    manage_ticks=False)
    for patch in artist["boxes"]:
        patch.set(facecolor=colour, alpha=alpha, hatch=hatch, edgecolor="#333333", linewidth=0.6)
    for line in artist["medians"]:
        line.set(color="white", linewidth=1.4)


def render_pcorr_by_regime(frame: pd.DataFrame, spec: dict) -> bytes:
    if frame.empty:
        raise ValueError("pcorr-by-regime view has no paired catchments")
    colours = {r["name"]: r["colour"] for r in canon.load()["regimes"]}
    regimes = [r["name"] for r in canon.load()["regimes"] if r["name"] in set(frame["regime"])]
    fig, (left, right) = plt.subplots(1, 2, figsize=(12, 4.6))
    for i, regime in enumerate(regimes):
        group = frame[frame["regime"] == regime].set_index("quantity")
        _box(left, group.loc["pbias_off"], i - 0.19, colours[regime], alpha=0.35)
        _box(left, group.loc["pbias_on"], i + 0.19, colours[regime], hatch="///", alpha=0.75)
        _box(right, group.loc["kge_gain"], i, colours[regime])
    labels = [f"{r}\nn = {int(frame[frame['regime'] == r]['n_catchments'].iloc[0])}" for r in regimes]
    for ax in (left, right):
        ax.set_xticks(range(len(regimes)), labels)
        ax.axhline(0, color="#888888", linewidth=0.6, linestyle="--")
        ax.grid(axis="x", visible=False)
    left.set_ylabel("Pbias (%), positive = simulation too low\n100 · Σ(obs − sim) / Σ obs")
    left.set_title("Volume bias without (plain) and with (hatched) precipitation correction", fontsize=9)
    right.set_ylabel("KGE gain (pcorr on − off)")
    right.set_title("KGE gain from precipitation correction", fontsize=9)
    models = " · ".join(m.upper() for m in REGIME_MODELS)
    fig.suptitle(f"{models}, pooled · boxes at percentiles {', '.join(map(str, summary_percents('box')))} · "
                 f"{_subtitle(spec, 'pcorr off and on')}", fontsize=7.5)
    return save_svg(fig)


# ── map of the KGE gain ───────────────────────────────────────────────────────

def load_attributes() -> dict[str, tuple[float, float]]:
    with ATTRIBUTES.open(newline="") as f:
        return {r["station"]: (float(r["lat"]), float(r["lon"])) for r in csv.DictReader(f)}


def load_outline() -> list[list[tuple[float, float]]]:
    geometry = json.loads(OUTLINE.read_text())["features"][0]["geometry"]
    return [[tuple(p) for p in polygon[0]] for polygon in geometry["coordinates"]]


def map_table(table: pd.DataFrame, spec: dict) -> pd.DataFrame:
    paired = _paired(table, spec, (MAP_MODEL,))
    location = load_attributes()
    missing = sorted(set(paired["station"]) - set(location))
    if missing:
        raise ValueError(f"stations without pinned attributes: {missing}")
    return pd.DataFrame({
        "model": MAP_MODEL, "station": paired["station"],
        "lat": paired["station"].map(lambda s: location[s][0]),
        "lon": paired["station"].map(lambda s: location[s][1]),
        "kge_gain": paired["kge_gain"],
    }).sort_values("station", kind="stable").reset_index(drop=True)


def colour_limit(values: np.ndarray) -> float:
    """Symmetric colour limit: the 95th percentile of the absolute values, rounded up to 0.05, so
    a few extreme catchments (a hugely negative KGE without pcorr) do not wash out the rest; they
    take the end colours and are counted in the title."""
    return max(0.05, float(np.ceil(np.nanpercentile(np.abs(values), 95) / 0.05) * 0.05))


def render_pcorr_map(frame: pd.DataFrame, spec: dict) -> bytes:
    if frame.empty:
        raise ValueError("pcorr-map view has no paired catchments")
    fig, ax = plt.subplots(figsize=(5.4, 7.6))
    for polygon in load_outline():
        xs, ys = zip(*polygon)
        ax.fill(xs, ys, color="#e8e8e8", edgecolor="#9a9a9a", linewidth=0.4, zorder=1)
    limit = colour_limit(frame["kge_gain"].to_numpy(dtype=float))
    norm = TwoSlopeNorm(vmin=-limit, vcenter=0.0, vmax=limit)
    points = ax.scatter(frame["lon"], frame["lat"], c=frame["kge_gain"], cmap="RdBu", norm=norm,
                        s=34, edgecolors="white", linewidths=0.5, zorder=3)
    bar = fig.colorbar(points, ax=ax, orientation="horizontal", fraction=0.04, pad=0.03,
                       extend="both")
    bar.set_label(f"KGE gain from precipitation correction, {MAP_MODEL.upper()}")
    ax.set_aspect(1 / np.cos(np.radians(65)))
    ax.set_axis_off()
    better = int((frame["kge_gain"] > 0).sum())
    beyond = int((frame["kge_gain"].abs() > limit).sum())
    ax.set_title(f"{MAP_MODEL.upper()}, calibrated to {GOAL.upper()}: pcorr improves KGE in "
                 f"{better} of {len(frame)} catchments\n{beyond} beyond ±{limit:.2f} shown in the "
                 f"end colours", fontsize=8.5)
    return save_svg(fig)
