# shyft-bench-platform

Benchmarking [Shyft](https://gitlab.com/shyft-os/shyft) hydrological model stacks with
different forcings and goal functions on a large sample of Norwegian catchments, automated
from experiment set-up on Sigma2 to a results dashboard. Successor to
`shyft-hydro-benchmarking`: it reuses that work's published results (Zenodo
[10.5281/zenodo.15595323](https://doi.org/10.5281/zenodo.15595323)) without re-running them.

The specification comes first. It is a [lean-spec](open-lean-spec/README.md) package, and
the build checks it.

| Module | What it holds |
|---|---|
| `ShyftBench/Requirements/` | Requirements `bench.*`, with scenarios, one file per area (index in `Requirements.lean`) |
| `ShyftBench/Decisions.lean` | Founder decisions `D-NNN`, linked to requirements |
| `ShyftBench/Domain.lean` | Stacks, forcings, goal functions, regimes, periods; canonical order and colours |
| `ShyftBench/Catchments.lean` | Catchment cohorts from the frozen regime table in `data/regime/` |
| `ShyftBench/Experiment.lean` | Experiments, Shyft builds, the launch decision, result filing, matched comparisons |
| `ShyftBench/Catalog.lean` | The experiment catalogue: legacy imports and planned experiments |
| `ShyftBench/Design.lean`, `Trace.lean` | Design units, traceability guards, the verification statement |

## Status

The specification and the experiment catalogue are in place. The pipeline (stage, collect,
metrics, export), the dashboard and the smoke tier are not built yet. Their requirements
are listed as open obligations in the verification statement.

The first planned experiment is **RPMFSM2K with seNorge2018 forcing on the 70 snow-dominated
catchments** (43 mountain + 27 inland). If the Sigma2 pod's Shyft lacks `r_pm_fsm2_k`,
there are two options: run **PTFSM2K** as a separate experiment, or request a new image.

## Check

```bash
lake build
python3 scripts/gate.py check
```

`python3 scripts/regime_table.py` regenerates `ShyftBench/Generated/Regime.lean` from
`data/regime/mon_Q_regime.csv`; `--check` fails if the generated module is stale.

## Agents

The repository has a GitHub Copilot agent crew in `.github/agents/`; see [AGENTS.md](AGENTS.md).
Issues can be assigned to the Copilot cloud agent; its pull requests go through the Lean gate.

## Dashboard and provenance

`main` is published to GitHub Pages after the Lean gate passes (`.github/workflows/pages.yml`).
Until the dashboard is built, a placeholder page is published. Every published file is listed
in `SHA256SUMS` and has a build-provenance attestation; to check a downloaded file:

```bash
gh attestation verify <file> --repo osilan/shyft-bench-platform
```

Rules for `main` (signed commits, no force-push, pull request plus gate) are recorded in
[`.github/rulesets/`](.github/rulesets/README.md).

## Working on Sigma2

Every Sigma2 step is a command of `scripts/sigma2.py` (decision D-009), so a collection can be
repeated without any agent. You log in to NIRD yourself; the tool reuses your kubectl session
and tells you (exit code 4) when the login has expired.

```bash
python3 scripts/sigma2.py preflight --run 20261005-1400-collect-reverse
python3 scripts/sigma2.py inventory --run 20261005-1400-collect-reverse --container se-bench
python3 scripts/sigma2.py snapshot  --run 20261005-1400-collect-reverse --experiment legacy-rpmstk-reverse --container se-bench
#   review runs/<run>/expected.proposed.json, set stations, save it as runs/<run>/expected.json
python3 scripts/sigma2.py complete  --run 20261005-1400-collect-reverse
python3 scripts/sigma2.py extract   --run 20261005-1400-collect-reverse --confirm
python3 scripts/sigma2.py fetch     --run 20261005-1400-collect-reverse
```

- Target (context, namespace, deployment, DTSS address, paths): `config/sigma2.json`.
- Legacy runs: the reverse run was launched by hand from the old `run_benchmark_experiment.py`
  in batches, so `snapshot` reads the run settings from that file and `fill_benchmark_data.py`.
  A run is reverse when its calibration starts after its simulation starts (`T0_CAL`, `T0_SIM`);
  the series names carry no `_rev`. Goals, pcorr and variants come from the series present;
  the stations the run covered are confirmed by the founder.
- Pod-side code: `scripts/sigma2_pod/`, piped to the pod's python on stdin; nothing is copied
  into the pod. Each pod script's SHA-256 is recorded in the manifest.
- Results: `runs/<run_id>/` (git-ignored) with `manifest.json`, the JSON/Markdown reports,
  and `data/` with NetCDF files verified against the pod's checksums. NetCDF files also carry
  a content hash that ignores who collected them when, so two collections of the same data
  compare equal.
- Read-only by default; `extract` writes a new pod folder only with `--confirm` and never
  into the DTSS store. Output folders are never overwritten.
- Tests: `python3 -m unittest tests.test_sigma2` (a fake kubectl runs the real pod scripts
  against a stub Shyft; extraction tests need `pip install -r requirements.txt`).
