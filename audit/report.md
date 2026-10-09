# Independent audit report

## Gate run

- `python3 scripts/gate.py check`: **FAIL** (exit 1). The only reported failure is the stale `audit/fingerprint.tsv`; the gate reports five added guard fingerprints. No `gate.py update` was run, and this report does not claim fingerprint acceptance.
- `python3 scripts/gate.py metrics`: **PASS** (exit 0). `metrics: {"guards": 112, "lean_files": 17, "lean_lines": 1450, "requirements": 18, "scenarios_deferred": 24, "scenarios_executable": 15, "sorry": 0, "sorry_dependent_theorems": 0, "tests_passed": true, "theorems": 187, "warnings": 0}`.
- The committed fingerprint is stale; P12 review is pending the founder. The current delta is: requirements changed—none; theorems added—none; guards added—five: `ShyftBench/Experiment.lean#344` (`093a7dd6fe8a`), `ShyftBench/Experiment.lean#392` (`3580311f3400`), `ShyftBench/Catalog.lean#119` (`6c7c16cd5ddb`), `ShyftBench/Catalog.lean#120` (`b887018e4ef8`), and `ShyftBench/Catalog.lean#123` (`398df8b3d777`).

## Mutation results

| Batch | Killed | Unexpected | Survivors |
|---|---:|---:|---:|
| P10a (`audit/mutations/P10a.md`) | 9/9 | 0 | 0 |
| P10b (`audit/mutations/P10b.md`) | 9/10 | 1 | 0 |
| P10c (`audit/mutations/P10c.md`) | 6/7 | 1 | 0 |
| P10d (`audit/mutations/P10d.md`) | 6/6 | 0 | 0 |
| Earlier batch (previous report) | 27/29 | 0 | 2 |

P10b's unexpected failure was a dependent short-forward fixture invalidated by the boundary mutation, not an isolated equality-boundary check. P10c's unexpected failure was the upstream `Experiment.accepts_model` proof failing before the named catalogue checks. The earlier batch's survivors were the 800-day validation-cutoff mutant and the non-isolating forcing-fixture mutant.

## Fallback policy

Under D-021, the founder chooses either to run the separately identified fallback experiment if the pod provides its stacks, or to request an image. A fallback is never relabelled as the planned experiment.

## Open items

- P10b #1 (`audit/mutations/P10b.md`): no isolated guard checks calibration equal to the whole simulation (forward boundary).
- P10b #7 (`audit/mutations/P10b.md`): no permanent fixture compares model arms that differ in goals.
- P10c #7 (`audit/mutations/P10c.md`): the model check in `accepts` is caught by the `accepts_model` proof before the named catalogue checks.
- P10d (`audit/mutations/P10d.md`): both `detailFigures` guards pass vacuously while the list is empty.
- R4 (review-round table in `docs/briefs/architect-dashboard-data.md`): variant comparison guards use one-station copies (`legacyPtgskComparable`, `legacyRpmstk*Comparable`) because legacy catchment lists are empty; switch to catalogue entries after the import.
- Copilot's second review of `osilan/shyft-bench-platform#1`: future entries in `Catalog.ok` need consideration.
- Copilot's second review of `osilan/shyft-bench-platform#1`: future experiments can be launched.
- Copilot's second review of `osilan/shyft-bench-platform#1`: the whole seNorge2018 grid needs review.
- Copilot's second review of `osilan/shyft-bench-platform#1`: the fallback proof misses the both-unavailable case.
- Copilot's second review of `osilan/shyft-bench-platform#1`: missing direction is counted as a direction difference.
- Copilot's second review of `osilan/shyft-bench-platform#1`: the smoke test hard-codes the seed.
- Copilot's second review of `osilan/shyft-bench-platform#1`: `bench.results.filing` wording still says "stack".
- Copilot's second review of `osilan/shyft-bench-platform#1`: the site-selector scenario is executable without site evidence.
