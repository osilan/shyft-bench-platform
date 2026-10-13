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
                   metric: str | tuple[str, ...] = HEADLINE,
                   pcorrs: tuple[bool, ...] = (False, True)) -> list[str]:
    """Stations with finite values for every model/seed/metric and requested pcorr arm."""
    metrics = (metric,) if isinstance(metric, str) else metric
    sub = table[table["model"].isin(models) & (table["goal"] == goal)
                & table["metric"].isin(metrics) & (table["period_kind"] == PERIOD_KIND)]
    seed_groups = {
        (model, None if pd.isna(seed) else seed)
        for model, seed in sub[["model", "seed"]].itertuples(index=False, name=None)
    }
    required = {
        (model, seed, metric, pcorr)
        for model, seed in seed_groups for metric in metrics for pcorr in pcorrs
    }
    sub = sub[sub["pcorr"].isin(pcorrs)]
    sub = sub[np.isfinite(sub["value"])]
    return sorted(
        station for station, rows in sub.groupby("station")
        if required.issubset({
            (model, None if pd.isna(seed) else seed, metric, pcorr)
            for model, seed, metric, pcorr in rows[["model", "seed", "metric", "pcorr"]].itertuples(
                index=False, name=None
            )
        })
    )
