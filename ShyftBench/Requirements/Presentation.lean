import LeanSpec.Elab.Sugar

/-!
# Requirements: export and dashboard

What is exported from the computed results and how the dashboard presents it.
-/

open LeanSpec

namespace ShyftBench

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

end ShyftBench
