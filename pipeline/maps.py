"""Pinned catchment locations and the Norway outline (bench.catchments.attributes, D-032)."""
import csv
import json

import numpy as np

from . import canon

ATTRIBUTES = canon.ROOT / "data/catchments/attributes.csv"
OUTLINE = canon.ROOT / "data/catchments/norway_outline.geojson"


def load_attributes() -> dict[str, tuple[float, float]]:
    """Station id to (latitude, longitude), WGS84."""
    with ATTRIBUTES.open(newline="") as f:
        return {r["station"]: (float(r["lat"]), float(r["lon"])) for r in csv.DictReader(f)}


def load_outline() -> list[list[tuple[float, float]]]:
    geometry = json.loads(OUTLINE.read_text())["features"][0]["geometry"]
    return [[tuple(p) for p in polygon[0]] for polygon in geometry["coordinates"]]


def draw_outline(ax) -> None:
    """Norway in light grey, with the aspect of a map at 65° N; no axes."""
    for polygon in load_outline():
        xs, ys = zip(*polygon)
        ax.fill(xs, ys, color="#e8e8e8", edgecolor="#9a9a9a", linewidth=0.4, zorder=1)
    ax.set_aspect(1 / np.cos(np.radians(65)))
    ax.set_axis_off()
