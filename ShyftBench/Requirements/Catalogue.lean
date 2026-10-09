import LeanSpec.Elab.Sugar

/-!
# Requirements: catalogue and launch

The experiment workflow, the typed catalogue, the pinned Shyft build and the launch decision with its fallback.
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

  scenario "direction is derived from the periods"
    given "a calibration period at the start of the simulation period, or inside it"
    when "the experiment is classified"
    then_ "it is forward when calibration starts the simulation, reverse when calibration starts later and ends at the end of the simulation (within one year), and has no direction otherwise; the validation period is the simulation minus the calibration, without segments shorter than one year"
    check deferred "covered by guards on the legacy periods (D-010, D-019, D-024), not yet by a theorem"

  scenario "legacy catchment lists"
    given "a legacy entry imported from the archive"
    when "the catalogue is loaded"
    then_ "its catchment list is the stations that have result files"
    check deferred "the archive is not imported yet, so legacy catchment lists are empty"

  scenario "seed and SCE-UA variants"
    given "legacy runs with seeds v00-v04 or the SCE-UA optimiser"
    when "they are catalogued"
    then_ "each seed and optimiser is a separate variant of its experiment"
    check deferred "the seed and SCE-UA runs are not catalogued yet"

  scenario "LSTM entries"
    given "the LSTM forward and reverse runs in lstm_baseline/runs"
    when "they are catalogued"
    then_ "each is an experiment with the LSTM model, its own periods and direction, and its catchments"
    check deferred "the LSTM runs are not catalogued yet"

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
  shall "When the pod cannot run the planned experiment, follow the founder's choice: run the fallback experiment if the pod provides its stacks, or request a new image built from the pinned commit; never relabel the fallback as the planned experiment."
  strength must

  scenario "image request starts nothing"
    given "the pod lacks a planned stack and the founder chose to request an image"
    when "the launch decision is taken"
    then_ "no experiment starts and the request names the pinned commit"
    check executable

  scenario "fallback runs only when the pod provides it"
    given "the pod lacks a planned stack and the founder chose to run the fallback"
    when "the launch decision is taken"
    then_ "the fallback experiment starts under its own id if the pod provides its stacks, otherwise an image is requested, and the planned experiment never starts"
    check executable

end ShyftBench
