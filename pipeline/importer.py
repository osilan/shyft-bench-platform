"""Read-only import of the legacy Shyft result files (D-006).

Only the daily series columns are read. The metric columns stored in the legacy CSVs
(`sim-*_result.csv`) are never read.
"""
import hashlib
import io
import os
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from . import canon

ROOT = canon.ROOT


def legacy_root() -> Path:
    return Path(os.environ.get("SHYFT_LEGACY_ROOT", ROOT.parent / "shyft-hydro-benchmarking"))


def legacy_output_dir() -> Path:
    return legacy_root() / "shyft-data" / "output"


@dataclass(frozen=True)
class Source:
    key: str  # path below shyft-data/output, the same on every machine
    sha256: str


def series_path(model: str, forcing: str, pcorr: bool, goal: str, optimizer: str) -> Path:
    if optimizer != "bobyqa":
        raise ValueError(f"first slice imports BOBYQA only, not {optimizer!r}")
    folder = f"{model}_bc{'_pcorr' if pcorr else ''}"
    return legacy_output_dir() / folder / f"{forcing}_{model}_discharge_sim-{goal}_{optimizer}.csv"


def station_id(stid: str) -> str:
    """Legacy ids carry a trailing point number: `178.1.0` is station `178.1`."""
    return re.sub(r"\.0$", "", stid)


def read_series(path: Path) -> tuple[pd.DataFrame, Source]:
    """Returns station, date (day), qobs, qsim; and the source record with its SHA-256."""
    data = path.read_bytes()
    frame = pd.read_csv(io.BytesIO(data), usecols=["stid", "time", "qobs", "q"],
                        dtype={"stid": str})
    frame["station"] = frame.pop("stid").map(station_id)
    frame["date"] = (pd.to_datetime(frame.pop("time"), utc=True)
                     .dt.tz_localize(None).dt.floor("D"))
    frame = frame.rename(columns={"q": "qsim"})
    if frame.duplicated(["station", "date"]).any():
        raise ValueError(f"{path.name}: duplicate (station, date) rows")
    known = {s["id"] for s in canon.load()["stations"]}
    unknown = set(frame["station"]) - known
    if unknown:
        raise ValueError(f"{path.name}: stations outside the Lean regime table: {sorted(unknown)}")
    source = Source(key=str(path.relative_to(legacy_output_dir())),
                    sha256=hashlib.sha256(data).hexdigest())
    return frame[["station", "date", "qobs", "qsim"]], source


def legacy_git_commit() -> str | None:
    import subprocess
    proc = subprocess.run(["git", "-C", str(legacy_root()), "rev-parse", "HEAD"],
                          capture_output=True, text=True, check=False)
    return proc.stdout.strip() if proc.returncode == 0 else None
