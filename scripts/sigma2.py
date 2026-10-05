#!/usr/bin/env python3
"""bench-sigma2: deterministic Sigma2 operations for shyft-bench-platform.

Every Sigma2 action goes through this tool. It is the only code that calls
kubectl (the workspace hook blocks raw kubectl), it pins the context and
namespace from config/sigma2.json, and it writes what it did to
runs/<run_id>/manifest.json. Same inputs, same outputs: the tool reproduces a
collection without any agent.

The founder authenticates; the tool never handles credentials.

First slice (collecting a finished run):
  preflight   local + pod checks; reports when a login is needed
  inventory   container directory listing and DTSS registration   (read-only)
  snapshot    pod code checksums, run settings, Shyft version      (read-only)
              and a proposed expected set for `complete`
  names       sample of existing series names and their shapes     (read-only)
  complete    present vs expected per run key                      (read-only)
  extract     complete series to NetCDF in a new pod folder         (writes in pod: --confirm)
  fetch       bring the extracted folder home, verify SHA-256       (writes locally)

Pod-side code lives in scripts/sigma2_pod/ and is piped to the pod's python on
stdin; nothing is copied into the pod. Standard library only.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config" / "sigma2.json"
POD_DIR = Path(__file__).resolve().parent / "sigma2_pod"
KUBECTL = os.environ.get("BENCH_SIGMA2_KUBECTL", "kubectl")

RUN_ID = re.compile(r"^\d{8}-\d{4}-[a-z0-9][a-z0-9-]*$")
# The legacy runner is not consistent: names may carry a prefix before "discharge-",
# put the variant before or after the station, and may end in "_rev". The stage is
# "sim" (whole period) or "cal" (calibration period). Most reverse runs carry no
# "_rev": a run is reverse when its calibration starts after its simulation starts.
SIMULATED = re.compile(
    r"^(?P<prefix>.*?)discharge-(?P<model>[a-z0-9_]+)-(?P<stage>sim|cal)-(?P<goal>[a-z0-9_]+)-(?P<optimizer>bobyqa|dream|sceua|global)"
    r"(?P<pcorr>-pcorr)?-(?:v(?P<variant>\d+)-(?P<station>[^/]+?)|(?P<station2>[^/]+?)-v(?P<variant2>\d+))"
    r"(?P<rev>_rev)?$")
OBSERVED = re.compile(r"^catchment/(?P<station>.+)\.discharge\.observed\.nve$")
SIMULATED_FIND = r"^.*discharge-.*$"
OBSERVED_FIND = r"^catchment\/.*\.discharge\.observed\.nve$"
AUTH_HINTS = ("unauthorized", "you must be logged in", "token", "expired", "oidc",
              "exec plugin", "credentials", "forbidden")

EXIT_USAGE, EXIT_POD, EXIT_AUTH, EXIT_VERIFY = 2, 3, 4, 5


class ToolError(Exception):
    code = 1


class AuthRequired(ToolError):
    code = EXIT_AUTH


class PodError(ToolError):
    code = EXIT_POD


class VerifyError(ToolError):
    code = EXIT_VERIFY


# ── configuration, git, manifest ──────────────────────────────────────────────

def load_config() -> dict:
    return json.loads(CONFIG.read_text())


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def git_state() -> dict:
    def git(*args):
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))}


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def write_json(path: Path, obj) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(obj, sort_keys=True, indent=1) + "\n").encode()
    path.write_bytes(data)
    return sha256_bytes(data)


class Run:
    """A run directory under the results root with an append-only manifest."""

    def __init__(self, cfg: dict, run_id: str):
        if not RUN_ID.match(run_id):
            raise ToolError(f"run id {run_id!r} must look like YYYYMMDD-HHMM-purpose")
        self.id = run_id
        self.dir = ROOT / cfg["results_root"] / run_id
        self.manifest = self.dir / "manifest.json"

    def path(self, name: str) -> Path:
        return self.dir / name

    def record(self, step: dict) -> None:
        doc = json.loads(self.manifest.read_text()) if self.manifest.exists() else {"run_id": self.id, "steps": []}
        doc["steps"].append(step)
        write_json(self.manifest, doc)


# ── kubectl: the single choke point ───────────────────────────────────────────

class Kube:
    """Runs kubectl with the configured context and namespace; records every call."""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.calls: list[dict] = []

    def _base(self) -> list[str]:
        return [KUBECTL, "--context", self.cfg["context"], "--namespace", self.cfg["namespace"]]

    def run(self, args: list[str], stdin: bytes | None = None, check: bool = True) -> subprocess.CompletedProcess:
        argv = self._base() + args
        proc = subprocess.run(argv, input=stdin, capture_output=True)
        self.calls.append({"argv": [Path(argv[0]).name] + argv[1:], "exit": proc.returncode,
                           "stdout_sha256": sha256_bytes(proc.stdout), "stdout_bytes": len(proc.stdout)})
        if proc.returncode != 0 and check:
            err = proc.stderr.decode(errors="replace").strip()
            if any(h in err.lower() for h in AUTH_HINTS):
                raise AuthRequired(login_message(self.cfg, err))
            raise ToolError(f"kubectl {' '.join(args[:2])} failed: {err[-800:]}")
        return proc

    def pod_python(self, script: str, args: dict, binary: bool = False):
        """Pipe scripts/sigma2_pod/_common.py + <script>.py to the pod's python."""
        source = (POD_DIR / "_common.py").read_text() + "\n" + (POD_DIR / f"{script}.py").read_text()
        target = ["exec", "-i", self.cfg["target"]]
        if self.cfg.get("container"):
            target += ["-c", self.cfg["container"]]
        proc = self.run(target + ["--", self.cfg["python"], "-", json.dumps(args, sort_keys=True)],
                        stdin=source.encode(), check=False)
        self.calls[-1]["pod_script"] = {"name": script, "sha256": sha256_bytes(source.encode())}
        if binary and proc.returncode == 0:
            return proc.stdout
        err = proc.stderr.decode(errors="replace").strip()
        if proc.returncode != 0 and any(h in err.lower() for h in AUTH_HINTS) and not proc.stdout:
            raise AuthRequired(login_message(self.cfg, err))
        try:
            out = json.loads(proc.stdout.decode())
        except ValueError:
            raise PodError(f"pod script {script} gave no JSON (exit {proc.returncode}): {err[-800:]}")
        if "error" in out:
            raise PodError(f"pod script {script}: {out['error']} {json.dumps({k: v for k, v in out.items() if k != 'error'})}")
        return out


def login_message(cfg: dict, detail: str) -> str:
    return (f"kubectl needs a fresh login ({detail.splitlines()[-1][:200] if detail else 'no detail'}).\n"
            "In your own terminal:\n"
            "  export PATH=$PATH:~/go/bin\n"
            f"  kubectl config use-context {cfg['context']}\n"
            "  then log in with the NIRD toolkit auth helper as usual, and rerun this command.")


def step(run: Run | None, name: str, args: argparse.Namespace, kube: Kube, outputs: dict, started: str,
         status: str = "ok") -> None:
    if run is None:
        return
    run.record({"step": name, "status": status, "started": started, "finished": now(),
                "tool": git_state(), "config_sha256": sha256_file(CONFIG),
                "argv": [a for a in sys.argv[1:]], "kubectl": kube.calls,
                "outputs": [{"path": str(Path(p).relative_to(run.dir)), "sha256": s} for p, s in sorted(outputs.items())]})


# ── completeness (pure, tested locally) ───────────────────────────────────────

Key = tuple  # (model, goal, pcorr, variant, station)


def parse_simulated(name: str):
    """(key, optimizer, rev_suffix, stage) or None. key = (model, goal, pcorr, variant, station);
    stage is "sim" or "cal"."""
    m = SIMULATED.match(name)
    if not m:
        return None
    variant = m["variant"] if m["variant"] is not None else m["variant2"]
    station = m["station"] if m["station"] is not None else m["station2"]
    return (m["model"], m["goal"], bool(m["pcorr"]), int(variant), station), m["optimizer"], bool(m["rev"]), m["stage"]


def direction(sim: dict, rev_suffix: bool, cal: list[dict]) -> str | None:
    """"reverse" or "forward" from the periods (or a "_rev" suffix); None when the key
    has no single calibration series to compare with."""
    if rev_suffix:
        return "reverse"
    if len(cal) != 1:
        return None
    return "reverse" if cal[0]["start"] > sim["start"] else "forward"


def expected_keys(expected: dict, observed_stations: list[str], present_stations: list[str]) -> list[Key]:
    stations = expected["stations"]
    if not (isinstance(stations, list) or stations in ("observed", "present")):
        raise ToolError("expected.json: stations must be a list of station ids, \"observed\" or \"present\" "
                        f"(the founder confirms which catchments the run covered); got {json.dumps(stations)[:200]}")
    if stations == "observed":
        stations = observed_stations
        if not stations:
            raise ToolError("expected.json says stations: observed, but the container has no observed series; "
                            "list the stations explicitly or use \"present\"")
    elif stations == "present":
        stations = present_stations
    return sorted((m, g, p, v, s) for m in expected["models"] for g in expected["goals"]
                  for p in expected["pcorr"] for v in expected["variants"] for s in stations)


def most_common_period(rows_by_key: dict, keys: set) -> tuple | None:
    periods = collections.Counter((r[0]["start"], r[0]["end"]) for k, r in rows_by_key.items()
                                  if k in keys and len(r) == 1)
    return sorted(periods.items(), key=lambda kv: (-kv[1], kv[0]))[0][0] if periods else None


def completeness(series: dict, expected: dict) -> dict:
    by_key: dict[Key, list[dict]] = collections.defaultdict(list)
    cal_by_key: dict[Key, list[dict]] = collections.defaultdict(list)
    unparsed = []
    reverse = bool(expected.get("reverse", False))
    other_direction = []
    parsed_rows = []
    for row in series["simulated"]:
        parsed = parse_simulated(row["name"])
        if parsed is None:
            unparsed.append(row["name"])
        elif parsed[3] == "cal":
            cal_by_key[parsed[0]].append(row)
        else:
            parsed_rows.append((row, parsed))
    directions = {}
    for row, parsed in parsed_rows:
        d = direction(row, parsed[2], cal_by_key.get(parsed[0], []))
        if d is not None and (d == "reverse") != reverse:
            other_direction.append(row["name"])
        else:
            by_key[parsed[0]].append(row)
            directions[row["name"]] = d or "unverified"
    observed = sorted({m["station"] for r in series["observed"] if (m := OBSERVED.match(r["name"]))})
    present = sorted({k[4] for k in by_key})
    wanted = expected_keys(expected, observed, present)
    wanted_set = set(wanted)

    if expected.get("simulation"):
        ref = (expected["simulation"]["start"], expected["simulation"]["end"])
        ref_source = "expected.json"
    else:
        ref = most_common_period(by_key, wanted_set)
        if ref is None:
            raise ToolError("no expected series present; nothing to compare against")
        ref_source = "most common period among present series"
    if expected.get("calibration"):
        cal_ref = (expected["calibration"]["start"], expected["calibration"]["end"])
        cal_source = "expected.json"
    else:
        cal_ref = most_common_period(cal_by_key, wanted_set)
        cal_source = "most common period among present calibration series"

    def covers(r, period):
        return period is not None and r["start"] <= period[0] and r["end"] >= period[1]

    def calibration(key):
        found = cal_by_key.get(key, [])
        if not found:
            return {"status": "missing"}
        if len(found) > 1:
            return {"status": "duplicate", "names": [r["name"] for r in found]}
        r = found[0]
        return {"status": "complete" if covers(r, cal_ref) else "partial",
                "name": r["name"], "start": r["start"], "end": r["end"]}

    rows = []
    for key in wanted:
        found = by_key.get(key, [])
        if not found:
            status, detail = "missing", None
        elif len(found) > 1:
            status, detail = "duplicate", [r["name"] for r in found]
        else:
            r = found[0]
            status = "complete" if covers(r, ref) else "partial"
            detail = {"name": r["name"], "start": r["start"], "end": r["end"], "direction": directions[r["name"]]}
        rows.append({"model": key[0], "goal": key[1], "pcorr": key[2], "variant": key[3],
                     "station": key[4], "status": status, "series": detail, "calibration": calibration(key)})
    unexpected = sorted(r["name"] for k, rs in by_key.items() if k not in wanted_set for r in rs)
    unexpected_count_other_direction = len(other_direction)

    summary = collections.OrderedDict()
    for row in rows:
        group = (row["model"], row["goal"], row["pcorr"], row["variant"])
        counts = summary.setdefault(group, collections.Counter())
        counts["expected"] += 1
        counts[row["status"]] += 1
    table = [{"model": g[0], "goal": g[1], "pcorr": g[2], "variant": g[3],
              **{s: c.get(s, 0) for s in ("expected", "complete", "partial", "duplicate", "missing")}}
             for g, c in summary.items()]
    totals = collections.Counter(r["status"] for r in rows)
    cal_totals = collections.Counter(r["calibration"]["status"] for r in rows)
    unverified = sum(1 for r in rows if isinstance(r["series"], dict) and r["series"]["direction"] == "unverified")
    return {"experiment": expected["experiment"], "container": series["container"],
            "reference_period": {"start": ref[0], "end": ref[1], "source": ref_source},
            "calibration_period": ({"start": cal_ref[0], "end": cal_ref[1], "source": cal_source}
                                   if cal_ref else None),
            "calibration_totals": {s: cal_totals.get(s, 0) for s in ("complete", "partial", "duplicate", "missing")},
            "direction_unverified": unverified,
            "stations": {"source": expected["stations"] if isinstance(expected["stations"], str) else "listed",
                         "count": len({k[4] for k in wanted})},
            "totals": {s: totals.get(s, 0) for s in ("complete", "partial", "duplicate", "missing")} | {"expected": len(rows)},
            "reverse": reverse,
            "other_direction": {"count": unexpected_count_other_direction,
                                "examples": sorted(other_direction)[:20]},
            "summary": table, "rows": rows, "unexpected": unexpected, "unparsed": sorted(unparsed)}


def calibration_line(report: dict) -> str:
    c, p = report["calibration_totals"], report["calibration_period"]
    period = f"{p['start']} to {p['end']} ({p['source']})" if p else "none present"
    line = (f"Calibration series, period {period}: complete {c['complete']}, partial {c['partial']}, "
            f"duplicate {c['duplicate']}, missing {c['missing']}.")
    if report["direction_unverified"]:
        line += (f" Direction unverified for {report['direction_unverified']} series "
                 "(no single calibration series to compare with).")
    return line


def completeness_markdown(report: dict) -> str:
    t = report["totals"]
    lines = [f"# Completeness: {report['experiment']} ({report['container']})", "",
             f"Reference period {report['reference_period']['start']} to {report['reference_period']['end']} "
             f"({report['reference_period']['source']}); {report['stations']['count']} stations "
             f"({report['stations']['source']}).", "",
             f"Expected {t['expected']}: complete {t['complete']}, partial {t['partial']}, "
             f"duplicate {t['duplicate']}, missing {t['missing']}.", "",
             f"{'Reverse' if report['reverse'] else 'Forward'} run. " + calibration_line(report), "",
             "| model | goal | pcorr | variant | expected | complete | partial | duplicate | missing |",
             "|---|---|---|---|---|---|---|---|---|"]
    lines += [f"| {r['model']} | {r['goal']} | {'on' if r['pcorr'] else 'off'} | v{r['variant']:02d} | {r['expected']} "
              f"| {r['complete']} | {r['partial']} | {r['duplicate']} | {r['missing']} |" for r in report["summary"]]
    for status in ("partial", "duplicate"):
        listed = [r for r in report["rows"] if r["status"] == status]
        if listed:
            lines += ["", f"## {status.capitalize()} series (for the founder's decision)", ""]
            lines += [f"- {r['model']} {r['goal']} pcorr={'on' if r['pcorr'] else 'off'} v{r['variant']:02d} "
                      f"{r['station']}: {json.dumps(r['series'])}" for r in listed]
    if report["unexpected"]:
        lines += ["", f"## Present but not expected ({len(report['unexpected'])})", ""] + \
                 [f"- {n}" for n in report["unexpected"]]
    if report["other_direction"]["count"]:
        lines += ["", f"## {'Forward' if report['reverse'] else 'Reverse'}-run series ignored "
                  f"({report['other_direction']['count']}; expected.json has reverse = {str(report['reverse']).lower()})", ""] + \
                 [f"- {n}" for n in report["other_direction"]["examples"]]
    if report["unparsed"]:
        lines += ["", f"## Names that do not follow the naming convention ({len(report['unparsed'])})", ""] + \
                 [f"- {n}" for n in report["unparsed"]]
    return "\n".join(lines) + "\n"


def extraction_plan(report: dict, run_id: str, snapshot: dict, tool_commit: str) -> list[dict]:
    t0 = int(dt.datetime.strptime(report["reference_period"]["start"], "%Y-%m-%dT%H:%M:%SZ")
             .replace(tzinfo=dt.timezone.utc).timestamp())
    t1 = int(dt.datetime.strptime(report["reference_period"]["end"], "%Y-%m-%dT%H:%M:%SZ")
             .replace(tzinfo=dt.timezone.utc).timestamp())
    groups: dict[tuple, list[dict]] = collections.defaultdict(list)
    for row in report["rows"]:
        if row["status"] == "complete":
            groups[(row["model"], row["pcorr"])].append(row)
    plan = []
    for (model, pcorr), rows in sorted(groups.items()):
        variant = "bc_pcorr" if pcorr else "bc"
        plan.append({
            "file": f"{report['experiment']}_{model}_{variant}.nc",
            "stations": sorted({r["station"] for r in rows}),
            "goals": sorted({r["goal"] for r in rows}),
            "variants": sorted({r["variant"] for r in rows}),
            "series": [{"name": r["series"]["name"], "station": r["station"], "goal": r["goal"],
                        "variant": r["variant"], "t0": t0, "t1": t1} for r in rows],
            "attrs": {"experiment_id": report["experiment"], "run_id": run_id, "model": model,
                      "pcorr": int(pcorr), "source_container": report["container"],
                      "shyft_version": str(snapshot.get("shyft_version")), "reverse": int(report["reverse"]),
                      "tool_commit": tool_commit, "period_start": report["reference_period"]["start"],
                      "period_end": report["reference_period"]["end"]}})
    return plan


def legacy_time(v) -> int | None:
    """Seconds since epoch from a parsed `time("...")` call or an ISO string."""
    text = v.get("arg") if isinstance(v, dict) and v.get("call") == "time" else v
    if not isinstance(text, str):
        return None
    try:
        return int(dt.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc).timestamp())
    except ValueError:
        return None


def iso(seconds: int) -> str:
    return dt.datetime.fromtimestamp(seconds, tz=dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def legacy_periods(settings: dict) -> dict:
    """Calibration and simulation periods from the legacy run settings T0_CAL/N_CAL,
    T0_SIM/N_SIM and DT (time step in seconds)."""
    step_s = settings.get("DT")
    out = {}
    for stage, t0, n in (("calibration", "T0_CAL", "N_CAL"), ("simulation", "T0_SIM", "N_SIM")):
        start, count = legacy_time(settings.get(t0)), settings.get(n)
        if start is not None and isinstance(count, int) and isinstance(step_s, (int, float)):
            out[stage] = {"start": iso(start), "end": iso(start + int(count * step_s))}
    return out


def legacy_model(v) -> str | None:
    """`RPMSTK_CONFIG` -> rpmstk; `ptfsm2k_config("default")` -> ptfsm2k."""
    if isinstance(v, dict) and "unparsed" in v and (m := re.fullmatch(r"([A-Z0-9]+)_CONFIG", v["unparsed"] or "")):
        return m[1].lower()
    if isinstance(v, dict) and (m := re.fullmatch(r"([a-z0-9]+)_config", v.get("call", ""))):
        return m[1]
    return None


def propose_expected(snapshot: dict, series: dict, experiment: str, container: str) -> dict:
    """Run settings come from the legacy run files; goals, pcorr and variants are not plain
    settings there, so they come from the series present. Stations stay for the founder."""
    settings = {}
    for name in snapshot.get("config_files", []):
        settings.update(snapshot["config"].get(name) or {})
    periods = legacy_periods(settings)
    keys = [p[0] for r in series["simulated"] if (p := parse_simulated(r["name"])) and p[3] == "sim"]
    model = legacy_model(settings.get("MODEL_CONFIG"))
    present_models = sorted({k[0] for k in keys})
    reverse = (periods["calibration"]["start"] > periods["simulation"]["start"]
               if len(periods) == 2 else None)
    catchments = settings.get("CATCHMENTS")
    return {
        "experiment": experiment, "container": container,
        "models": [model] if model else present_models,
        "goals": sorted({k[1] for k in keys}),
        "pcorr": sorted({k[2] for k in keys}),
        "variants": sorted({k[3] for k in keys}),
        "stations": {"confirm": "replace this with the list of station ids the run covered",
                     "CATCHMENTS": catchments.get("unparsed") if isinstance(catchments, dict) else catchments,
                     "present": len({k[4] for k in keys})},
        "reverse": reverse,
        "calibration": periods.get("calibration"),
        "simulation": periods.get("simulation"),
        "_from": {"models": f"MODEL_CONFIG; names show {present_models}" if model else "series names",
                  "goals, pcorr, variants": "series names",
                  "reverse, calibration, simulation": "T0_CAL, N_CAL, T0_SIM, N_SIM, DT" if len(periods) == 2
                  else "not found in the run files: set them by hand"},
        "_note": ("Proposed from the pod's CURRENT run files and the series present. Check every field, "
                  "set stations, remove the keys starting with _, then save as expected.json in this run folder."),
    }


# ── commands ──────────────────────────────────────────────────────────────────

def cmd_preflight(args, cfg) -> int:
    kube, started = Kube(cfg), now()
    report = {"context": cfg["context"], "namespace": cfg["namespace"], "target": cfg["target"]}
    current = subprocess.run([KUBECTL, "config", "current-context"], capture_output=True, text=True)
    report["current_context"] = current.stdout.strip() or None
    report["note"] = "every command pins --context/--namespace from config/sigma2.json"
    for verb, resource in (("get", "pods"), ("create", "pods/exec")):
        proc = kube.run(["auth", "can-i", verb, resource], check=False)
        answer = proc.stdout.decode().strip()
        err = proc.stderr.decode(errors="replace")
        if proc.returncode != 0 and any(h in err.lower() for h in AUTH_HINTS) and answer not in ("yes", "no"):
            raise AuthRequired(login_message(cfg, err))
        report[f"can_{verb}_{resource.replace('/', '_')}"] = answer == "yes"
    deploy = json.loads(kube.run(["get", cfg["target"], "-o", "json"]).stdout.decode())
    status = deploy.get("status", {})
    report["deployment"] = {"ready_replicas": status.get("readyReplicas", 0), "replicas": status.get("replicas", 0)}
    report["pod"] = kube.pod_python("probe", {"dtss": cfg["dtss"], "output_root": cfg["pod_output_root"],
                                             "stacks": args.stacks or []})
    problems = []
    if not report["can_get_pods"] or not report["can_create_pods_exec"]:
        problems.append("missing permission to read pods or exec into them")
    if not report["deployment"]["ready_replicas"]:
        problems.append("deployment has no ready replica")
    if not report["pod"]["dtss"]["reachable"]:
        problems.append(f"DTSS at {cfg['dtss']} not reachable from the pod")
    if not report["pod"]["modules"].get("xarray"):
        problems.append("xarray missing in the pod: extract will not work")
    report["problems"] = problems
    run = Run(cfg, args.run) if args.run else None
    outputs = {}
    if run:
        outputs[run.path("preflight.json")] = write_json(run.path("preflight.json"), report)
    step(run, "preflight", args, kube, outputs, started, "ok" if not problems else "problems")
    print(json.dumps(report, sort_keys=True, indent=1))
    return 0 if not problems else 1


def cmd_inventory(args, cfg) -> int:
    run, kube, started = Run(cfg, args.run), Kube(cfg), now()
    result = kube.pod_python("inventory", {"container": args.container, "directory": args.directory,
                                           "store_root": cfg["store_root"], "dtss": cfg["dtss"]})
    out = {run.path("inventory.json"): write_json(run.path("inventory.json"), result)}
    step(run, "inventory", args, kube, out, started, "ok" if result.get("registered") else "not-registered")
    print(f"{result['path']}: {result['files']} files, {result['bytes']} bytes, newest {result['newest_modified']}; "
          f"container {args.container!r} registered with DTSS: {result.get('registered')}")
    if result.get("registered") is False:
        print("The container is not registered with the running DTSS. Register it yourself, then rerun; "
              "this tool does not change the server.")
        return 1
    return 0


def cmd_snapshot(args, cfg) -> int:
    run, kube, started = Run(cfg, args.run), Kube(cfg), now()
    result = kube.pod_python("snapshot", {"code_dir": cfg["pod_code_dir"], "files": cfg["pod_code_files"],
                                          "config_files": cfg["pod_config_files"]})
    out = {run.path("snapshot.json"): write_json(run.path("snapshot.json"), result)}
    series = kube.pod_python("series", {"container": args.container, "dtss": cfg["dtss"],
                                        "simulated_pattern": SIMULATED_FIND, "observed_pattern": OBSERVED_FIND})
    proposal = propose_expected(result, series, args.experiment, args.container)
    out[run.path("expected.proposed.json")] = write_json(run.path("expected.proposed.json"), proposal)
    step(run, "snapshot", args, kube, out, started)
    missing = [n for n, v in result["files"].items() if v is None]
    print(f"snapshot: {len(result['files']) - len(missing)} files hashed, missing: {missing or 'none'}; "
          f"Shyft {result['shyft_version']}")
    direction_ = {True: "reverse", False: "forward", None: "unknown"}[proposal["reverse"]]
    print(f"run: {', '.join(proposal['models']) or '?'}, {direction_}; calibration {proposal['calibration']}; "
          f"simulation {proposal['simulation']}; {len(proposal['goals'])} goals, pcorr {proposal['pcorr']}, "
          f"variants {proposal['variants']}, {proposal['stations']['present']} stations present")
    print(f"proposed expected set: {run.path('expected.proposed.json').relative_to(ROOT)} "
          "(check it, then save as expected.json)")
    return 0


def name_shape(name: str) -> str:
    return re.sub(r"\d+", "9", name)


def cmd_names(args, cfg) -> int:
    run, kube, started = Run(cfg, args.run), Kube(cfg), now()
    if bool(args.container) == bool(args.directory):
        raise ToolError("give exactly one of --container (ask the DTSS) or --directory (read the store folder)")
    if args.directory:
        found = kube.pod_python("listnames", {"store_root": cfg["store_root"], "directory": args.directory,
                                              "pattern": args.pattern.replace("\\/", "/").lstrip("^").rstrip("$")})
    else:
        found = kube.pod_python("series", {"container": args.container, "dtss": cfg["dtss"],
                                           "simulated_pattern": args.pattern, "observed_pattern": OBSERVED_FIND})
    names = [r["name"] for r in found["simulated"]]
    shapes = collections.Counter(name_shape(n) for n in names)
    report = {"container": args.container, "directory": args.directory, "pattern": args.pattern, "count": len(names),
              "parsed": sum(1 for n in names if parse_simulated(n)),
              "simulation": sum(1 for n in names if (p := parse_simulated(n)) and p[3] == "sim"),
              "calibration": sum(1 for n in names if (p := parse_simulated(n)) and p[3] == "cal"),
              "rev_suffix": sum(1 for n in names if (p := parse_simulated(n)) and p[2]),
              "observed_count": len(found["observed"]),
              "shapes": [{"shape": k, "count": v} for k, v in sorted(shapes.items(), key=lambda kv: (-kv[1], kv[0]))],
              "sample": names[:args.limit]}
    out = {run.path("names.json"): write_json(run.path("names.json"), report)}
    step(run, "names", args, kube, out, started)
    where = f"DTSS container {args.container!r}" if args.container else f"store folder {args.directory!r}"
    print(f"{report['count']} names match {args.pattern!r} in {where}; parsed {report['parsed']} "
          f"(sim {report['simulation']}, cal {report['calibration']}; ending in _rev {report['rev_suffix']}); "
          f"observed series {report['observed_count']}")
    for s_ in report["shapes"][:15]:
        print(f"  {s_['count']:>7}  {s_['shape']}")
    return 0


def cmd_complete(args, cfg) -> int:
    run, kube, started = Run(cfg, args.run), Kube(cfg), now()
    expected_path = run.path("expected.json")
    if not expected_path.exists():
        raise ToolError(f"{expected_path.relative_to(ROOT)} is missing: review expected.proposed.json and save it "
                        "as expected.json first (the founder confirms the expected set)")
    expected = json.loads(expected_path.read_text())
    series = kube.pod_python("series", {"container": expected["container"], "dtss": cfg["dtss"],
                                        "simulated_pattern": SIMULATED_FIND, "observed_pattern": OBSERVED_FIND})
    report = completeness(series, expected)
    out = {run.path("series.json"): write_json(run.path("series.json"), series),
           run.path("completeness.json"): write_json(run.path("completeness.json"), report)}
    md = completeness_markdown(report).encode()
    run.path("completeness.md").write_bytes(md)
    out[run.path("completeness.md")] = sha256_bytes(md)
    step(run, "complete", args, kube, out, started)
    print(completeness_markdown(report).split("\n## ")[0])
    return 0


def cmd_extract(args, cfg) -> int:
    run, kube, started = Run(cfg, args.run), Kube(cfg), now()
    for need, command in (("snapshot.json", "snapshot"), ("completeness.json", "complete")):
        if not run.path(need).exists():
            raise ToolError(f"run `{command}` first")
    report = json.loads(run.path("completeness.json").read_text())
    snapshot = json.loads(run.path("snapshot.json").read_text())
    git = git_state()
    plan = extraction_plan(report, run.id, snapshot, git["commit"])
    out_dir = f"{cfg['pod_output_root'].rstrip('/')}/{run.id}"
    summary = {"output_dir": out_dir, "files": [{"file": g["file"], "series": len(g["series"])} for g in plan]}
    if not args.confirm:
        print(json.dumps({"dry_run": True, **summary}, indent=1))
        print("Nothing written. This creates a new folder in the pod; rerun with --confirm to extract.")
        return 0
    if git["dirty"] and not args.allow_dirty:
        raise ToolError("working tree has uncommitted changes; commit first, or pass --allow-dirty to record the diff")
    outputs = {}
    if git["dirty"]:
        diff = subprocess.run(["git", "diff", "HEAD"], cwd=ROOT, capture_output=True).stdout
        run.path("uncommitted.diff").parent.mkdir(parents=True, exist_ok=True)
        run.path("uncommitted.diff").write_bytes(diff)
        outputs[run.path("uncommitted.diff")] = sha256_bytes(diff)
    outputs[run.path("extract.plan.json")] = write_json(run.path("extract.plan.json"), {"output_dir": out_dir, "groups": plan})
    result = kube.pod_python("extract", {"output_dir": out_dir, "container": report["container"],
                                         "dtss": cfg["dtss"], "groups": plan})
    outputs[run.path("extract.json")] = write_json(run.path("extract.json"), result)
    step(run, "extract", args, kube, outputs, started)
    for f in result["files"]:
        print(f"{f['file']}: {f['series']} series, {f['bytes']} bytes, sha256 {f['sha256'][:12]}")
    return 0


def safe_members(tar: tarfile.TarFile):
    for member in tar:
        name = Path(member.name)
        if member.isdir():
            continue
        if not member.isfile() or name.is_absolute() or ".." in name.parts:
            raise VerifyError(f"refusing unsafe archive member {member.name!r}")
        yield member


def cmd_fetch(args, cfg) -> int:
    run, kube, started = Run(cfg, args.run), Kube(cfg), now()
    if not run.path("extract.json").exists():
        raise ToolError("run `extract --confirm` first")
    extract = json.loads(run.path("extract.json").read_text())
    dest = run.path("data")
    if dest.exists() and any(dest.iterdir()):
        raise ToolError(f"{dest.relative_to(ROOT)} already has files; fetched data is immutable")
    blob = kube.pod_python("pack", {"output_dir": extract["output_dir"]}, binary=True)
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r|") as tar:
        for member in safe_members(tar):
            target = dest / member.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(tar.extractfile(member).read())
    pod_sums = json.loads((dest / "checksums.json").read_text())["files"]
    checks = []
    for entry in pod_sums:
        local = dest / entry["file"]
        got = sha256_file(local) if local.exists() else None
        checks.append({"file": entry["file"], "pod_sha256": entry["sha256"], "local_sha256": got,
                       "content_sha256": entry["content_sha256"], "ok": got == entry["sha256"]})
    listed = {e["file"] for e in pod_sums} | {"checksums.json"}
    extra = sorted(str(p.relative_to(dest)) for p in dest.rglob("*") if p.is_file() and str(p.relative_to(dest)) not in listed)
    verify = {"files": checks, "unlisted_files": extra, "ok": all(c["ok"] for c in checks) and not extra,
              "archive_sha256": sha256_bytes(blob)}
    outputs = {run.path("verify.json"): write_json(run.path("verify.json"), verify)}
    outputs.update({dest / c["file"]: c["local_sha256"] for c in checks if c["local_sha256"]})
    step(run, "fetch", args, kube, outputs, started, "ok" if verify["ok"] else "verify-failed")
    for c in checks:
        print(f"{'ok  ' if c['ok'] else 'FAIL'} {c['file']} {c['local_sha256']}")
    if not verify["ok"]:
        raise VerifyError("checksum verification failed; see verify.json")
    print(f"{len(checks)} files home in {dest.relative_to(ROOT)}, all checksums match")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="sigma2.py", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("preflight")
    s.add_argument("--run")
    s.add_argument("--stacks", nargs="*", help="Shyft stacks that must import, e.g. r_pm_fsm2_k")
    s.set_defaults(fn=cmd_preflight)
    s = sub.add_parser("inventory")
    s.add_argument("--run", required=True)
    s.add_argument("--container", required=True, help="DTSS container name")
    s.add_argument("--directory", help="its directory under store_root, if it differs from the name")
    s.set_defaults(fn=cmd_inventory)
    s = sub.add_parser("snapshot")
    s.add_argument("--run", required=True)
    s.add_argument("--experiment", required=True, help="catalogue id, e.g. legacy-rpmstk-reverse")
    s.add_argument("--container", required=True)
    s.set_defaults(fn=cmd_snapshot)
    s = sub.add_parser("names", help="read-only: what series names exist (sample and name shapes)")
    s.add_argument("--run", required=True)
    s.add_argument("--container", help="ask the DTSS (container must be registered)")
    s.add_argument("--directory", help="read file names from this store folder instead (no DTSS needed)")
    s.add_argument("--pattern", default=SIMULATED_FIND)
    s.add_argument("--limit", type=int, default=50)
    s.set_defaults(fn=cmd_names)
    s = sub.add_parser("complete")
    s.add_argument("--run", required=True)
    s.set_defaults(fn=cmd_complete)
    s = sub.add_parser("extract")
    s.add_argument("--run", required=True)
    s.add_argument("--confirm", action="store_true", help="actually write the new folder in the pod")
    s.add_argument("--allow-dirty", action="store_true")
    s.set_defaults(fn=cmd_extract)
    s = sub.add_parser("fetch")
    s.add_argument("--run", required=True)
    s.set_defaults(fn=cmd_fetch)
    args = p.parse_args(argv)
    try:
        return args.fn(args, load_config())
    except ToolError as e:
        print(f"sigma2: {e}", file=sys.stderr)
        return e.code


if __name__ == "__main__":
    sys.exit(main())
