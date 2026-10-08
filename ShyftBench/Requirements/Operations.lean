import LeanSpec.Elab.Sugar

/-!
# Requirements: operations

The CI smoke tier and safe operation on Sigma2.
-/

open LeanSpec

namespace ShyftBench

requirement smokeTier where
  id "bench.ci.smoke"
  shall "Run a containerised smoke tier in CI from the pinned Shyft commit using a small DTSS and short forcing slice. Exercise one PTFSM2K calibration for KGE, catchment cid-10-178.1.0 and pcorr enabled, then run the metric and dashboard steps against recorded references."
  strength must

  scenario "smoke run in CI"
    when "a pull request is opened"
    then_ "the smoke tier completes and its metrics match the recorded reference"
    check deferred "container and fixture are not built"

  scenario "smoke calibration uses the selected variant"
    when "the smoke calibration is planned"
    then_ "it uses PTFSM2K, KGE, cid-10-178.1.0 and pcorr enabled"
    check deferred "the smoke experiment fixture is not built"

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
