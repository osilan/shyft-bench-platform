import ShyftBench.Domain
import ShyftBench.Catchments

/-!
# Experiments, Shyft versions, launch decisions, result filing

An experiment is a typed value: stacks x forcing x goals x catchments x periods x pcorr.
Before launch, the pod's Shyft build is checked for every stack the experiment names
(decision D-002). Results are filed only under an experiment whose stacks, goals and
catchments contain them, so a PTFSM2K result can never be filed as RPMFSM2K.
-/

namespace ShyftBench

/-- A Shyft build: the commit it was built from and the stacks it provides. -/
structure ShyftBuild where
  commit : String
  stacks : List Stack
  deriving Repr, BEq

def ShyftBuild.provides (b : ShyftBuild) (s : Stack) : Bool := b.stacks.contains s

/-- Earliest `origin/master` commit known to provide `r_pm_fsm2_k` with Python bindings
and DRMS service support (checked 2026-10-01 in the local shyft clone, last fetch 2026-09-04). -/
def shyftPin : ShyftBuild := { commit := "bfbdbe63c", stacks := Stack.all }

/-- Local `master` (8c038f006, 2026-04-06): has `pt_fsm2_k` but not `r_pm_fsm2_k`. Kept as a
fixture: answering from this checkout is how the stack was first reported missing. -/
def shyftLocalMaster : ShyftBuild :=
  { commit := "8c038f006", stacks := [.ptgsk, .ptstk, .ptsthbv, .rpmgsk, .rpmstk, .ptfsm2k] }

structure Experiment where
  id : String
  models : List Model
  forcing : Forcing
  goals : List Goal
  optimizer : Optimizer := .bobyqa
  catchments : List StationId
  calibration : Period
  simulation : Period
  /-- Precipitation-correction variants: `false` = `_bc`, `true` = `_bc_pcorr`. -/
  pcorr : List Bool
  seeds : List Seed := []
  deriving Repr, BEq

structure DayInterval where
  startDay : Int
  endDay : Int
  deriving Repr, DecidableEq, Inhabited

def DayInterval.days (p : DayInterval) : Nat := (p.endDay - p.startDay).toNat
def minimumValidationDays : Nat := 365

/-- Direction is derived from which simulation boundary contains calibration. -/
def Experiment.direction? (e : Experiment) : Option Direction :=
  if e.calibration.startDay == e.simulation.startDay &&
      e.calibration.endDay < e.simulation.endDay then some .forward
  else if e.calibration.startDay > e.simulation.startDay &&
      e.calibration.startDay < e.simulation.endDay &&
      e.calibration.endDay ≤ e.simulation.endDay &&
      (e.simulation.endDay - e.calibration.endDay).toNat ≤ minimumValidationDays then
    some .reverse
  else none

/-- Validation is the simulation interval minus calibration; it may have two segments if the
calibration does not exactly touch a simulation boundary. Segments shorter than one year are
dropped. -/
def Experiment.validationPeriods? (e : Experiment) : Option (List DayInterval) :=
  let keepLongEnough (periods : List DayInterval) :=
    periods.filter fun period => decide (minimumValidationDays ≤ period.days)
  if e.calibration.startDay == e.simulation.startDay &&
      e.calibration.endDay < e.simulation.endDay then
    some (keepLongEnough [⟨e.calibration.endDay, e.simulation.endDay⟩])
  else if e.calibration.startDay > e.simulation.startDay &&
      e.calibration.startDay < e.simulation.endDay &&
      e.calibration.endDay ≤ e.simulation.endDay then
    some (keepLongEnough ([⟨e.simulation.startDay, e.calibration.startDay⟩] ++
      (if e.calibration.endDay < e.simulation.endDay then
        [⟨e.calibration.endDay, e.simulation.endDay⟩] else [])))
  else none

/-- Well-formed: a directional calibration/validation split exists and forcing covers both periods. -/
def Experiment.wellFormed (e : Experiment) : Bool :=
  !e.models.isEmpty && !e.goals.isEmpty && !e.catchments.isEmpty && !e.pcorr.isEmpty &&
    e.forcing.covers e.calibration && e.forcing.covers e.simulation &&
    e.direction?.isSome &&
    (match e.validationPeriods? with
     | some periods => !periods.isEmpty
     | none => false) &&
    e.seeds.eraseDups.length == e.seeds.length

/-- Number of runs across model, goal, catchment, pcorr and seed variants. -/
def Experiment.runCount (e : Experiment) : Nat :=
  e.models.length * e.goals.length * e.catchments.length * e.pcorr.length *
    (if e.seeds.isEmpty then 1 else e.seeds.length)

/-- Expand pcorr and seed combinations into single-axis variants. An empty seed list represents
one unseeded variant. -/
def Experiment.variants (e : Experiment) : List Experiment :=
  e.pcorr.flatMap fun pcorr =>
    if e.seeds.isEmpty then
      [{ e with pcorr := [pcorr] }]
    else
      e.seeds.map fun seed => { e with pcorr := [pcorr], seeds := [seed] }

/-- Every Shyft model is in the build; the external LSTM model is not gated on Shyft. -/
def Experiment.runsOn (e : Experiment) (b : ShyftBuild) : Bool :=
  e.models.all fun
    | .shyft stack => b.provides stack
    | .lstm => true

/-- Periods of the existing benchmark (`experiment_config.py` TimeConfig): calibration
1979-09-01 to 2001-01-01, simulation 1979-09-01 to 2021-01-01, daily. -/
def benchCalibration : Period := ⟨⟨1979, 9, 1⟩, 7793⟩
def benchSimulation : Period := ⟨⟨1979, 9, 1⟩, 15098⟩
def legacyReverseCalibration : Period := ⟨⟨1999, 9, 1⟩, 7792⟩

-- The day counts in the old config land exactly on the documented end dates.
#guard benchCalibration.endDay == (⟨2001, 1, 1⟩ : Date).toDays
#guard benchSimulation.endDay == (⟨2021, 1, 1⟩ : Date).toDays

/-- The same design with other models, under a new id. -/
def Experiment.withModels (e : Experiment) (id : String) (models : List Model) : Experiment :=
  { e with id, models }

/-! ## Launch decision (D-002, D-016) -/

inductive FallbackChoice where
  | runFallback
  | requestImage
  deriving Repr, DecidableEq

inductive LaunchDecision where
  | launch (e : Experiment)
  | launchFallback (planned fallback : Experiment)
  | requestImage (planned : Experiment) (minCommit : String)
  deriving Repr, BEq

/-- Launch the plan if available. Otherwise run only the explicitly selected, runnable fallback,
or request an image. Fallback results retain their own experiment identity. -/
def decideLaunch (pod : ShyftBuild) (planned fallback : Experiment) (choice : FallbackChoice) :
    LaunchDecision :=
  if planned.runsOn pod then .launch planned
  else match choice with
    | .runFallback => if fallback.runsOn pod then .launchFallback planned fallback
                      else .requestImage planned shyftPin.commit
    | .requestImage => .requestImage planned shyftPin.commit

/-- The experiment that would actually start, if any. -/
def LaunchDecision.started : LaunchDecision → Option Experiment
  | .launch e => some e
  | .launchFallback _ fallback => some fallback
  | .requestImage _ _ => none

/-- Nothing starts on a pod that lacks one of its stacks. -/
theorem decideLaunch_runsOn (pod : ShyftBuild) (planned fallback : Experiment)
    (choice : FallbackChoice) (e : Experiment)
    (h : (decideLaunch pod planned fallback choice).started = some e) : e.runsOn pod = true := by
  unfold decideLaunch at h
  split at h
  · simp [LaunchDecision.started] at h; subst h; assumption
  · cases choice with
    | runFallback =>
      simp only at h
      split at h
      · simp [LaunchDecision.started] at h; subst h; assumption
      · simp [LaunchDecision.started] at h
    | requestImage => simp [LaunchDecision.started] at h

/-- When the pod provides the planned stacks, the plan itself is launched. -/
theorem decideLaunch_planned (pod : ShyftBuild) (planned fallback : Experiment)
    (choice : FallbackChoice) (h : planned.runsOn pod = true) :
    decideLaunch pod planned fallback choice = .launch planned := by
  simp [decideLaunch, h]

/-- When the pod lacks a planned stack, no run starts and the request names the pinned commit. -/
theorem decideLaunch_requestImage (pod : ShyftBuild) (planned : Experiment)
    (fallback : Experiment) (h : planned.runsOn pod = false) :
    decideLaunch pod planned fallback .requestImage = .requestImage planned shyftPin.commit := by
  simp [decideLaunch, h]

theorem decideLaunch_launchFallback (pod : ShyftBuild) (planned fallback : Experiment)
    (hPlanned : planned.runsOn pod = false) (hFallback : fallback.runsOn pod = true) :
    decideLaunch pod planned fallback .runFallback = .launchFallback planned fallback := by
  simp [decideLaunch, hPlanned, hFallback]

theorem decideLaunch_fallbackPolicy (pod : ShyftBuild) (planned fallback : Experiment) :
    (planned.runsOn pod = false → fallback.runsOn pod = true →
      decideLaunch pod planned fallback .runFallback = .launchFallback planned fallback) ∧
    (planned.runsOn pod = false →
      decideLaunch pod planned fallback .requestImage = .requestImage planned shyftPin.commit) := by
  exact ⟨decideLaunch_launchFallback pod planned fallback,
    fun hPlanned => decideLaunch_requestImage pod planned fallback hPlanned⟩

/-! ## Result filing -/

/-- One calibrated-and-simulated series, as collected from the DTSS or a result file. -/
structure ResultKey where
  experimentId : String
  model : Model
  goal : Goal
  station : StationId
  pcorr : Bool
  optimizer : Optimizer
  direction : Direction
  seed : Option Seed
  shyftCommit : String
  deriving Repr, BEq

/-- A result is filed under `e` only if `e` planned exactly that run. -/
def Experiment.accepts (e : Experiment) (r : ResultKey) : Bool :=
  r.experimentId == e.id && e.models.contains r.model && e.goals.contains r.goal &&
    e.catchments.contains r.station && e.pcorr.contains r.pcorr && e.optimizer == r.optimizer &&
    e.direction? == some r.direction &&
    r.shyftCommit != "" &&
    (match r.seed with
     | none => e.seeds.isEmpty
     | some seed => e.seeds.contains seed)

theorem Experiment.accepts_model (e : Experiment) (r : ResultKey) (h : e.accepts r = true) :
    r.model ∈ e.models := by
  simp only [Experiment.accepts, Bool.and_eq_true, List.contains_iff_mem] at h
  exact h.1.1.1.1.1.1.1.2

/-! ## Matched comparisons -/

def Experiment.matchedCohort (a b : Experiment) : List StationId :=
  a.catchments.filter b.catchments.contains

def sameMembers [BEq α] (a b : List α) : Bool :=
  a.all b.contains && b.all a.contains

def differsByOne [BEq α] : List α → List α → Bool
  | [left], [right] => left != right
  | _, _ => false

def Experiment.sameOnUnchosenAxes (axis : ComparisonAxis) (a b : Experiment) : Bool :=
  let periodsMatch := a.calibration == b.calibration && a.simulation == b.simulation
  match axis with
  | .model => periodsMatch && sameMembers a.goals b.goals && a.direction? == b.direction? &&
      sameMembers a.pcorr b.pcorr && a.optimizer == b.optimizer && sameMembers a.seeds b.seeds
  | .goal => periodsMatch && sameMembers a.models b.models && a.direction? == b.direction? &&
      sameMembers a.pcorr b.pcorr && a.optimizer == b.optimizer && sameMembers a.seeds b.seeds
  | .direction => a.simulation == b.simulation && sameMembers a.models b.models &&
      sameMembers a.goals b.goals && sameMembers a.pcorr b.pcorr && a.optimizer == b.optimizer &&
      sameMembers a.seeds b.seeds
  | .pcorr => periodsMatch && sameMembers a.models b.models && sameMembers a.goals b.goals &&
      a.direction? == b.direction? && a.optimizer == b.optimizer && sameMembers a.seeds b.seeds
  | .optimizer => periodsMatch && sameMembers a.models b.models && sameMembers a.goals b.goals &&
      a.direction? == b.direction? && sameMembers a.pcorr b.pcorr && sameMembers a.seeds b.seeds
  | .seed => periodsMatch && sameMembers a.models b.models && sameMembers a.goals b.goals &&
      a.direction? == b.direction? && sameMembers a.pcorr b.pcorr && a.optimizer == b.optimizer

def Experiment.differsOnAxis (axis : ComparisonAxis) (a b : Experiment) : Bool :=
  match axis with
  | .model => differsByOne a.models b.models
  | .goal => differsByOne a.goals b.goals
  | .direction => a.direction? != b.direction?
  | .pcorr => differsByOne a.pcorr b.pcorr
  | .optimizer => a.optimizer != b.optimizer
  | .seed => differsByOne a.seeds b.seeds

/-- Same-forcing experiments with common catchments may be compared along exactly the selected
axis; every unselected comparison dimension agrees. -/
def Experiment.comparableWith (axis : ComparisonAxis) (a b : Experiment) : Bool :=
  (decide (a.forcing = b.forcing)) &&
    (!(a.matchedCohort b).isEmpty &&
      (a.sameOnUnchosenAxes axis b && a.differsOnAxis axis b))

theorem Experiment.comparableWith_same_forcing (axis : ComparisonAxis) (a b : Experiment)
    (h : a.comparableWith axis b = true) : a.forcing = b.forcing := by
  simp only [Experiment.comparableWith, Bool.and_eq_true, decide_eq_true_eq] at h
  exact h.1

theorem Experiment.not_comparableWith_different_forcing (axis : ComparisonAxis)
    (a b : Experiment) (hForcing : a.forcing ≠ b.forcing) :
    a.comparableWith axis b = false := by
  simp [Experiment.comparableWith, hForcing]

theorem Experiment.comparableWith_same_on_unchosen_axes (axis : ComparisonAxis)
    (a b : Experiment) (h : a.comparableWith axis b = true) :
    a.sameOnUnchosenAxes axis b = true := by
  simp only [Experiment.comparableWith, Bool.and_eq_true] at h
  exact h.2.2.1

theorem Experiment.comparableWith_differs_on_chosen_axis (axis : ComparisonAxis)
    (a b : Experiment) (h : a.comparableWith axis b = true) :
    a.differsOnAxis axis b = true := by
  simp only [Experiment.comparableWith, Bool.and_eq_true] at h
  exact h.2.2.2

theorem Experiment.comparableWith_obeys_selected_axis (axis : ComparisonAxis)
    (a b : Experiment) (h : a.comparableWith axis b = true) :
    a.forcing = b.forcing ∧ a.sameOnUnchosenAxes axis b = true ∧
      a.differsOnAxis axis b = true := by
  exact ⟨Experiment.comparableWith_same_forcing axis a b h,
    Experiment.comparableWith_same_on_unchosen_axes axis a b h,
    Experiment.comparableWith_differs_on_chosen_axis axis a b h⟩

theorem Experiment.comparison_evidence (axis : ComparisonAxis) (a b : Experiment)
    (s : StationId) (hComparable : a.comparableWith axis b = true)
    (hMatched : s ∈ a.matchedCohort b) :
    s ∈ a.catchments ∧ s ∈ b.catchments ∧ a.forcing = b.forcing ∧
      a.sameOnUnchosenAxes axis b = true ∧ a.differsOnAxis axis b = true := by
  have hCohort : s ∈ a.catchments ∧ s ∈ b.catchments := by
    simp [Experiment.matchedCohort] at hMatched
    exact hMatched
  exact ⟨hCohort.1, hCohort.2,
    (Experiment.comparableWith_obeys_selected_axis axis a b hComparable).1,
    (Experiment.comparableWith_obeys_selected_axis axis a b hComparable).2.1,
    (Experiment.comparableWith_obeys_selected_axis axis a b hComparable).2.2⟩

theorem Experiment.matchedCohort_mem (a b : Experiment) (s : StationId)
    (h : s ∈ a.matchedCohort b) : s ∈ a.catchments ∧ s ∈ b.catchments := by
  simp [Experiment.matchedCohort] at h
  exact h

def forwardPeriodExample : Experiment where
  id := "forward-period-example"
  models := [.shyft .ptgsk]
  forcing := .seNorge2018
  goals := [.kge]
  catchments := ["109.29"]
  calibration := benchCalibration
  simulation := benchSimulation
  pcorr := [true]
  seeds := [.v00]

def shortForwardValidationExample : Experiment :=
  { forwardPeriodExample with
    simulation := ⟨benchCalibration.start, benchCalibration.days + 100⟩ }

def reversePeriodExample : Experiment :=
  { forwardPeriodExample with
    id := "reverse-period-example"
    calibration := legacyReverseCalibration }

def middlePeriodExample : Experiment :=
  { forwardPeriodExample with
    id := "middle-period-example"
    calibration := ⟨⟨1990, 1, 1⟩, 3652⟩ }

def validationSegmentExample (days : Nat) : Experiment :=
  { forwardPeriodExample with
    calibration := ⟨⟨2000, 1, 1⟩, 0⟩
    simulation := ⟨⟨2000, 1, 1⟩, days⟩ }

#guard forwardPeriodExample.direction? == some .forward
#guard shortForwardValidationExample.direction? == some .forward &&
  shortForwardValidationExample.validationPeriods? == some [] &&
  !shortForwardValidationExample.wellFormed
#guard reversePeriodExample.direction? == some .reverse
#guard middlePeriodExample.direction? == none
#guard (validationSegmentExample 364).validationPeriods? == some []
#guard ((validationSegmentExample 365).validationPeriods?).get!.map (·.days) == [365]
#guard ((validationSegmentExample 366).validationPeriods?).get!.map (·.days) == [366]
#guard forwardPeriodExample.validationPeriods? ==
  some [⟨benchCalibration.endDay, benchSimulation.endDay⟩]
#guard reversePeriodExample.validationPeriods? ==
  some [⟨benchSimulation.startDay, legacyReverseCalibration.startDay⟩]
#guard middlePeriodExample.validationPeriods? ==
  some [⟨benchSimulation.startDay, middlePeriodExample.calibration.startDay⟩,
    ⟨middlePeriodExample.calibration.endDay, benchSimulation.endDay⟩]
#guard (forwardPeriodExample.validationPeriods?).get!.head!.days ==
  benchSimulation.days - benchCalibration.days
#guard (reversePeriodExample.validationPeriods?).get!.head!.days ==
  (legacyReverseCalibration.startDay - benchSimulation.startDay).toNat
#guard (reversePeriodExample.validationPeriods?).get!.all fun period =>
  minimumValidationDays ≤ period.days

def optimizerExample : Experiment := { forwardPeriodExample with optimizer := .sceua }
def pcorrExample : Experiment := { forwardPeriodExample with pcorr := [false] }
def seedExample : Experiment := { forwardPeriodExample with seeds := [.v01] }
def modelExample : Experiment := { forwardPeriodExample with models := [.shyft .rpmstk] }
def goalExample : Experiment := { forwardPeriodExample with goals := [.nse] }
def otherForcingExample : Experiment := { modelExample with forcing := .aifs }
def overlappingModelLeft : Experiment :=
  { forwardPeriodExample with models := [.shyft .ptgsk, .shyft .rpmstk] }
def overlappingModelRight : Experiment :=
  { forwardPeriodExample with models := [.shyft .ptgsk, .shyft .ptfsm2k] }
def reorderedModel : Experiment :=
  { forwardPeriodExample with models := [.shyft .rpmstk, .shyft .ptgsk] }
def reorderedModelGoal : Experiment :=
  { reorderedModel with goals := [.nse] }
def overlappingGoalLeft : Experiment := { forwardPeriodExample with goals := [.kge, .nse] }
def overlappingGoalRight : Experiment := { forwardPeriodExample with goals := [.kge, .lnse] }
def overlappingPcorrLeft : Experiment := { forwardPeriodExample with pcorr := [true, false] }
def overlappingPcorrRight : Experiment := { forwardPeriodExample with pcorr := [true, true] }
def overlappingSeedLeft : Experiment := { forwardPeriodExample with seeds := [.v00, .v01] }
def overlappingSeedRight : Experiment := { forwardPeriodExample with seeds := [.v00, .v02] }
def pcorrSeedVariantsExample : Experiment :=
  { forwardPeriodExample with pcorr := [false, true], seeds := [.v00, .v01] }

#guard Experiment.comparableWith .direction forwardPeriodExample reversePeriodExample
#guard Experiment.comparableWith .optimizer forwardPeriodExample optimizerExample
#guard Experiment.comparableWith .pcorr forwardPeriodExample pcorrExample
#guard Experiment.comparableWith .seed forwardPeriodExample seedExample
#guard Experiment.comparableWith .model forwardPeriodExample modelExample
#guard Experiment.comparableWith .goal forwardPeriodExample goalExample
#guard pcorrSeedVariantsExample.variants.map (fun variant => (variant.pcorr, variant.seeds)) ==
  [([false], [.v00]), ([false], [.v01]), ([true], [.v00]), ([true], [.v01])]
#guard !Experiment.comparableWith .model overlappingModelLeft overlappingModelRight
#guard !Experiment.comparableWith .model overlappingModelLeft reorderedModel
#guard Experiment.comparableWith .goal overlappingModelLeft reorderedModelGoal
#guard !Experiment.comparableWith .goal overlappingGoalLeft overlappingGoalRight
#guard !Experiment.comparableWith .pcorr overlappingPcorrLeft overlappingPcorrRight
#guard !Experiment.comparableWith .seed overlappingSeedLeft overlappingSeedRight
#guard !Experiment.comparableWith .model forwardPeriodExample otherForcingExample

end ShyftBench
