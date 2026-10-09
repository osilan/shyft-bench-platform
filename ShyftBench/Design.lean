import LeanSpec.Design
import LeanSpec.Snapshot
import ShyftBench.Requirements
import ShyftBench.Catalog
import ShyftBench.Figures

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
  tests := ⟨#[⟨"Catalog.ok catalog", by native_decide⟩,
    ⟨"forwardPeriodExample.direction? == some .forward", by native_decide⟩,
    ⟨"reversePeriodExample.direction? == some .reverse", by native_decide⟩,
    ⟨"middlePeriodExample.direction? == none", by native_decide⟩,
    ⟨"forward and reverse validation period guards", by native_decide⟩], by native_decide⟩
  theorems := #[⟨"ShyftBench.catalog_ok_live", by native_decide⟩]
}

def pinnedShyftDesign : DesignUnit := {
  id := pinnedShyft.id
  interfaces := ⟨#[⟨"ShyftBuild", by native_decide⟩, ⟨"shyftPin", by native_decide⟩], by native_decide⟩
  tests := ⟨#[⟨"ptfsm2kSnow.runsOn shyftPin", by native_decide⟩], by native_decide⟩
  theorems := #[⟨"ShyftBench.ptfsm2kSnow_launches_on_pin", by native_decide⟩]
}

def launchPreconditionDesign : DesignUnit := {
  id := launchPrecondition.id
  interfaces := ⟨#[⟨"decideLaunch", by native_decide⟩, ⟨"LaunchDecision", by native_decide⟩], by native_decide⟩
  tests := ⟨#[⟨"decideLaunch shyftLocalMaster rpmfsm2kSnow ptfsm2kSnow", by native_decide⟩], by native_decide⟩
  theorems := #[⟨"ShyftBench.decideLaunch_runsOn", by native_decide⟩]
}

def launchFallbackDesign : DesignUnit := {
  id := launchFallback.id
  interfaces := ⟨#[⟨"FallbackChoice", by native_decide⟩, ⟨"decideLaunch", by native_decide⟩], by native_decide⟩
  tests := ⟨#[⟨"founder-selected fallback launches only when available", by native_decide⟩], by native_decide⟩
  theorems := #[⟨"ShyftBench.decideLaunch_fallbackPolicy", by native_decide⟩]
}

def resultFilingDesign : DesignUnit := {
  id := resultFiling.id
  interfaces := ⟨#[⟨"ResultKey", by native_decide⟩, ⟨"Experiment.accepts", by native_decide⟩], by native_decide⟩
  tests := ⟨#[⟨"rpmfsm2kSnow rejects a PTFSM2K result", by native_decide⟩,
    ⟨"rpmfsm2kSnow rejects an empty Shyft commit", by native_decide⟩], by native_decide⟩
  theorems := #[⟨"ShyftBench.rpmfsm2kSnow_rejects_other_models", by native_decide⟩]
}

def matchedComparisonDesign : DesignUnit := {
  id := matchedComparison.id
  interfaces := ⟨#[⟨"Experiment.comparableWith", by native_decide⟩,
    ⟨"Experiment.matchedCohort", by native_decide⟩], by native_decide⟩
  tests := ⟨#[⟨"Experiment.comparableWith .direction forwardPeriodExample reversePeriodExample", by native_decide⟩,
    ⟨"Experiment.comparableWith rejects another forcing", by native_decide⟩,
    ⟨"Experiment.comparableWith rejects overlapping and reordered list axes", by native_decide⟩,
    ⟨"Experiment.comparableWith treats unchosen list order as irrelevant", by native_decide⟩],
    by native_decide⟩
  theorems := #[⟨"ShyftBench.Experiment.comparison_evidence", by native_decide⟩]
}

def smokeDesign : DesignUnit := {
  id := smokeTier.id
  interfaces := ⟨#[⟨"smokeExperiment", by native_decide⟩, ⟨"smokeStation", by native_decide⟩], by native_decide⟩
  tests := ⟨#[⟨"smokeExperiment.wellFormed", by native_decide⟩], by native_decide⟩
  theorems := #[⟨"ShyftBench.smoke_ok", by native_decide⟩]
}

def exportDesign : DesignUnit := {
  id := exportData.id
  interfaces := ⟨#[⟨"FigureSpec", by native_decide⟩, ⟨"figureGrid", by native_decide⟩,
    ⟨"gridMatches", by native_decide⟩], by native_decide⟩
  tests := ⟨#[⟨"gridMatches rejects a missing figure", by native_decide⟩], by native_decide⟩
  theorems := #[⟨"ShyftBench.figureGrid_ok", by native_decide⟩]
}

def dashboardDesign : DesignUnit := {
  id := dashboard.id
  interfaces := ⟨#[⟨"Experiment.comparableWith", by native_decide⟩], by native_decide⟩
  tests := ⟨#[⟨"Experiment.comparableWith rejects another forcing", by native_decide⟩], by native_decide⟩
  theorems := #[⟨"ShyftBench.Experiment.comparableWith_same_forcing", by native_decide⟩]
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
  canonicalMetrics, exportData, dashboard, smokeTier, sigma2Safety, codeDivergence,
  documentation, independentAudit]

def allDesigns : Array DesignUnit := #[
  catalogueDesign, pinnedShyftDesign, launchPreconditionDesign, launchFallbackDesign,
  resultFilingDesign, matchedComparisonDesign, snowCohortDesign, smokeDesign, exportDesign,
  dashboardDesign]

def specSnapshot : SpecSnapshot := {
  requirements := allRequirements
  uniqueIds := by native_decide
  designs := allDesigns
}

end ShyftBench
