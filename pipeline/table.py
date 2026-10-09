"""The internal long metrics table: one row per experiment, model, goal, forcing, direction,
pcorr, optimiser, seed, station, period kind and metric. Never published.
"""
import numpy as np
import pandas as pd

from . import canon, importer
from .importer import Source
from .metrics import all_metrics

COLUMNS = ["experiment_id", "model", "goal", "forcing", "direction", "pcorr", "optimizer",
           "seed", "station", "period_kind", "metric", "value", "n_days", "period_start",
           "period_end"]


def _day_numbers(dates: pd.Series) -> np.ndarray:
    return dates.values.astype("datetime64[D]").astype(np.int64)


def validation_mask(dates: pd.Series, intervals: list[dict]) -> np.ndarray:
    """Simulation minus calibration, as Lean's `Experiment.validationPeriods?` derives it
    (day numbers since 1970-01-01, end exclusive)."""
    days = _day_numbers(dates)
    mask = np.zeros(len(days), dtype=bool)
    for iv in intervals:
        mask |= (days >= iv["startDay"]) & (days < iv["endDay"])
    return mask


def build(experiment_id: str, model: str, optimizer: str = "bobyqa",
          ) -> tuple[pd.DataFrame, dict[tuple[bool, str], Source]]:
    entry = canon.catalogue_entry(experiment_id)
    if model not in entry["models"]:
        raise ValueError(f"{model} is not a model of {experiment_id}")
    if entry["direction"] is None or entry["validation"] is None:
        raise ValueError(f"{experiment_id} has no calibration/validation split")
    if entry["optimizer"] != optimizer:
        raise ValueError(f"{experiment_id} is a {entry['optimizer']} experiment")
    rows = []
    sources: dict[tuple[bool, str], Source] = {}
    for pcorr in entry["pcorr"]:
        for goal in entry["goals"]:
            path = importer.series_path(model, entry["forcing"], pcorr, goal, optimizer)
            frame, source = importer.read_series(path)
            sources[(pcorr, goal)] = source
            inside = validation_mask(frame["date"], entry["validation"])
            if not inside.all():
                raise ValueError(f"{path.name} has days outside the validation period of "
                                 f"{experiment_id}; this slice imports validation series only")
            for station, one in frame.groupby("station", sort=True):
                one = one.sort_values("date")
                paired = one["qobs"].notna() & one["qsim"].notna()
                values = all_metrics(one["qobs"].to_numpy(), one["qsim"].to_numpy(), one["date"])
                start, end = one["date"].min().date().isoformat(), one["date"].max().date().isoformat()
                for metric, value in values.items():
                    rows.append((experiment_id, model, goal, entry["forcing"], entry["direction"],
                                 pcorr, optimizer, None, station, "validation", metric, value,
                                 int(paired.sum()), start, end))
    table = pd.DataFrame(rows, columns=COLUMNS)
    table["seed"] = table["seed"].astype("string")
    return table.sort_values(["pcorr", "goal", "station", "metric"], kind="stable",
                             ignore_index=True), sources
