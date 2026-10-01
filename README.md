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
| `ShyftBench/Requirements.lean` | Requirements `bench.*`, with scenarios |
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
