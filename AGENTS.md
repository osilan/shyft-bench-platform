# Agents

GitHub Copilot custom agents in `.github/agents/`. Pick one from the Chat agent menu in
VS Code. This folder is the only copy.

| Agent | Role | Works from |
|---|---|---|
| Architect | Turns requests and experiment ideas into Lean requirements, decisions and catalogue entries; files issues. Never builds | A request from the founder |
| Builder | Builds one issue: Lean proofs and guards, Python pipeline, dashboard, CI, docs; Shyft questions from the pinned commit. Also the GitHub cloud agent's rules | An issue |
| Reviewer | Review only, on one pull request: Lean, Python, C++, TypeScript | A pull request |
| Sigma2 Guru | Operates Sigma2 only through `scripts/sigma2.py` (no file edits; local VS Code only) | The founder's request |
| Independent Auditor | Proof meaning, security, quality; owns the gate (only tightens). Reports to the founder | The founder's request |

## The loop

1. **Request** from the founder to the Architect.
2. **Spec pull request** (`spec/<topic>` into `main`): requirements, decisions, catalogue.
   The founder reads the changed statements, runs `python3 scripts/gate.py update`, commits,
   and adds the label `statements-approved`. Merge.
3. **Issues**: the Architect files one issue per small task
   (`.github/ISSUE_TEMPLATE/task.md`), ordered with "Waits for #N" where two touch one file.
4. **Build**: the founder assigns an issue to Copilot (cloud) or runs the Builder locally.
   One issue, one pull request into `main`.
5. **Review**: the Reviewer (or Copilot code review) comments on the pull request; the gate
   check must pass. The founder merges.
6. Findings that are not fixed in that pull request go back to the Architect, who sorts them
   (below) into a spec change or new issues.

No integration branches and no review rounds: every pull request goes into `main` behind the gate.

## Fixes and the spec

A fix becomes part of the spec only when it changes what the system *should* do.

| Kind | Spec changes? | Recorded as | Who |
|---|---|---|---|
| Decision or meaning change (spec wrong, unclear or silent) | yes | a `D-NNN` decision plus the amended requirement or scenario, in a spec pull request with `statements-approved` | Architect writes it; founder approves |
| Bug (the model or code does not meet approved text) | no | a regression `#guard`, theorem or test under the existing requirement's design unit | Builder, from an issue |
| Process (reports, mutation checks, approvals) | no | `audit/report.md` | Independent Auditor or founder |

A build task never changes requirement text or decisions: if it cannot be done without that,
stop and say so in the pull request.

## The gate in pull requests

`python3 scripts/gate.py check` is the definition of done. In CI, a pull request may only
**add** statements (guards, theorems, requirements) relative to `main`, and
`audit/fingerprint.tsv` must match the build (the Builder runs `gate.py update` for its
additions). A changed or removed statement fails until the founder adds the label
`statements-approved`. Pushes to `main` are strict.

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
- `docs/briefs/` is history. Agents do not read it; new work is an issue.

## In GitHub's cloud (D-011)

- Assign an issue to Copilot to have the cloud agent work on it; it follows
  `.github/agents/builder.agent.md` and opens a pull request into `main`.
  `.github/workflows/copilot-setup-steps.yml` installs the Python requirements and builds the
  Lean package first, so the agent can run `python3 scripts/gate.py check` itself.
- The workspace hooks in `.github/hooks/` are for local VS Code. The cloud agent's pull request
  must pass the `gate` check before it can merge (ruleset in `.github/rulesets/`).
- Sigma2 is not reachable from GitHub's cloud: collection and launches stay local (D-009).
- `.github/workflows/pages.yml` publishes the dashboard from `main` after the gate passes.
