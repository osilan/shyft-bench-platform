# Agents

GitHub Copilot custom agents in `.github/agents/`. Pick one from the Chat agent menu in
VS Code. Canonical copies: `copilot-agents/variants/shyft-bench-platform/`.

| Agent | Role | Reports to |
|---|---|---|
| Researcher | Proposes experiment plans as catalogue entries; keeps claims honest | Founder, via the Architect |
| Architect | Lead: turns requirements into Lean specs and decisions, delegates, runs the review round | Founder |
| Sigma2 Guru | Operates Sigma2 only through `scripts/sigma2.py` (no file edits). First: collect the finished reverse run from DTSS container `se-bench`; later slices: pod-code divergence, launch decision, staging, launches, monitoring (local VS Code only) | Architect |
| Backend Developer | Lean proofs and reference model, Python pipeline, C++ for Shyft; answers Shyft questions from the pinned commit | Architect |
| Frontend Developer | TypeScript dashboard | Architect |
| Documentation | README, AGENTS and generated docs true to the spec; literature search on hydrological benchmarking, recorded as verified references | Architect |
| Lean Reviewer | Review only: smaller, more functional Lean, statements frozen | Architect |
| Code Reviewer | Review only: Python, C++, TypeScript | Architect |
| DevOps | GitHub Actions, the Shyft container, the smoke tier, releases | Architect |
| Independent Auditor | Proof meaning, security, quality; owns the gate (only tightens) | Founder |

## Fixes and the spec

A fix becomes part of the spec only when it changes what the system *should* do.

| Kind | Spec changes? | Recorded as | Who |
|---|---|---|---|
| Decision or meaning change (spec wrong, unclear or silent) | yes | a `D-NNN` decision plus the amended requirement or scenario; the founder approves the statements | Architect, before any fix task |
| Bug (the model or code does not meet approved text) | no | a regression `#guard`, theorem or test under the existing requirement's design unit; a deferred scenario may become executable | any builder, also the cloud agent |
| Process (reports, mutation checks, approvals) | no | `audit/report.md` | Independent Auditor or founder |

Branches: a review round has one integration branch (its pull request). Spec changes go in
first, on their own sub-branch, merged once the founder has approved the statements. Each fix
is a small sub-branch with a pull request into the integration branch. A fix task never
changes requirement text or decisions: if it cannot be done without that, stop and report.

## Rules for every agent

- The Lean specification is the source of truth. Experiments, stacks, goal functions,
  periods and the canonical order and colours are defined in `ShyftBench/` and exported;
  they are not redefined in code.
- Requirement text, theorem statements and decisions change only with the founder's approval.
- Shyft facts come from the pinned commit (`shyftPin`), not from a local checkout's branch.
- Nothing runs on Sigma2 unless `decideLaunch` allows it on the pod's actual Shyft build.
- Sigma2 is reached only through `python3 scripts/sigma2.py` (D-009); a workspace hook blocks raw
  `kubectl`, the auth helper and kubeconfig for every agent.
- Regime codes are the R script's (1 mountain, 2 inland, 3 atlantic, 4 baltic,
  0 transition). Pass regimes between modules by name.
- Never handle credentials; never delete remote data; never work on `main`. Agents cannot
  sign commits, so they stage changes and hand the founder the commands.

## In GitHub's cloud (D-011)

- Assign an issue to Copilot to have the cloud agent work on it; it opens a pull request.
  `.github/workflows/copilot-setup-steps.yml` installs the Python requirements and builds the
  Lean package first, so the agent can run `python3 scripts/gate.py check` itself.
- The workspace hooks in `.github/hooks/` are for local VS Code. The cloud agent's pull request
  must pass the `gate` check before it can merge (ruleset in `.github/rulesets/`).
- Sigma2 is not reachable from GitHub's cloud: collection and launches stay local (D-009).
- `.github/workflows/pages.yml` publishes the dashboard from `main` after the gate passes.
