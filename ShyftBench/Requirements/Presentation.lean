import LeanSpec.Elab.Sugar

/-!
# Requirements: export and dashboard

What is exported from the computed results and how the dashboard presents it.
-/

open LeanSpec

namespace ShyftBench

requirement exportData where
  id "bench.export"
  shall "Generate the site's export from the Lean specification: pre-rendered SVG figures, one CSV data table per figure, a figure index, the canon (model, goal, regime and metric order and colours), the catalogue and a manifest, with the index, canon, catalogue and manifest as JSON. The figure grid is declared in Lean as an explicit list, at most 48 aggregate figures and 10 catchment-detail figures; the export check fails if a declared figure is missing or an undeclared one appears. The internal long metrics table has one row per experiment, model, goal, forcing, direction, pcorr, optimiser, seed, station, period kind and metric, and is stored as Parquet; it is not published. Daily series are not published. A figure may plot one unlabelled point, curve or map marker per catchment; its table then has at most one row per catchment and plotted quantity, and otherwise holds summaries at the fixed percentiles declared in Lean with the cohort size. No table repeats the internal long metrics table, and no figure draws a station label. Each SVG is at most 2 MB, each CSV at most 1 MB and the whole export at most 15 MB (1 MB is 1,048,576 bytes), as declared in Lean; the export check fails above a limit. The manifest records, for every figure and table, its source files with SHA-256 values, the code version and the Shyft commit."
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

  scenario "published set matches the declaration"
    given "an export to publish"
    when "the export is published"
    then_ "its figure ids equal the ids in Figures.published, with none missing and none extra"
    check deferred "Python `pipeline check --scope published` enforces the set against the exported published list, but its checks are not represented in Lean"

  scenario "figure tables follow what the figure plots"
    given "computed metrics for many stations"
    when "the export is generated"
    then_ "a table has at most one row per catchment and plotted quantity when its figure plots per catchment, percentile or median summaries with the cohort size otherwise, and no figure draws a station label"
    check deferred "the Python exporter writes the summary tables, but its checks are not represented in Lean"

  scenario "export stays within the size limits"
    given "a generated export"
    when "the export check runs"
    then_ "it fails if any SVG exceeds the SVG limit, any CSV the CSV limit or the whole export the export limit declared in Lean"
    check deferred "the size check runs in Python; Lean declares the limits but cannot read file sizes"

requirement dashboard where
  id "bench.dashboard"
  shall "Present the results as final, paper-quality figures on a thin static site organised by research question into the pages declared in Lean (Figures.pages): study area, models and precipitation correction, goal functions, robustness (direction and equifinality) and the comparison with the regional LSTM; a planned page is hidden until its data are in the catalogue. Python draws every figure in advance as SVG, and the same files go into the paper. Each page shows its figures at full width with the selectors declared for that page (precipitation correction, model or goal), and each figure's data table is folded below it, rounded, with a CSV download. Nothing is computed in the browser. seNorge2018 is the main experiment and the default; results are never compared across forcings. Show only matched comparisons, in the canonical model order and colours; direction is shown by line style, never by another colour. Seeds are not a selector: their spread is shown inside the figures as the envelope of the per-seed curves, never pooled and never reduced to a best seed. A figure may show one unlabelled point, curve or map marker per catchment. Maps are static SVG drawn from the pinned catchment attributes and Norway outline."
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

  scenario "cumulative distributions are drawn at fixed percentiles"
    given "matched results with finite values for several models and goals"
    when "a cumulative distribution is drawn"
    then_ "each model curve is plotted at the percentiles declared in Lean, using linear interpolation, and each panel shows its cohort size"
    check deferred "the Python renderer draws the percentile curves, but LeanSpec has no Python target"

  scenario "diagnostic views summarise per model and goal"
    given "matched results for several models and goals"
    when "the kge-compass, low-flow and ruzzante figures are drawn"
    then_ "kge-compass shows the medians of both KGE formulations with interquartile bars per model in one panel per goal, low-flow shows a KGE(1/Q) box per model and goal, ruzzante shows medians with interquartile bars per model and goal for its twelve components, and none draws or labels individual stations"
    check deferred "the Python renderer draws the summary views, but LeanSpec has no Python target"

  scenario "first slice is published"
    given "the legacy seNorge forward BOBYQA results for ptgsk, ptstk, ptsthbv, rpmgsk and rpmstk"
    when "the site is published"
    then_ "it shows a scoreboard figure with its CSV table for each pcorr setting, containing all five stacks in canonical model order and each model-goal median over the matched catchment cohort"
    check deferred "the five-stack build and static site are not yet published"

  scenario "site follows the declared pages"
    given "the pages declared in Lean"
    when "the site is loaded"
    then_ "it shows one menu entry per published page, that page's figures at full width with its declared selectors, and each data table folded below its figure with rounded values and a CSV download"
    check deferred "the page layout is not built (D-032)"

  scenario "direction is drawn by line style"
    given "forward and reverse results of one model with several seeds"
    when "they are drawn in one figure"
    then_ "both use the model's canonical colour, forward solid and reverse dashed, with seed spread as the envelope of the per-seed curves"
    check deferred "the reverse run and the forward seed runs are not in the catalogue"

  scenario "maps use pinned locations"
    given "the catchment attributes and Norway outline pinned in Lean"
    when "a map is drawn"
    then_ "each catchment is one unlabelled marker at its pinned location on the pinned outline, and the SVG is within the size limit"
    check deferred "the catchment attributes and outline are not pinned yet"

  scenario "site computes nothing"
    when "the site is built and loaded"
    then_ "it reads only the figure index and renders no metric computed in the browser"
    check deferred "the site is not built"

end ShyftBench
