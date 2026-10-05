import LeanSpec.Design
import LeanSpec.Snapshot
import ShyftBench.Requirements
import ShyftBench.Catalog

/-!
# Design units

Only the parts implemented in Lean have design units here. lean-spec v1.0.0's `TargetLang`
has no Python or C++, so the Python pipeline and Shyft code are traced through deferred
scenarios until that gap is closed upstream.
-/

open LeanSpec

namespace ShyftBench

def catalogueDesign : DesignUnit := {
  id := typedCatalogue.id
  interfaces := ⟨#[⟨"Experiment", by native_decide⟩, ⟨"Entry", by native_decide⟩,
    ⟨"catalog", by native_decide⟩], by native_decide⟩
  functions := #[⟨"Catalog.ok", by native_decide⟩, ⟨"Catalog.live", by native_decide⟩]
  tests := ⟨#[⟨"Catalog.ok catalog", by native_decide⟩], by native_decide⟩
  theorems := #[⟨"ShyftBench.catalog_ok_live", by native_decide⟩]
}

def pinnedShyftDesign : DesignUnit := {
  id := pinnedShyft.id
  interfaces := ⟨#[⟨"ShyftBuild", by native_decide⟩, ⟨"shyftPin", by native_decide⟩], by native_decide⟩
  tests := ⟨#[⟨"rpmfsm2kSnow.runsOn shyftPin", by native_decide⟩], by native_decide⟩
  theorems := #[⟨"ShyftBench.rpmfsm2kSnow_launches_on_pin", by native_decide⟩]
}

def launchPreconditionDesign : DesignUnit := {
  id := launchPrecondition.id
  interfaces := ⟨#[⟨"decideLaunch", by native_decide⟩, ⟨"LaunchDecision", by native_decide⟩], by native_decide⟩
  tests := ⟨#[⟨"decideLaunch shyftLocalMaster", by native_decide⟩], by native_decide⟩
  theorems := #[⟨"ShyftBench.decideLaunch_runsOn", by native_decide⟩]
}

def launchFallbackDesign : DesignUnit := {
  id := launchFallback.id
  interfaces := ⟨#[⟨"FallbackChoice", by native_decide⟩, ⟨"ptfsm2kSnow", by native_decide⟩], by native_decide⟩
  tests := ⟨#[⟨"decideLaunch shyftLocalMaster .requestImage", by native_decide⟩], by native_decide⟩
  theorems := #[⟨"ShyftBench.decideLaunch_requestImage", by native_decide⟩]
}

def resultFilingDesign : DesignUnit := {
  id := resultFiling.id
  interfaces := ⟨#[⟨"ResultKey", by native_decide⟩, ⟨"Experiment.accepts", by native_decide⟩], by native_decide⟩
  tests := ⟨#[⟨"rpmfsm2kSnow rejects a PTFSM2K result", by native_decide⟩], by native_decide⟩
  theorems := #[⟨"ShyftBench.rpmfsm2kSnow_rejects_other_stacks", by native_decide⟩]
}

def matchedComparisonDesign : DesignUnit := {
  id := matchedComparison.id
  interfaces := ⟨#[⟨"Experiment.comparableWith", by native_decide⟩,
    ⟨"Experiment.matchedCohort", by native_decide⟩], by native_decide⟩
  tests := ⟨#[⟨"rpmfsm2kSnow.comparableWith ptfsm2kSnow", by native_decide⟩], by native_decide⟩
  theorems := #[⟨"ShyftBench.Experiment.matchedCohort_mem", by native_decide⟩]
}

def snowCohortDesign : DesignUnit := {
  id := snowCohort.id
  interfaces := ⟨#[⟨"snowDominatedStations", by native_decide⟩, ⟨"regimeTable", by native_decide⟩], by native_decide⟩
  tests := ⟨#[⟨"regime counts and hashes", by native_decide⟩], by native_decide⟩
  theorems := #[⟨"ShyftBench.snowCohort_counts", by native_decide⟩]
}

def allRequirements : Array Requirement := #[
  automateWorkflow, typedCatalogue, pinnedShyft, launchPrecondition, launchFallback,
  resultFiling, matchedComparison, snowCohort, legacyReadOnly, collectReverseRun,
  canonicalMetrics, dashboard, smokeTier, sigma2Safety, codeDivergence, documentation,
  independentAudit]

def allDesigns : Array DesignUnit := #[
  catalogueDesign, pinnedShyftDesign, launchPreconditionDesign, launchFallbackDesign,
  resultFilingDesign, matchedComparisonDesign, snowCohortDesign]

def specSnapshot : SpecSnapshot := {
  requirements := allRequirements
  uniqueIds := by native_decide
  designs := allDesigns
}

end ShyftBench
