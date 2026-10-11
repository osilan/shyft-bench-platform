"""The canon, catalogue and figure grid, exported from Lean (never retyped here).

`python3 -m pipeline.canon` regenerates pipeline/canon.json from ShyftBench/;
`python3 -m pipeline.canon --check` fails if the committed file is stale.
"""
import json
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANON_PATH = Path(__file__).resolve().parent / "canon.json"
LEAN_SCRIPT = Path(__file__).resolve().parent / "lean_export.lean"


def run_lean_export() -> str:
    proc = subprocess.run(["lake", "env", "lean", "--run", str(LEAN_SCRIPT)], cwd=ROOT,
                          capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"Lean export failed:\n{proc.stdout}\n{proc.stderr}")
    return proc.stdout


@lru_cache(maxsize=1)
def load() -> dict:
    return json.loads(CANON_PATH.read_text())


def model_colours() -> dict[str, str]:
    return {m["key"]: m["colour"] for m in load()["models"]}


def catalogue_entry(experiment_id: str) -> dict:
    for e in load()["catalogue"]:
        if e["id"] == experiment_id:
            return e
    raise KeyError(f"experiment {experiment_id!r} is not in the Lean catalogue")


def declared_figures(scope: str = "grid") -> list[dict]:
    """`grid` is the whole declared grid; `first-slice` and `published` are Lean-declared subsets."""
    grid = load()["figureGrid"]
    if scope == "grid":
        return grid
    if scope == "first-slice":
        ids = set(load()["firstSlice"])
        return [f for f in grid if f["id"] in ids]
    if scope == "published":
        by_id = {f["id"]: f for f in grid}
        return [by_id[i] for i in load()["published"]]
    raise ValueError(scope)


def main(argv: list[str]) -> int:
    fresh = run_lean_export()
    if "--check" in argv:
        if CANON_PATH.read_text() != fresh:
            print("pipeline/canon.json is stale; run python3 -m pipeline.canon")
            return 1
        print("pipeline/canon.json is up to date")
        return 0
    CANON_PATH.write_text(fresh)
    print(f"wrote {CANON_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
