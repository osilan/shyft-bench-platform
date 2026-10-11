"""Summary tables derived from the internal long metrics table."""
import numpy as np
import pandas as pd

from . import canon

HEADLINE = "kge_gupta_2009"
PERIOD_KIND = "validation"


def summary_percents(kind: str) -> tuple[int, ...]:
    """Return the Lean-exported percentile list for a summary view."""
    try:
        return tuple(canon.load()["summaryPercents"][kind])
    except KeyError:
        raise ValueError(f"unsupported summary percentile list: {kind}") from None


def matched_cohort(table: pd.DataFrame, models: list[str], goal: str,
                   metric: str = HEADLINE,
                   pcorrs: tuple[bool, ...] = (False, True)) -> list[str]:
    """Stations with finite values for every model/seed and requested pcorr arm."""
    sub = table[table["model"].isin(models) & (table["goal"] == goal)
                & (table["metric"] == metric) & (table["period_kind"] == PERIOD_KIND)]
    seed_groups = {
        (model, None if pd.isna(seed) else seed)
        for model, seed in sub[["model", "seed"]].itertuples(index=False, name=None)
    }
    required = {(model, seed, pcorr) for model, seed in seed_groups for pcorr in pcorrs}
    sub = sub[sub["pcorr"].isin(pcorrs)]
    sub = sub[np.isfinite(sub["value"])]
    return sorted(
        station for station, rows in sub.groupby("station")
        if required.issubset({
            (model, None if pd.isna(seed) else seed, pcorr)
            for model, seed, pcorr in rows[["model", "seed", "pcorr"]].itertuples(
                index=False, name=None
            )
        })
    )


def percentile_table(table: pd.DataFrame, spec: dict, metrics: list[str],
                     percents: list[int]) -> pd.DataFrame:
    """Summarize each model/goal/metric/seed over its panel's matched stations."""
    required = {"model", "goal", "forcing", "direction", "pcorr", "optimizer", "seed",
                "station", "period_kind", "metric", "value"}
    missing = required - set(table.columns)
    if missing:
        raise ValueError(f"metric table is missing columns: {sorted(missing)}")

    rows = table
    for column in ("forcing", "direction", "pcorr", "optimizer"):
        value = spec[column]
        rows = rows[rows[column].isna()] if value is None else rows[rows[column] == value]
    rows = rows[rows["period_kind"] == PERIOD_KIND]
    rows = rows[rows["metric"].isin(metrics)].copy()
    rows["value"] = pd.to_numeric(rows["value"], errors="coerce")
    rows = rows[rows["station"].notna()]

    percent_columns = [f"p{percent:02d}" for percent in percents]
    output = []
    model_order = {model["key"]: index for index, model in enumerate(canon.load()["models"])}
    for metric in dict.fromkeys(metrics):
        for goal in dict.fromkeys(rows["goal"]):
            panel = rows[(rows["metric"] == metric) & (rows["goal"] == goal)]
            present = set(panel["model"].dropna())
            models = sorted(present, key=lambda model: (model_order.get(model, len(model_order)),
                                                        model))
            if not models:
                continue
            cohort = matched_cohort(panel, models, goal, metric=metric,
                                    pcorrs=(spec["pcorr"],))
            matched = panel[panel["station"].isin(cohort)]
            for (model, seed), sample in matched.groupby(
                    ["model", "seed"], dropna=False, sort=False):
                values = sample.loc[np.isfinite(sample["value"]), "value"].to_numpy(dtype=float)
                n = len(values)
                if n != len(cohort):
                    raise ValueError(
                        f"percentile cohort size mismatch for {model}/{seed}: "
                        f"used {n} values from {len(cohort)} matched stations"
                    )
                percentiles = np.percentile(values, percents, method="linear")
                row = {"model": model, "goal": goal, "metric": metric, "seed": seed,
                       "n": n}
                row.update(zip(percent_columns, percentiles))
                output.append(row)

    return pd.DataFrame(output, columns=[
        "model", "goal", "metric", "seed", "n", *percent_columns,
    ])
