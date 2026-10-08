import LeanSpec.Elab.Sugar

/-!
# Requirements: operations

The CI smoke tier and safe operation on Sigma2.
-/

open LeanSpec

namespace ShyftBench

requirement smokeTier where
  id "bench.ci.smoke"
  shall "Run a containerised smoke tier in CI from the pinned Shyft commit using a small DTSS and short forcing slice. Exercise one PTFSM2K calibration for KGE and pcorr enabled on one mountain station drawn once at random from the frozen regime table with a recorded seed and fixed in Lean, then run the metric and figure steps against recorded references."
  strength must

  scenario "smoke run in CI"
    when "a pull request is opened"
    then_ "the smoke tier completes and its metrics match the recorded reference"
    check deferred "container and fixture are not built"

  scenario "smoke catchment is a mountain station"
    when "the package builds"
    then_ "the smoke station is in the mountain cohort of the frozen regime table and the smoke experiment is PTFSM2K, KGE, pcorr enabled"
    check executable

requirement sigma2Safety where
  id "bench.sigma2.safety"
  shall "Operate on Sigma2 only through the founder's existing kubectl session: never handle credentials, never delete remote data, and write a manifest for every staged file and launched batch."
  strength must

  scenario "launch leaves a manifest"
    when "a batch is launched on the pod"
    then_ "a manifest records the code version, experiment id, Shyft commit and output location"
    check deferred "launcher is not implemented"

requirement codeDivergence where
  id "bench.sigma2.code-divergence"
  shall "Before any new experiment is launched on Sigma2, establish read-only how the benchmark code in the pod at /shyft-data/projects/shyft-hydro-benchmarking, starting with run_benchmark_experiment.py and its configuration, diverged from the shyft-hydro-benchmarking repository, and record the pod's active configuration, its Shyft version and the layout of the DTSS store at /shyft-var/dtss/db."
  strength must

  scenario "pod file matches no commit"
    given "a pod file's content matches no commit of the repository"
    when "the divergence check runs"
    then_ "the report lists the file with its SHA-256, the nearest commit and the lines that differ, and nothing in the pod or the store is changed"
    check deferred "the divergence check has not been run on the pod"

end ShyftBench
