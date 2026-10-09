# Lean audit gate

One script, `scripts/gate.py`, runs in three places: by hand, from Copilot agent
hooks, and in GitHub Actions (`.github/workflows/lean-gate.yml`).

| Check | Fails when |
|---|---|
| `lake build` | the package does not build; warnings exceed `baseline.json` |
| forbidden tokens | `sorry`/`admit` outside `obligations`, `axiom`, `native_decide`, `unsafe`, `implemented_by` (unless allow-listed in `gate.json`) |
| axioms | a theorem depends on anything beyond `propext`, `Classical.choice`, `Quot.sound` (`sorryAx` is counted and ratcheted) |
| fingerprint | theorem statements, requirement values, or `#guard` lines differ from the committed `fingerprint.tsv` |
| tests | `tests/` exists and `python -m unittest discover -s tests` fails (or `test_cmd` in `gate.json`) |

```bash
python3 scripts/gate.py check     # full gate
python3 scripts/gate.py metrics   # sizes and evidence counts
python3 scripts/gate.py update    # record statement changes in fingerprint.tsv (commit it)
python3 scripts/gate.py ratchet   # tighten baseline.json to current values
python3 scripts/gate.py init      # first time a Lean library exists
```

Ownership: **Independent Auditor** defines the checks and baselines (they only tighten),
**DevOps** keeps the workflow running, **Backend Developer** keeps it green. The
workspace hook (`.github/hooks/lean-gate.json`) asks before any agent edits a
gate-owned file, or a file listed under `frozen` in `gate.json` (add the
requirements file there once the spec is frozen).

Hooks run only in local VS Code, not in GitHub's cloud coding agent; CI is the
gate of record. The cloud agent's environment is prepared by
`.github/workflows/copilot-setup-steps.yml`, so it can run the gate itself, and the
`main` ruleset (`.github/rulesets/main-gate.json`) requires the `gate` job to pass.

In CI, pull requests into a review branch (any base except `main`) run
`gate.py check --no-committed --mode append-only --against <base fingerprint>`: new checks and
theorems pass, changed or removed statements fail. Pushes to `main` and pull requests into `main`
run the strict `gate.py check`, so the committed fingerprint must be current there.
