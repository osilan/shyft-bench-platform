/-!
# Decision log

Founder decisions, each linked to the requirements it refines. `ShyftBench/Trace.lean`
fails the build if a link names no requirement.
-/

namespace ShyftBench

structure Decision where
  id : String
  date : String
  decided : String
  why : String
  refines : List String
  deriving Repr

def decisions : List Decision := [
  { id := "D-001", date := "2026-10-01"
    decided := "First new experiment: RPMFSM2K (r_pm_fsm2_k) on the snow-dominated cohort, pinned to shyft origin/master at bfbdbe63c or later."
    why := "r_pm_fsm2_k is on origin/master with Python bindings and DRMS support; the local master (2026-04-06) and the fsm_tin_1403 checkout lack it."
    refines := ["bench.shyft.pinned", "bench.experiment.catalogue"] },
  { id := "D-002", date := "2026-10-01"
    decided := "Before launch, check the pod's Shyft build for r_pm_fsm2_k. If it is missing, run PTFSM2K on Sigma2 instead, or ask the Sigma2 team for a new image."
    why := "The pod's Shyft version is not known; a run must not start on a build that lacks its stack."
    refines := ["bench.launch.precondition", "bench.launch.fallback", "bench.results.filing"] },
  { id := "D-003", date := "2026-10-01"
    decided := "The snow-dominated cohort is the mountain and inland stations of calc_hydrological_regime.r's output as it is now (70 stations); the classification is not extended."
    why := "Most other catchments in the list have no discharge data; only some AIFS catchments do."
    refines := ["bench.cohort.snow"] },
  { id := "D-004", date := "2026-10-01"
    decided := "Start FSM2 testing with seNorge2018 forcing."
    why := "seNorge2018 (1958-2020) covers the benchmark periods and matches the legacy runs."
    refines := ["bench.experiment.catalogue", "bench.compare.matched"] },
  { id := "D-005", date := "2026-10-01"
    decided := "Repository shyft-bench-platform, hosted on GitHub as primary."
    why := "The Copilot cloud agent, pull-request review and Actions need GitHub; a GitLab-to-GitHub mirror is one-way."
    refines := ["bench.ci.smoke", "bench.audit.independent"] },
  { id := "D-006", date := "2026-10-01"
    decided := "Do not re-run legacy results; import them read-only and collect the finished rpmstk reverse run."
    why := "The published benchmark is the baseline; re-running it would cost compute and break provenance."
    refines := ["bench.legacy.read-only", "bench.collect.reverse-run"] }
]

end ShyftBench
