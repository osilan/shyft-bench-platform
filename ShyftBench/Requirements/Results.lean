import LeanSpec.Elab.Sugar

/-!
# Requirements: results, comparison and collection

Filing results, matched comparisons, the snow cohort, legacy imports and the reverse-run collection.
-/

open LeanSpec

namespace ShyftBench

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
  shall "Compare two results only along one chosen axis (model, goal, direction, precipitation correction, optimiser or seed): they differ in that axis and agree on all the others, over the catchments both contain. Forcing is never an axis; never compare across forcings. Preserve seed variants as a distribution and never silently select a best seed."
  strength must

  scenario "comparison uses the common catchments"
    when "two comparable experiments are compared"
    then_ "every compared catchment belongs to both experiments"
    check executable

  scenario "different forcings cannot be compared"
    given "two otherwise matching experiments use different forcings"
    when "comparability is checked along any axis"
    then_ "the experiments are not comparable"
    check executable

  scenario "arms differ only in the chosen axis"
    given "two experiments comparable along an axis"
    when "comparability holds"
    then_ "they differ in the chosen axis and agree on every other axis"
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

end ShyftBench
