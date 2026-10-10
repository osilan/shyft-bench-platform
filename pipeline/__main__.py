"""Build and check the declared forward legacy figure subset."""
import argparse
import io
import sys
from pathlib import Path

import pandas as pd

from . import canon, export, figures, table

INTERNAL = canon.ROOT / "build" / "metrics"


def experiment_for(spec: dict, model: str) -> dict:
    found = [e for e in canon.load()["catalogue"]
             if e["provenance"] == "zenodo-import" and e["forcing"] == spec["forcing"]
             and e["direction"] == spec["direction"] and e["models"] == [model]
             and e["optimizer"] == spec["optimizer"]]
    if len(found) != 1:
        raise LookupError(f"{spec['id']}: expected one legacy experiment for {model}, got {len(found)}")
    return found[0]


def slice_models(spec: dict) -> list[str]:
    eligible = {
        model
        for experiment in canon.load()["catalogue"]
        if experiment["provenance"] == "zenodo-import"
        and experiment["forcing"] == spec["forcing"]
        and experiment["direction"] == spec["direction"]
        and experiment["optimizer"] == spec["optimizer"]
        for model in experiment["models"]
    }
    return [model["key"] for model in canon.load()["models"] if model["key"] in eligible]


def parquet_bytes(frame: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    frame.to_parquet(buffer, engine="pyarrow", index=False, compression="zstd")
    return buffer.getvalue()


def build(dist: Path) -> int:
    specs = canon.declared_figures("published")
    tables, sources, experiment_ids = [], [], []
    for model in slice_models(specs[0]):
        experiment = experiment_for(specs[0], model)
        frame, srcs = table.build(experiment["id"], model, specs[0]["optimizer"])
        export.write_once(INTERNAL / f"{experiment['id']}.parquet", parquet_bytes(frame))
        tables.append(frame)
        experiment_ids.append(experiment["id"])
        sources += [{"experiment_id": experiment["id"], "path": s.key, "sha256": s.sha256}
                for _, s in sorted(srcs.items())]
    metrics = pd.concat(tables, ignore_index=True)

    artifacts, index = [], []
    for spec in specs:
        if spec["view"] == "scoreboard":
            frame = figures.scoreboard_table(metrics, spec["pcorr"])
            svg = figures.render_scoreboard(frame)
        elif spec["view"] == "cdf":
            frame = figures.cdf_table(metrics, spec)
            svg = figures.render_cdf(frame, spec)
        else:
            frame = figures.diagnostic_table(metrics, spec)
            svg = figures.render_diagnostic(frame, spec)
        svg_rel, csv_rel = export.figure_paths(spec["id"])
        csv = figures.table_csv(frame)
        export.write_once(dist / svg_rel, svg)
        export.write_once(dist / csv_rel, csv)
        for kind, rel, data in (("figure", svg_rel, svg), ("table", csv_rel, csv)):
            artifacts.append({"id": spec["id"], "kind": kind, "path": rel,
                              "sha256": export.sha256(data), "experiment_ids": experiment_ids,
                              "sources": sources})
        index.append(export.index_entry(spec))
    (dist / "figure-index.json").write_bytes(export.dumps({"figures": index}))
    (dist / "canon.json").write_bytes(canon.CANON_PATH.read_bytes())
    (dist / "catalogue.json").write_bytes(export.dumps(canon.load()["catalogue"]))
    (dist / "manifest.json").write_bytes(export.dumps(export.manifest(artifacts)))
    problems = export.check_dist(dist, "published")
    for p in problems:
        print("FAIL:", p)
    print(f"published {len(index)} figures to {dist}")
    return 1 if problems else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="pipeline")
    parser.add_argument("command", choices=["build", "check"])
    parser.add_argument("--dist", type=Path, default=export.DEFAULT_DIST)
    parser.add_argument("--scope", choices=["first-slice", "published", "grid"],
                        default="published",
                        help="declared figure set the published ids must equal")
    args = parser.parse_args(argv)
    if args.command == "build":
        return build(args.dist)
    problems = export.check_dist(args.dist, args.scope)
    for p in problems:
        print("FAIL:", p)
    print("grid check passed" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
