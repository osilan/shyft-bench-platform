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

end ShyftBench
