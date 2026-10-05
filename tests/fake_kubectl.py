#!/usr/bin/env python3
"""Stand-in for kubectl in tests: runs the real pod scripts locally against a stub
Shyft (tests/fake_pod), and can simulate an expired login. State comes from the
FAKE_KUBE environment variable (a JSON file)."""
import json
import os
import subprocess
import sys
from pathlib import Path

state = json.loads(Path(os.environ["FAKE_KUBE"]).read_text())
args = sys.argv[1:]
log = Path(os.environ["FAKE_KUBE"]).with_suffix(".calls")
with open(log, "a") as fh:
    fh.write(json.dumps(args) + "\n")

if args[:2] == ["config", "current-context"]:
    print(state.get("current_context", "nird-lmd"))
    sys.exit(0)
assert args[0] == "--context" and args[2] == "--namespace", args
if args[1] != state.get("context", "nird-lmd"):
    print(f'error: context "{args[1]}" does not exist', file=sys.stderr)
    sys.exit(1)
rest = args[4:]
if state.get("expired"):
    print("error: You must be logged in to the server (Unauthorized)", file=sys.stderr)
    sys.exit(1)
if rest[:2] == ["auth", "can-i"]:
    print("yes")
elif rest[0] == "get":
    print(json.dumps({"status": {"readyReplicas": 1, "replicas": 1}}))
elif rest[0] == "exec":
    sep = rest.index("--")
    assert rest[sep + 2] == "-", "pod scripts must arrive on stdin"
    env = dict(os.environ, PYTHONPATH=str(Path(__file__).parent / "fake_pod"))
    proc = subprocess.run([os.environ.get("FAKE_POD_PYTHON", sys.executable), "-"] + rest[sep + 3:], input=sys.stdin.buffer.read(),
                          env=env, capture_output=True)
    sys.stdout.buffer.write(proc.stdout)
    sys.stderr.buffer.write(proc.stderr)
    sys.exit(proc.returncode)
else:
    print(f"fake kubectl: unsupported {rest}", file=sys.stderr)
    sys.exit(1)
