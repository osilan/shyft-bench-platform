import ShyftBench.Requirements.Catalogue
import ShyftBench.Requirements.Results
import ShyftBench.Requirements.Metrics
import ShyftBench.Requirements.Presentation
import ShyftBench.Requirements.Operations
import ShyftBench.Requirements.Governance

/-!
# Requirements

From Olga's brief (2026-10-01): a production platform for benchmarking Shyft model stacks
with different forcings and goal functions on a large sample of Norwegian catchments,
automating the whole workflow from experiment set-up on Sigma2 to the dashboard. Old
results are reused, not re-run. Decisions refining these are in `ShyftBench/Decisions.lean`.

One file per area under `ShyftBench/Requirements/`, so every edit has unique context:

| File | Requirements |
|---|---|
| `Catalogue.lean` | `bench.workflow.automate`, `bench.experiment.catalogue`, `bench.shyft.pinned`, `bench.launch.precondition`, `bench.launch.fallback` |
| `Results.lean` | `bench.results.filing`, `bench.compare.matched`, `bench.cohort.snow`, `bench.legacy.read-only`, `bench.collect.reverse-run` |
| `Metrics.lean` | `bench.metrics.canonical` |
| `Presentation.lean` | `bench.export`, `bench.dashboard` |
| `Operations.lean` | `bench.ci.smoke`, `bench.sigma2.safety`, `bench.sigma2.code-divergence` |
| `Governance.lean` | `bench.docs`, `bench.audit.independent` |
-/
