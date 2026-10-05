# Agents

GitHub Copilot custom agents in `.github/agents/`. Pick one from the Chat agent menu in
VS Code. Canonical copies: `copilot-agents/variants/shyft-bench-platform/`.

| Agent | Role | Reports to |
|---|---|---|
| Researcher | Proposes experiment plans as catalogue entries; keeps claims honest | Founder, via the Architect |
| Architect | Lead: turns requirements into Lean specs and decisions, delegates, runs the review round | Founder |
| Sigma2 Guru | First: collect the finished reverse run from `se-bench-rev1`; then pod-code divergence, pod and DTSS checks, staging, launches, monitoring and collection on Sigma2 (local VS Code only) | Architect |
| Backend Developer | Lean proofs and reference model, Python pipeline, C++ for Shyft; answers Shyft questions from the pinned commit | Architect |
| Frontend Developer | TypeScript dashboard | Architect |
| Documentation | README, AGENTS and generated docs true to the spec; literature search on hydrological benchmarking, recorded as verified references | Architect |
| Lean Reviewer | Review only: smaller, more functional Lean, statements frozen | Architect |
| Code Reviewer | Review only: Python, C++, TypeScript | Architect |
| DevOps | GitHub Actions, the Shyft container, the smoke tier, releases | Architect |
| Independent Auditor | Proof meaning, security, quality; owns the gate (only tightens) | Founder |

## Rules for every agent

- The Lean specification is the source of truth. Experiments, stacks, goal functions,
  periods and the canonical order and colours are defined in `ShyftBench/` and exported;
  they are not redefined in code.
- Requirement text, theorem statements and decisions change only with the founder's approval.
- Shyft facts come from the pinned commit (`shyftPin`), not from a local checkout's branch.
- Nothing runs on Sigma2 unless `decideLaunch` allows it on the pod's actual Shyft build.
- Regime codes are the R script's (1 mountain, 2 inland, 3 atlantic, 4 baltic,
  0 transition). Pass regimes between modules by name.
- Never handle credentials; never delete remote data; never work on `main`. Agents cannot
  sign commits, so they stage changes and hand the founder the commands.
