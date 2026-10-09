import LeanSpec.Elab.Sugar

/-!
# Requirements: export and dashboard

What is exported from the computed results and how the dashboard presents it.
-/

open LeanSpec

namespace ShyftBench

requirement exportData where
  id "bench.export"
  shall "Generate the site's export from the Lean specification: pre-rendered SVG figures, one CSV data table per figure, a figure index, the canon (model, goal, regime and metric order and colours), the catalogue and a manifest, with the index, canon, catalogue and manifest as JSON. The figure grid is declared in Lean as an explicit list, at most 48 aggregate figures and 10 catchment-detail figures; the export check fails if a declared figure is missing or an undeclared one appears. The internal long metrics table has one row per experiment, model, goal, forcing, direction, pcorr, optimiser, seed, station, period kind and metric, and is stored as Parquet; it is not published. Daily series are not published. The manifest records, for every figure and table, its source files with SHA-256 values, the code version and the Shyft commit."
  strength must

  scenario "export matches the declared figure grid"
    given "a set of published figure ids"
    when "the export check runs against the declared grid"
    then_ "it passes only if every declared figure is present and no undeclared figure appears"
    check executable

  scenario "grid is bounded"
    when "the package builds"
    then_ "the declared grid has at most 48 aggregate figures and at most 10 catchment-detail figures"
    check executable

  scenario "detail catchments are the best and worst by KGE"
    given "computed KGE for rpmstk with pcorr on"
    when "the catchment-detail figures are declared"
    then_ "they are the 5 best and the 5 worst catchments, listed explicitly in Lean"
    check deferred "the data-dependent station ranking is not yet recorded in Lean"

  scenario "every figure and table traces to its sources"
    when "the export is generated"
    then_ "the manifest lists for every figure and table its source files with SHA-256 values, the code version and the Shyft commit"
    check deferred "the Python exporter writes source and artifact hashes, but its checks are not represented in Lean"

  scenario "no daily series are published"
    when "the export is generated"
    then_ "it contains figures, tables, index, canon, catalogue and manifest, and no daily discharge, SWE or snow-covered-area series"
    check deferred "the Python exporter limits published files, but its checks are not represented in Lean"

requirement dashboard where
  id "bench.dashboard"
  shall "Present the results as final, paper-quality figures on a thin static site, like a paper or poster with selectors. Python draws every figure in advance as SVG, and the same files go into the paper. The selectors pick the matching figure, forcing first and then the variants (direction, precipitation correction, optimiser); seeds are not a selector, their spread is shown inside the figures. Each figure has its data table below it. Nothing is computed in the browser. seNorge2018 is the main experiment and the default; results are never compared across forcings. Show only matched comparisons, in the canonical model order and colours, and preserve seed spread without silently selecting a best seed. The figures cover the scoreboard (median over the matched cohort), cumulative distributions as small multiples by goal and metric (both KGE formulations, KGE(1/Q) and each Ruzzante decomposition metric, with model curves over a finite matched cohort per panel), per-catchment model comparisons, calibration-to-validation drop, precipitation-correction effects, both KGE formulations, Ruzzante decomposition, low-flow KGE(1/Q) and flow-duration curves, forward versus reverse, LSTM versus Shyft stacks, seed spread, maps and catchment hydrographs."
  strength must

  scenario "forcing selects a comparable result set"
    given "results from seNorge2018 and AIFS experiments"
    when "the user selects a forcing and compares models"
    then_ "only figures for that forcing are shown and no figure compares results across forcings"
    check executable

  scenario "selectors pick a declared figure"
    given "a forcing and a variant selection"
    when "the site is loaded"
    then_ "it shows the matching pre-rendered figure with its data table below it"
    check deferred "the site is not built"

  scenario "variants and seeds remain visible"
    given "matched results with different direction, pcorr, optimiser or seed variants"
    when "a figure is drawn for them"
    then_ "the variants are labelled and seed spread is preserved without silently choosing a best seed"
    check deferred "the figures are not rendered"

  scenario "scoreboard reports matched-cohort medians"
    given "matched metric results for multiple models and goals"
    when "the scoreboard figure is drawn"
    then_ "each model-by-goal value is the median over the matched cohort"
    check deferred "Python tests cover matched-cohort medians and SVG rendering, but LeanSpec has no Python target"

  scenario "cumulative distributions use declared metrics"
    given "matched results with finite values for multiple models and goals"
    when "a cumulative distribution is drawn for a goal"
    then_ "separate metric panels show both KGE formulations, KGE(1/Q) and each Ruzzante decomposition metric, with model curves over the finite catchments matched across models for that panel"
    check deferred "Python CDF behavior is not covered by Lean guards; LeanSpec has no Python target"

  scenario "first slice is published"
    given "the legacy PTGSK seNorge forward BOBYQA results"
    when "the site is published"
    then_ "it shows the scoreboard figure with its table for each pcorr setting"
    check deferred "the Python first-slice build exists, but the data-backed export and static site are not published"

  scenario "site computes nothing"
    when "the site is built and loaded"
    then_ "it reads only the figure index and renders no metric computed in the browser"
    check deferred "the site is not built"

end ShyftBench
