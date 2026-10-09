"""Manifest, figure index, write-once output and the declared-grid check."""
import hashlib
import importlib.metadata
import json
import subprocess
from pathlib import Path

from . import canon, importer

ROOT = canon.ROOT
DEFAULT_DIST = ROOT / "dashboard" / "dist-data"
FIGURES, TABLES = "figures", "tables"


class WriteOnceError(RuntimeError):
    pass


def write_once(path: Path, data: bytes) -> bool:
    """Write a result file; identical content is a no-op, different content is refused."""
    if path.exists():
        if path.read_bytes() == data:
            return False
        raise WriteOnceError(f"{path} exists with different content; results are never overwritten")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return True


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _git(*args: str) -> str:
    proc = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                          check=False)
    return proc.stdout.strip() if proc.returncode == 0 else ""


def code_version() -> dict:
    files = sorted(p for p in (ROOT / "pipeline").iterdir()
                   if p.suffix in {".py", ".lean", ".json"})
    tree = hashlib.sha256()
    for p in files:
        tree.update(p.name.encode() + b"\0" + p.read_bytes())
    libs = {name: importlib.metadata.version(name)
            for name in ("hydroeval", "matplotlib", "numpy", "pandas", "pyarrow", "scipy")}
    return {"commit": _git("rev-parse", "HEAD"),
            "dirty": bool(_git("status", "--porcelain", "--", "pipeline", "ShyftBench")),
            "pipeline_sha256": tree.hexdigest(), "libraries": libs}


def figure_paths(figure_id: str) -> tuple[str, str]:
    return f"{FIGURES}/{figure_id}.svg", f"{TABLES}/{figure_id}.csv"


def index_entry(spec: dict) -> dict:
    svg, csv = figure_paths(spec["id"])
    return {"id": spec["id"], "view": spec["view"], "forcing": spec["forcing"],
            "direction": spec["direction"], "pcorr": spec["pcorr"],
            "optimizer": spec["optimizer"], "svg": svg, "csv": csv}


def dumps(obj) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def manifest(artifacts: list[dict]) -> dict:
    code = code_version()
    return {
        "schema": 1,
        "code": code,
        "shyft": {"commit": canon.load()["shyftPin"],
                  "note": "platform pin (shyftPin); the legacy results were produced by an "
                          "earlier Shyft build whose commit is not recorded (unverified)"},
        "legacy_repo_commit": importer.legacy_git_commit(),
        "artifacts": [{**a, "code_commit": code["commit"],
                       "shyft_commit": None,
                       "platform_shyft_pin": canon.load()["shyftPin"]} for a in artifacts],
    }


def check_grid(published: list[str], declared: list[str]) -> list[str]:
    """Problems if a declared figure is missing or an undeclared one appears."""
    problems = [f"declared figure missing: {i}" for i in declared if i not in published]
    problems += [f"undeclared figure published: {i}" for i in published if i not in declared]
    problems += [f"duplicate id: {i}" for i in dict.fromkeys(published) if published.count(i) > 1]
    return problems


def check_dist(dist: Path, scope: str) -> list[str]:
    """The published directory equals the declared grid (`first-slice` or `grid`), and every
    listed file exists and matches its manifest checksum."""
    index_path, manifest_path = dist / "figure-index.json", dist / "manifest.json"
    problems = [f"{name} is missing" for name in ("canon.json", "catalogue.json")
                if not (dist / name).is_file()]
    if not index_path.is_file() or not manifest_path.is_file():
        return problems + ["figure-index.json or manifest.json is missing"]
    entries = json.loads(index_path.read_text())["figures"]
    declared = {f["id"]: f for f in canon.declared_figures(scope)}
    problems += check_grid([e["id"] for e in entries], list(declared))
    for e in entries:
        spec = declared.get(e["id"])
        if spec is not None and e != index_entry(spec):
            problems.append(f"{e['id']}: index entry differs from the Lean declaration")
    recorded = {a["path"]: a["sha256"] for a in json.loads(manifest_path.read_text())["artifacts"]}
    listed = set()
    for e in entries:
        for rel in (e["svg"], e["csv"]):
            listed.add(rel)
            file = dist / rel
            if not file.is_file():
                problems.append(f"{rel}: file missing")
            elif recorded.get(rel) != sha256(file.read_bytes()):
                problems.append(f"{rel}: checksum differs from the manifest")
    for folder in (FIGURES, TABLES):
        for file in sorted((dist / folder).glob("*")) if (dist / folder).is_dir() else []:
            if f"{folder}/{file.name}" not in listed:
                problems.append(f"{folder}/{file.name}: file is not in the figure index")
    return problems
