#!/usr/bin/env python3
"""Lean audit gate: one script for local runs, Copilot hooks, and CI.

Owned by the Lean Audit agent. Lean Prover keeps it green; DevOps runs it
unchanged in CI. Standard library only.

Commands
  check      run the full gate (exit 1 on failure)
  metrics    print size and evidence counts
  update     rewrite audit/fingerprint.tsv from the current build
  ratchet    tighten audit/baseline.json to current values (never loosens)
  init       create audit/baseline.json and audit/fingerprint.tsv
  hook EVENT Copilot hook adapter (reads hook JSON on stdin)

Fingerprint = every theorem statement, every lean-spec requirement value, and
every #guard line in the package. Statement changes must be visible in the
committed audit/fingerprint.tsv, so they show up in review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AUDIT = ROOT / "audit"
CONFIG = AUDIT / "gate.json"
BASELINE = AUDIT / "baseline.json"
FINGERPRINT = AUDIT / "fingerprint.tsv"
STATE = ROOT / ".lake" / "gate"

TRUSTED_AXIOMS = {"propext", "Classical.choice", "Quot.sound"}
FORBIDDEN = {
    "sorry": r"\bsorry\b",
    "admit": r"\badmit\b",
    "axiom": r"^\s*(?:private\s+|protected\s+)?axiom\s",
    "native_decide": r"\bnative_decide\b",
    "unsafe": r"\bunsafe\b",
    "implemented_by": r"\bimplemented_by\b",
}
DEFAULT_CONFIG = {
    "lean_roots": None,          # module roots; None = read from lakefile.lean
    "exclude_dirs": [".lake", "open-lean-spec"],
    "obligations": [],           # files where `sorry` is allowed
    "allow": {},                 # {"native_decide": ["path/File.lean"]}
    "test_cmd": None,            # None = unittest discover on tests/ if present
    "frozen": [],                # files edits must ask for (e.g. a frozen spec)
    "protected": ["scripts/gate.py", "audit/gate.json", "audit/baseline.json",
                  "audit/fingerprint.tsv", ".github/workflows", ".github/hooks"],
    "stop_retries": 3,
}


# ── configuration ─────────────────────────────────────────────────────────────

def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG.exists():
        cfg.update(json.loads(CONFIG.read_text()))
    if cfg["lean_roots"] is None:
        cfg["lean_roots"] = lakefile_roots()
    return cfg


def lakefile_roots() -> list[str]:
    lakefile = ROOT / "lakefile.lean"
    if not lakefile.exists():
        return []
    text = lakefile.read_text()
    roots = re.findall(r"roots\s*:=\s*#\[([^\]]*)\]", text)
    if roots:
        return [r.strip().lstrip("`") for r in roots[0].split(",") if r.strip()]
    return re.findall(r"^\s*lean_lib\s+«?([\w.]+)»?", text, re.M)


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def lean_sources(cfg: dict) -> list[Path]:
    excluded = {ROOT / d for d in cfg["exclude_dirs"]}
    tops = {r.split(".")[0] for r in cfg["lean_roots"]}
    files = []
    for top in sorted(tops):
        base = ROOT / top
        candidates = list(base.rglob("*.lean")) if base.is_dir() else []
        if (ROOT / f"{top}.lean").exists():
            candidates.append(ROOT / f"{top}.lean")
        files += [f for f in candidates
                  if not any(ex in f.parents for ex in excluded)]
    return sorted(set(files))


def strip_comments_and_strings(src: str) -> str:
    src = re.sub(r"/-.*?-/", lambda m: "\n" * m.group().count("\n"), src, flags=re.S)
    src = re.sub(r'"(?:\\.|[^"\\])*"', '""', src)
    return re.sub(r"--[^\n]*", "", src)


# ── checks ────────────────────────────────────────────────────────────────────

@dataclass
class Result:
    failures: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def fail(self, msg: str) -> None:
        self.failures.append(msg)


def run(cmd: list[str] | str, timeout: int = 1800) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                          timeout=timeout, shell=isinstance(cmd, str))


def lake_build(res: Result, cfg: dict) -> bool:
    proc = run(["lake", "build"])
    out = proc.stdout + proc.stderr
    if proc.returncode != 0:
        errors = [l for l in out.splitlines() if "error" in l][:20]
        res.fail("lake build failed:\n" + "\n".join(errors or out.splitlines()[-20:]))
        return False
    own = {rel(f) for f in lean_sources(cfg)}
    warnings = sorted({l.strip() for l in out.splitlines()
                       if "warning:" in l and any(p in l for p in own)})
    res.metrics["warnings"] = len(warnings)
    if warnings:
        res.notes.append("warnings:\n" + "\n".join(warnings[:20]))
    return True


def forbidden_tokens(res: Result, cfg: dict) -> None:
    obligations = set(cfg["obligations"])
    sorry_count = 0
    for f in lean_sources(cfg):
        path = rel(f)
        clean = strip_comments_and_strings(f.read_text())
        for name, pattern in FORBIDDEN.items():
            for m in re.finditer(pattern, clean, re.M):
                line = clean.count("\n", 0, m.start()) + 1
                if name in ("sorry", "admit"):
                    sorry_count += 1
                    if path in obligations:
                        continue
                if path in cfg["allow"].get(name, []):
                    continue
                res.fail(f"{path}:{line}: `{name}` is not allowed here")
    res.metrics["sorry"] = sorry_count


AUDIT_LEAN = """\
{imports}
open Lean Elab Command Meta

set_option pp.proofs false
set_option pp.fieldNotation false

#eval show CommandElabM Unit from do
  let env ← getEnv
  let tops : List String := {tops}
  let mut rows : Array String := #[]
  for (n, ci) in env.constants.map₁.toList do
    let userName := (privateToUserName? n).getD n
    if userName.isInternalDetail || userName.isInternal then continue
    let some idx := env.getModuleIdxFor? n | continue
    let modName := (env.header.moduleNames[idx.toNat]!).toString
    unless tops.any (fun t => modName == t || modName.startsWith (t ++ ".")) do continue
    match ci with
    | .thmInfo t =>
      let ty ← liftTermElabM <| ppExpr t.type
      let axs ← liftCoreM <| collectAxioms n
      rows := rows.push s!"theorem\\t{{userName}}\\t{{(ty.pretty 1000000).replace "\\n" " "}}"
      rows := rows.push s!"axioms\\t{{userName}}\\t{{",".intercalate (axs.toList.map toString)}}"
    | .defnInfo d =>
      if d.type.isConstOf `LeanSpec.Requirement then
        let v ← liftTermElabM <| ppExpr d.value
        rows := rows.push s!"requirement\\t{{userName}}\\t{{(v.pretty 1000000).replace "\\n" " "}}"
    | _ => pure ()
  IO.FS.writeFile {out} ("\\n".intercalate (rows.qsort (· < ·)).toList ++ "\\n")
"""


def lean_facts(cfg: dict) -> list[tuple[str, str, str]] | None:
    """Theorem statements, axioms, and requirement values from the built package."""
    if not cfg["lean_roots"]:
        return None
    STATE.mkdir(parents=True, exist_ok=True)
    out = STATE / "facts.tsv"
    script = STATE / "GateAudit.lean"
    tops = sorted({r.split(".")[0] for r in cfg["lean_roots"]})
    script.write_text(AUDIT_LEAN.format(
        imports="\n".join(f"import {r}" for r in cfg["lean_roots"]),
        tops="[" + ", ".join(json.dumps(t) for t in tops) + "]",
        out=json.dumps(str(out))))
    if out.exists():
        out.unlink()
    proc = run(["lake", "env", "lean", str(script)])
    if proc.returncode != 0 or not out.exists():
        raise RuntimeError("Lean fact extraction failed:\n"
                           + (proc.stdout + proc.stderr)[-2000:])
    rows = []
    for line in out.read_text().splitlines():
        kind, name, text = line.split("\t", 2)
        # generated proof names (`_proof_3✝`) are not part of the statement
        text = re.sub(r",?\s*property := [\w.«»]*_proof_\d+✝", "", text)
        rows.append((kind, name, text))
    return rows


def guard_rows(cfg: dict) -> list[tuple[str, str, str]]:
    rows = []
    for f in lean_sources(cfg):
        clean = strip_comments_and_strings(f.read_text())
        raw = f.read_text().splitlines()
        for i, line in enumerate(clean.splitlines()):
            if re.match(r"\s*#guard\b", line):
                rows.append(("guard", f"{rel(f)}#{i + 1}", " ".join(raw[i].split())))
    return rows


def fingerprint(cfg: dict) -> tuple[list[tuple[str, str, str]], dict[str, list[str]]]:
    facts = lean_facts(cfg) or []
    axioms = {n: [a for a in t.split(",") if a] for k, n, t in facts if k == "axioms"}
    rows = [r for r in facts if r[0] != "axioms"]
    # guards are keyed by content, not line number, so moving code is not a change
    guards = sorted({("guard", hashlib.sha256(t.encode()).hexdigest()[:12], t)
                     for _, _, t in guard_rows(cfg)})
    return sorted(rows) + guards, axioms


def write_fingerprint(rows, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{k}\t{n}\t{t}\n" for k, n, t in rows))


def read_fingerprint(path: Path) -> dict[tuple[str, str], str]:
    rows = {}
    for line in path.read_text().splitlines():
        if line.strip():
            k, n, t = line.split("\t", 2)
            rows[(k, n)] = t
    return rows


def compare(current: dict, reference: dict, mode: str) -> list[str]:
    """mode: 'frozen' = identical; 'append-only' = additions allowed."""
    problems = []
    for key, text in reference.items():
        if key not in current:
            problems.append(f"removed {key[0]} {key[1]}")
        elif current[key] != text:
            problems.append(f"changed {key[0]} {key[1]}")
    if mode == "frozen":
        problems += [f"added {k[0]} {k[1]}" for k in current if k not in reference]
    return problems


def axiom_check(res: Result, axioms: dict[str, list[str]], cfg: dict) -> None:
    dependent = sorted(n for n, axs in axioms.items() if "sorryAx" in axs)
    res.metrics["sorry_dependent_theorems"] = len(dependent)
    for n, axs in sorted(axioms.items()):
        extra = set(axs) - TRUSTED_AXIOMS - {"sorryAx"}
        if extra:
            res.fail(f"theorem {n} depends on untrusted axioms: {', '.join(sorted(extra))}")
    if dependent:
        res.notes.append("theorems resting on sorry: " + ", ".join(dependent))


def python_tests(res: Result, cfg: dict) -> None:
    cmd = cfg["test_cmd"]
    if cmd is None:
        if not (ROOT / "tests").is_dir():
            res.notes.append("no tests/ directory; implementation tests skipped")
            return
        cmd = f"{sys.executable} -m unittest discover -s tests"
    proc = run(cmd)
    res.metrics["tests_passed"] = proc.returncode == 0
    if proc.returncode != 0:
        res.fail("implementation tests failed:\n" + (proc.stdout + proc.stderr)[-2000:])


def metrics(res: Result, cfg: dict, rows) -> None:
    lines = 0
    for f in lean_sources(cfg):
        lines += sum(1 for l in strip_comments_and_strings(f.read_text()).splitlines()
                     if l.strip())
    src = "\n".join(f.read_text() for f in lean_sources(cfg))
    res.metrics.update({
        "lean_files": len(lean_sources(cfg)),
        "lean_lines": lines,
        "theorems": sum(1 for r in rows if r[0] == "theorem"),
        "requirements": sum(1 for r in rows if r[0] == "requirement"),
        "guards": sum(1 for r in rows if r[0] == "guard"),
        "scenarios_executable": len(re.findall(r"\bcheck\s+executable\b", src)),
        "scenarios_deferred": len(re.findall(r"\bcheck\s+deferred\b", src)),
    })


def ratchet_check(res: Result) -> None:
    if not BASELINE.exists():
        res.notes.append("no audit/baseline.json; run `gate.py init`")
        return
    base = json.loads(BASELINE.read_text())
    for key, limit in base.items():
        value = res.metrics.get(key)
        if value is not None and value > limit:
            res.fail(f"{key} = {value} exceeds baseline {limit} (baselines may only tighten)")


# ── commands ──────────────────────────────────────────────────────────────────

def gate(cfg: dict, reference: Path | None, mode: str, committed: bool) -> Result:
    res = Result()
    if not (ROOT / "lakefile.lean").exists() and not (ROOT / "lakefile.toml").exists():
        res.notes.append("no Lean package yet; Lean checks skipped")
        python_tests(res, cfg)
        return res
    if not lake_build(res, cfg):
        return res
    forbidden_tokens(res, cfg)
    try:
        rows, axioms = fingerprint(cfg)
    except RuntimeError as e:
        res.fail(str(e))
        return res
    axiom_check(res, axioms, cfg)
    metrics(res, cfg, rows)
    current = {(k, n): t for k, n, t in rows}
    if committed:
        if not FINGERPRINT.exists():
            res.fail("audit/fingerprint.tsv missing; run `gate.py update` and commit it")
        else:
            stale = compare(current, read_fingerprint(FINGERPRINT), "frozen")
            if stale:
                res.fail("audit/fingerprint.tsv is out of date (statements changed); "
                         "review, run `gate.py update`, commit:\n  " + "\n  ".join(stale[:30]))
    if reference is not None and reference.exists():
        moved = compare(current, read_fingerprint(reference), mode)
        if moved:
            res.fail(f"statements moved ({mode} vs session start):\n  "
                     + "\n  ".join(moved[:30]))
    python_tests(res, cfg)
    ratchet_check(res)
    return res


def report(res: Result, stream=sys.stdout) -> None:
    status = "FAIL" if res.failures else "PASS"
    print(f"lean gate: {status}", file=stream)
    for f in res.failures:
        print("  x " + f.replace("\n", "\n    "), file=stream)
    for n in res.notes:
        print("  - " + n.replace("\n", "\n    "), file=stream)
    print("  metrics: " + json.dumps(res.metrics, sort_keys=True), file=stream)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as fh:
            fh.write(f"## Lean gate: {status}\n\n| metric | value |\n|---|---|\n")
            fh.writelines(f"| {k} | {v} |\n" for k, v in sorted(res.metrics.items()))
            fh.writelines(f"\n- ❌ {f.splitlines()[0]}" for f in res.failures)
            fh.write("\n")


def cmd_check(args) -> int:
    cfg = load_config()
    ref = Path(args.against) if args.against else None
    res = gate(cfg, ref, args.mode, committed=not args.no_committed)
    report(res)
    return 1 if res.failures else 0


def cmd_metrics(_args) -> int:
    cfg = load_config()
    res = Result()
    if lake_build(res, cfg):
        forbidden_tokens(res, cfg)
        rows, axioms = fingerprint(cfg)
        axiom_check(res, axioms, cfg)
        metrics(res, cfg, rows)
    print(json.dumps(res.metrics, indent=2, sort_keys=True))
    return 0


def cmd_update(_args) -> int:
    cfg = load_config()
    res = Result()
    if not lake_build(res, cfg):
        report(res)
        return 1
    rows, _ = fingerprint(cfg)
    old = read_fingerprint(FINGERPRINT) if FINGERPRINT.exists() else {}
    write_fingerprint(rows, FINGERPRINT)
    diff = compare({(k, n): t for k, n, t in rows}, old, "frozen")
    print(f"wrote {rel(FINGERPRINT)} ({len(rows)} entries)")
    print("\n".join("  " + d for d in diff) or "  no statement changes")
    return 0


RATCHETED = ("warnings", "sorry", "sorry_dependent_theorems")


def cmd_ratchet(args) -> int:
    cfg = load_config()
    res = Result()
    if not lake_build(res, cfg):
        report(res)
        return 1
    forbidden_tokens(res, cfg)
    _, axioms = fingerprint(cfg)
    axiom_check(res, axioms, cfg)
    base = json.loads(BASELINE.read_text()) if BASELINE.exists() and not args.init else {}
    new = {k: min(res.metrics[k], base.get(k, res.metrics[k])) for k in RATCHETED}
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(json.dumps(new, indent=2, sort_keys=True) + "\n")
    print(f"{rel(BASELINE)}: {json.dumps(new, sort_keys=True)}")
    return 0


def cmd_init(args) -> int:
    if not CONFIG.exists():
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        cfg = {k: v for k, v in DEFAULT_CONFIG.items()}
        CONFIG.write_text(json.dumps(cfg, indent=2) + "\n")
        print(f"wrote {rel(CONFIG)}")
    if not (ROOT / "lakefile.lean").exists():
        print("no Lean package yet; baseline and fingerprint will be created later")
        return 0
    args.init = not BASELINE.exists()
    return cmd_ratchet(args) or cmd_update(args)


# ── Copilot hook adapter ──────────────────────────────────────────────────────

WRITE_TOOL = re.compile(r"edit|create|write|replace|insert|delete|rename|patch|move", re.I)
TERMINAL_TOOL = re.compile(r"terminal|command|shell|execute|run", re.I)
WRITE_SHELL = re.compile(r"(>|\bsed\s+-i|\brm\s|\bmv\s|\bcp\s|\btee\b|\bgit\s+(checkout|restore)\b"
                         r"|gate\.py\s+(update|ratchet|init))")


def strings_in(obj) -> list[str]:
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in strings_in(v)]
    if isinstance(obj, list):
        return [s for v in obj for s in strings_in(v)]
    return []


def emit(obj: dict) -> int:
    print(json.dumps(obj))
    return 0


def session_snapshot(session: str) -> Path:
    return STATE / f"session-{re.sub(r'[^A-Za-z0-9_-]', '_', session or 'none')}.tsv"


def hook_prompt(event: dict) -> int:
    """UserPromptSubmit: snapshot statements once per session."""
    snap = session_snapshot(event.get("session_id", ""))
    if not snap.exists():
        try:
            cfg = load_config()
            if lakefile_roots() or cfg["lean_roots"]:
                res = Result()
                if lake_build(res, cfg):
                    rows, _ = fingerprint(cfg)
                    write_fingerprint(rows, snap)
        except Exception as e:  # never block a prompt because the snapshot failed
            print(f"gate snapshot skipped: {e}", file=sys.stderr)
    return emit({"continue": True})


def hook_guard(event: dict) -> int:
    """PreToolUse: ask before edits to frozen or gate-owned files."""
    cfg = load_config()
    tool = event.get("tool_name", "")
    texts = strings_in(event.get("tool_input", {}))
    watched = [(p, "frozen spec") for p in cfg["frozen"]] + \
              [(p, "gate-owned (Lean Audit / DevOps)") for p in cfg["protected"]]
    is_write = bool(WRITE_TOOL.search(tool))
    is_shell = bool(TERMINAL_TOOL.search(tool))
    for path, why in watched:
        hit = any(path in t for t in texts)
        if not hit:
            continue
        if is_write or (is_shell and any(WRITE_SHELL.search(t) for t in texts)):
            return emit({"hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": f"{path} is {why}. Approve only if you intend this change."}})
    return emit({"continue": True})


def hook_post_edit(event: dict) -> int:
    """PostToolUse: rebuild after a .lean edit and feed errors back."""
    if not any(t.endswith(".lean") for t in strings_in(event.get("tool_input", {}))):
        return emit({"continue": True})
    proc = run(["lake", "build"], timeout=300)
    if proc.returncode == 0:
        return emit({"continue": True})
    out = proc.stdout + proc.stderr
    errors = "\n".join([l for l in out.splitlines() if "error" in l][:15]) or out[-1500:]
    return emit({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": f"lake build fails after this edit:\n{errors}"}})


def hook_stop(event: dict, role: str) -> int:
    """Stop: refuse to finish while the gate fails (bounded retries)."""
    cfg = load_config()
    STATE.mkdir(parents=True, exist_ok=True)
    session = event.get("session_id", "")
    counter = STATE / f"stops-{re.sub(r'[^A-Za-z0-9_-]', '_', session or 'none')}"
    snap = session_snapshot(session)
    mode = "frozen" if role == "audit" else "append-only"
    res = gate(cfg, snap if snap.exists() else None, mode, committed=True)
    if not res.failures:
        counter.unlink(missing_ok=True)
        return emit({"continue": True})
    tries = int(counter.read_text()) if counter.exists() else 0
    if tries >= cfg["stop_retries"]:
        counter.unlink(missing_ok=True)
        return emit({"continue": True, "systemMessage":
                     "Lean gate still failing after retries; stopping so the user can decide."})
    counter.write_text(str(tries + 1))
    reason = "The Lean gate fails. Fix these before finishing (do not edit the gate):\n- " + \
             "\n- ".join(f.splitlines()[0] if len(f) > 400 else f for f in res.failures)
    if role == "audit":
        reason += "\nAs auditor you must leave every statement exactly as it was."
    return emit({"hookSpecificOutput": {"hookEventName": "Stop",
                                        "decision": "block", "reason": reason}})


def cmd_hook(args) -> int:
    raw = sys.stdin.read()
    event = json.loads(raw) if raw.strip() else {}
    handlers = {
        "prompt": hook_prompt,
        "guard": hook_guard,
        "post-edit": hook_post_edit,
        "stop": lambda e: hook_stop(e, args.role),
    }
    return handlers[args.event](event)


def main() -> int:
    p = argparse.ArgumentParser(description=textwrap.dedent(__doc__),
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("--against", help="reference fingerprint file")
    c.add_argument("--mode", choices=["frozen", "append-only"], default="append-only")
    c.add_argument("--no-committed", action="store_true",
                   help="do not require audit/fingerprint.tsv to be current")
    c.set_defaults(fn=cmd_check)
    sub.add_parser("metrics").set_defaults(fn=cmd_metrics)
    sub.add_parser("update").set_defaults(fn=cmd_update)
    r = sub.add_parser("ratchet")
    r.set_defaults(fn=cmd_ratchet, init=False)
    sub.add_parser("init").set_defaults(fn=cmd_init)
    h = sub.add_parser("hook")
    h.add_argument("event", choices=["prompt", "guard", "post-edit", "stop"])
    h.add_argument("--role", choices=["prover", "lead", "audit"], default="prover")
    h.set_defaults(fn=cmd_hook)
    args = p.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
