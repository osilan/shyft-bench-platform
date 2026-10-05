#!/usr/bin/env python3
"""PreToolUse hook: Sigma2 is reached only through scripts/sigma2.py.

Denies, for every agent:
  - terminal commands that mention kubectl, the NIRD auth helper, ~/.kube or
    KUBECONFIG, or try to swap the tool's kubectl (BENCH_SIGMA2_KUBECTL);
  - reading ~/.kube files;
  - writing code that calls kubectl anywhere except the tool's own files.
Documentation (.md, .json, .txt) may mention kubectl.

A seatbelt, not a sandbox: it stops improvised commands, and the Sigma2 Guru
has no reason to need one. Reads the hook event on stdin, answers on stdout.
"""
import json
import re
import sys

ALWAYS = re.compile(r"nird-toolkit-auth-helper|\.kube/|KUBECONFIG|BENCH_SIGMA2_KUBECTL")
KUBECTL = re.compile(r"\bkubectl\b")
PATHLIKE = re.compile(r"^[\w./~-]+\.(py|sh|bash|zsh|ts|js|mjs|ipynb|lean|md|json|txt|yml|yaml)$")
DOCS = (".md", ".json", ".txt")
TOOL_FILES = ("scripts/sigma2.py", "scripts/sigma2_pod/", "scripts/sigma2_guard.py",
              "tests/test_sigma2.py", "tests/fake_kubectl.py", "tests/fake_pod/")


def strings(obj):
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from strings(v)


def decide(event: dict):
    texts = list(strings(event.get("tool_input", {})))
    paths = [t.strip() for t in texts if PATHLIKE.match(t.strip())]
    touched_tool_files = paths and all(any(f in p for f in TOOL_FILES) for p in paths)
    only_docs = paths and all(p.endswith(DOCS) for p in paths)
    for text in texts:
        if ALWAYS.search(text) and not only_docs:
            return "credentials, kubeconfig and the auth helper are the founder's; never touch them"
        if KUBECTL.search(text) and text.strip() not in paths and not (touched_tool_files or only_docs):
            return "raw kubectl is blocked; use python3 scripts/sigma2.py <command> (see --help)"
    return None


def main() -> int:
    raw = sys.stdin.read()
    event = json.loads(raw) if raw.strip() else {}
    reason = decide(event)
    if reason is None:
        print(json.dumps({"continue": True}))
    else:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "permissionDecision": "deny",
            "permissionDecisionReason": reason,
            "additionalContext": "Every Sigma2 action goes through python3 scripts/sigma2.py "
                                 "(preflight, inventory, snapshot, complete, extract, fetch)."}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
