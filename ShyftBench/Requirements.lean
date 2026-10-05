import LeanSpec.Elab.Sugar

/-!
# Requirements

From Olga's brief (2026-10-01): a production platform for benchmarking Shyft model stacks
with different forcings and goal functions on a large sample of Norwegian catchments,
automating the whole workflow from experiment set-up on Sigma2 to the dashboard. Old
results are reused, not re-run. Decisions refining these are in `ShyftBench/Decisions.lean`.
-/

open LeanSpec

namespace ShyftBench

requirement automateWorkflow where
  id "bench.workflow.automate"
  shall "Automate the benchmarking workflow end to end: plan an experiment, stage forcing and observations in the DTSS, launch and monitor the runs on Sigma2, collect results, compute efficiency metrics, and publish them to the dashboard, each stage restartable and recorded in a run manifest."
  strength must

  scenario "one experiment from plan to dashboard"
    given "a planned experiment in the catalogue"
    when "the pipeline runs every stage"
    then_ "its metrics appear in the dashboard and every number traces to a run manifest"
    check deferred "pipeline stages are not implemented"

requirement typedCatalogue where
  id "bench.experiment.catalogue"
  shall "Define every experiment as a typed catalogue entry naming its stacks, forcing, goal functions, optimiser, catchments, calibration and simulation periods and pcorr variants; ids are unique, planned experiments are well formed, and the catalogue plans at least one run."
  strength must

  scenario "catalogue is consistent and live"
    when "the package builds"
    then_ "ids are unique, every planned experiment has work to do and its forcing covers both periods, and at least one run is planned"
    check executable

requirement pinnedShyft where
  id "bench.shyft.pinned"
  shall "Run and answer Shyft questions from one pinned Shyft commit that provides every stack the catalogue plans, not from whatever branch a local clone has checked out."
  strength must

  scenario "planned stacks exist in the pinned build"
    given "the catalogue plans RPMFSM2K"
    when "the launch decision is taken on a pod built from the pinned commit"
    then_ "the planned experiment is launched"
    check executable

requirement launchPrecondition where
  id "bench.launch.precondition"
  shall "Before launching, read the Shyft build on the Sigma2 pod and start an experiment only if that build provides every stack the experiment names."
  strength must

  scenario "no run on a build without the stack"
    given "the pod's Shyft build lacks a stack the experiment names"
    when "the launch decision is taken"
    then_ "that experiment does not start"
    check executable

requirement launchFallback where
  id "bench.launch.fallback"
  shall "When the pod cannot run the planned experiment, follow the founder's choice: run the fallback experiment if the pod provides its stacks, or request a new image built from the pinned commit; never relabel the fallback as the planned experiment."
  strength must

  scenario "image request starts nothing"
    given "the pod lacks a planned stack and the founder chose to request an image"
    when "the launch decision is taken"
    then_ "no experiment starts and the request names the pinned commit"
    check executable

requirement resultFiling where
  id "bench.results.filing"
  shall "File a collected result under an experiment only if that experiment planned its stack, goal function, catchment and pcorr variant, and record the Shyft commit that produced it."
  strength must

  scenario "fallback result is not filed as the planned stack"
    given "a PTFSM2K result carries the RPMFSM2K experiment id"
    when "it is filed"
    then_ "the RPMFSM2K experiment rejects it"
    check executable

requirement matchedComparison where
  id "bench.compare.matched"
  shall "Compare experiments only when forcing, periods, optimiser, goal functions and pcorr variants match, and only over the catchments both experiments contain."
  strength must

  scenario "comparison uses the common catchments"
    when "two comparable experiments are compared"
    then_ "every compared catchment belongs to both experiments"
    check executable

requirement snowCohort where
  id "bench.cohort.snow"
  shall "Select the FSM2 cohort as the mountain and inland stations of the frozen regime table produced by calc_hydrological_regime.r, pinned by SHA-256, without re-classifying other catchments."
  strength must

  scenario "cohort matches the frozen table"
    when "the package builds"
    then_ "the cohort has 70 distinct stations, 43 mountain and 27 inland, and the table and script hashes match the pinned values"
    check executable

requirement legacyReadOnly where
  id "bench.legacy.read-only"
  shall "Import the published Zenodo results as read-only catalogue entries with a checksum per file, and never re-run or modify them."
  strength must

  scenario "imported file changed"
    given "a legacy result file differs from its recorded checksum"
    when "the catalogue is loaded"
    then_ "loading fails and names the file"
    check deferred "legacy import is not implemented"

requirement collectReverseRun where
  id "bench.collect.reverse-run"
  shall "Collect the finished rpmstk reverse run, stored in DTSS container se-bench, before any other Sigma2 work: report completeness per run key against the run's configuration, list partial and duplicated series for the founder's decision, extract the complete series to NetCDF with metadata, and bring them home with SHA-256 checksums and a manifest that records the pod's code checksums, configuration and Shyft version."
  strength must

  scenario "partial or duplicated series"
    given "a run key has a series that ends before the simulation period ends, or more than one series"
    when "the reverse run is collected"
    then_ "the key is listed for the founder's decision and no series for it is chosen or dropped silently"
    check deferred "collection is not implemented"

  scenario "copy verified"
    when "the extracted files are copied home"
    then_ "every file's SHA-256 matches the checksum computed in the pod"
    check deferred "collection is not implemented"

requirement canonicalMetrics where
  id "bench.metrics.canonical"
  shall "Compute efficiency metrics, including KGE, NSE and the Ruzzante et al. (2025) decomposition, from one implementation per metric, checked against fixed reference values."
  strength must

  scenario "reference series"
    given "a fixed observed and simulated series with known metric values"
    when "the metrics are computed"
    then_ "each value matches its reference within the stated tolerance"
    check deferred "metrics are not ported yet"

requirement dashboard where
  id "bench.dashboard"
  shall "Present all catalogue results in a TypeScript dashboard with model comparison by regime, maps and time series, using the canonical stack order and colours and showing only matched comparisons."
  strength must

  scenario "compare stacks for a regime"
    given "results from comparable experiments"
    when "the user selects a regime"
    then_ "the dashboard shows each stack's metric distribution over the matched catchments"
    check deferred "dashboard is not built"

requirement smokeTier where
  id "bench.ci.smoke"
  shall "Run a containerised smoke tier in CI from the pinned Shyft commit: a small DTSS with a few catchments and a short forcing slice, one calibration per stack in the first planned experiment, and the metric and dashboard steps on its output."
  strength must

  scenario "smoke run in CI"
    when "a pull request is opened"
    then_ "the smoke tier completes and its metrics match the recorded reference"
    check deferred "container and fixture are not built"

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

requirement documentation where
  id "bench.docs"
  shall "Keep README, AGENTS and generated documentation consistent with the Lean specification, and maintain the project's literature on hydrological benchmarking as typed references, each verified against its publisher record and linked to the requirements or experiments it informs."
  strength must

  scenario "unverified reference"
    given "a reference whose DOI or publisher record could not be opened"
    when "it is recorded"
    then_ "it is marked unverified and is not cited as read"
    check deferred "the literature module is not built"

requirement independentAudit where
  id "bench.audit.independent"
  shall "Have an independent auditor, outside the architect's crew and reporting to the founder, check security and quality; audit thresholds may only become stricter."
  strength must

  scenario "audit blocks a weakened check"
    given "a change loosens a gate threshold or removes a check"
    when "the gate runs"
    then_ "the gate fails and the auditor reports the finding verbatim"
    check deferred "audit gate is not installed"

end ShyftBench
