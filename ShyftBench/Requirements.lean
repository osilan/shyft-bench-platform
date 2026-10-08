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
  shall "Define every experiment as a typed catalogue entry naming its Shyft stack or LSTM model, forcing, goal functions, optimiser, catchments, calibration and simulation periods, precipitation-correction setting and seed or variant; derive forward or reverse direction from its periods. Keep forcing-specific experiments separate, import legacy results read-only, and ensure ids are unique, planned experiments are well formed, and the catalogue plans at least one run."
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
    given "the catalogue plans the active PTFSM2K experiment"
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
  shall "When the pod cannot run a planned experiment, do not substitute a different stack or launch a fallback experiment; request an image built from the pinned commit and start no run."
  strength must

  scenario "missing PTFSM2K requests an image"
    given "the pod lacks the stack in the active PTFSM2K plan"
    when "the launch decision is taken"
    then_ "no experiment starts, no fallback stack is substituted, and the request names the pinned commit"
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
  shall "Compare experiments only when forcing, periods, optimiser, goal functions and precipitation-correction settings match, and only over the catchments both experiments contain. Never compare across forcings. Preserve seed variants as a distribution and never silently select a best seed."
  strength must

  scenario "comparison uses the common catchments"
    when "two comparable experiments are compared"
    then_ "every compared catchment belongs to both experiments"
    check executable

  scenario "different forcings cannot be compared"
    given "two otherwise matching experiments use different forcings"
    when "comparability is checked"
    then_ "the experiments are not comparable"
    check deferred "forcing equality is not yet enforced by the experiment model"

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
  shall "Recompute dashboard metrics from daily observed and simulated discharge series for every legacy Shyft, reverse-run, LSTM and new result; do not display metric columns stored in legacy CSVs. Use hydroeval for NSE, KGE (Gupta et al., 2009), KGE' (Kling et al., 2012), PBIAS and KGE(1/Q), and a characterized port of the old repository's Ruzzante et al. (2025) NSE decomposition. KGE(1/Q) uses 1/(Q + ε), where ε is 0.01 times mean observed flow over the evaluation period, added to both series; retain zero-flow days. Check each implementation against fixed reference values."
  strength must

  scenario "pinned hydroeval formulations"
    given "a pinned hydroeval version"
    when "the metric implementations are selected"
    then_ "the version and the mapping of hydroeval kge and kgeprime to the two specified KGE formulations are verified and recorded"
    check deferred "the pinned hydroeval version and formulation mapping are not verified"

  scenario "reference series"
    given "a fixed observed and simulated series with known metric values"
    when "the metrics are computed"
    then_ "NSE, both KGE formulations and PBIAS match their fixed references within the stated tolerance"
    check deferred "metrics are not ported yet"

  scenario "low-flow metric retains zero-flow days"
    given "an evaluation series containing zero-flow days"
    when "KGE(1/Q) is computed with ε equal to 0.01 times mean observed flow"
    then_ "ε is added to observed and simulated flow, no zero-flow day is dropped, and the value matches its fixed reference"
    check deferred "KGE(1/Q) and its zero-flow reference test are not implemented"

  scenario "Ruzzante port is characterized"
    given "fixed series and output from the old repository's Ruzzante implementation"
    when "the ported seasonal, interannual and irregular NSE decomposition is computed"
    then_ "NSE components, r, α and variance shares match the characterized old output within the stated tolerance"
    check deferred "the old output has not been pinned and the decomposition is not ported"

requirement exportData where
  id "bench.export"
  shall "Generate a machine-readable dashboard export from the Lean specification. Emit canonical definitions, catalogue and manifest as JSON; catchment geometries as GeoJSON with regime names; and the long metrics table and daily observed and simulated discharge plus available SWE and snow-covered area series as Parquet, partitioned by experiment and catchment. The metrics table has one row per experiment, model, goal, forcing, direction, pcorr, optimiser, seed, station, period kind and metric. Include variants, periods, Shyft commit and provenance in the catalogue, and source files with SHA-256 values and code version in the manifest. Keep series split by catchment and experiment so clients need not load the full dataset."
  strength must

  scenario "export preserves canonical definitions and provenance"
    when "the dashboard export is generated"
    then_ "its canonical definitions and catalogue come from Lean and every metric row traces to source checksums, code version and Shyft commit"
    check deferred "the export schema and generator are not implemented"

  scenario "large series are split for delivery"
    given "daily discharge, SWE or snow-covered area series for multiple catchments"
    when "series are exported"
    then_ "each catchment and experiment has separately addressable series data, with only available variables included"
    check deferred "series export is not implemented"

  scenario "catchment geometry carries regime names"
    when "catchments are exported"
    then_ "their GeoJSON geometry includes each catchment's regime by name"
    check deferred "catchment GeoJSON export is not implemented"

requirement dashboard where
  id "bench.dashboard"
  shall "Present a static TypeScript dashboard that reads the Lean-generated export and computes no metrics. Show Shyft stacks and LSTM in canonical model order and colours. Let forcing select the experiment before other filters; never compare results across forcings. Support filters and grouping by goal, regime, metric, forward or reverse direction derived from periods, precipitation correction, optimiser and seed, preserving seed spread without silently selecting a best seed. Show only matched comparisons. The scoreboard shows models by goals and the median metric over the matched cohort. Also support cumulative distributions, per-catchment model comparisons, calibration-to-validation drop, precipitation-correction effects, both KGE component formulations, Ruzzante decomposition, low-flow KGE(1/Q) and flow-duration curves, forward-versus-reverse, LSTM-versus-Shyft, seed spread, maps and catchment hydrographs with available SWE and snow-covered area."
  strength must

  scenario "forcing selects a comparable result set"
    given "results from seNorge2018 and AIFS experiments"
    when "the user selects a forcing and compares models"
    then_ "only results for that forcing are shown and no comparison can contain results from another forcing"
    check deferred "dashboard is not built"

  scenario "variants and seeds remain visible"
    given "matched results with different direction, pcorr, optimiser or seed variants"
    when "the user filters or groups the results"
    then_ "the selected variants are shown, and seed spread is preserved without silently choosing a best seed"
    check deferred "dashboard variant views are not built"

  scenario "model comparison uses the matched cohort"
    given "results from comparable models for a regime"
    when "the user opens a model comparison view"
    then_ "score distributions and per-catchment comparisons use only the matched catchments"
    check deferred "matched dashboard comparisons are not built"

  scenario "scoreboard reports matched-cohort medians"
    given "matched metric results for multiple models and goals"
    when "the scoreboard is rendered"
    then_ "each model-by-goal value is the median over the matched cohort"
    check deferred "the median scoreboard is not built"

  scenario "static view consumes exported data"
    when "the dashboard is built and loaded"
    then_ "it renders the Lean-generated export without recomputing metrics in TypeScript"
    check deferred "the static dashboard is not built"

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
