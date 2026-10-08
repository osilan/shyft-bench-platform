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
  stacks : List Stack
  forcing : Forcing
  goals : List Goal
  optimizer : Optimizer := .bobyqa
  catchments : List StationId
  calibration : Period
  simulation : Period
  /-- Precipitation-correction variants: `false` = `_bc`, `true` = `_bc_pcorr`. -/
  pcorr : List Bool
  deriving Repr, BEq

/-- Well-formed: something to run, and the forcing covers both periods. -/
def Experiment.wellFormed (e : Experiment) : Bool :=
  !e.stacks.isEmpty && !e.goals.isEmpty && !e.catchments.isEmpty && !e.pcorr.isEmpty &&
    e.forcing.covers e.calibration && e.forcing.covers e.simulation &&
    e.calibration.start == e.simulation.start && e.calibration.days ≤ e.simulation.days

/-- Number of calibrations: one per stack, goal, catchment and pcorr variant. -/
def Experiment.runCount (e : Experiment) : Nat :=
  e.stacks.length * e.goals.length * e.catchments.length * e.pcorr.length

/-- Every stack the experiment names is in the build. -/
def Experiment.runsOn (e : Experiment) (b : ShyftBuild) : Bool :=
  e.stacks.all b.provides

/-- Periods of the existing benchmark (`experiment_config.py` TimeConfig): calibration
1979-09-01 to 2001-01-01, simulation 1979-09-01 to 2021-01-01, daily. -/
def benchCalibration : Period := ⟨⟨1979, 9, 1⟩, 7793⟩
def benchSimulation : Period := ⟨⟨1979, 9, 1⟩, 15098⟩

-- The day counts in the old config land exactly on the documented end dates.
#guard benchCalibration.endDay == (⟨2001, 1, 1⟩ : Date).toDays
#guard benchSimulation.endDay == (⟨2021, 1, 1⟩ : Date).toDays

/-- The same design with other stacks, under a new id. -/
def Experiment.withStacks (e : Experiment) (id : String) (stacks : List Stack) : Experiment :=
  { e with id, stacks }

/-! ## Launch decision (D-002, D-016) -/

inductive LaunchDecision where
  | launch (e : Experiment)
  | requestImage (planned : Experiment) (minCommit : String)
  deriving Repr, BEq

/-- Launch the plan when the pod provides its stacks. Otherwise request an image; never
substitute a different experiment or stack. -/
def decideLaunch (pod : ShyftBuild) (planned : Experiment) : LaunchDecision :=
  if planned.runsOn pod then .launch planned else .requestImage planned shyftPin.commit

/-- The experiment that would actually start, if any. -/
def LaunchDecision.started : LaunchDecision → Option Experiment
  | .launch e => some e
  | .requestImage _ _ => none

/-- Nothing starts on a pod that lacks one of its stacks. -/
theorem decideLaunch_runsOn (pod : ShyftBuild) (planned : Experiment) (e : Experiment)
    (h : (decideLaunch pod planned).started = some e) : e.runsOn pod = true := by
  unfold decideLaunch at h
  split at h
  · simp [LaunchDecision.started] at h; subst h; assumption
  · simp [LaunchDecision.started] at h

/-- When the pod provides the planned stacks, the plan itself is launched. -/
theorem decideLaunch_planned (pod : ShyftBuild) (planned : Experiment)
    (h : planned.runsOn pod = true) :
    decideLaunch pod planned = .launch planned := by
  simp [decideLaunch, h]

/-- When the pod lacks a planned stack, no run starts and the request names the pinned commit. -/
theorem decideLaunch_requestImage (pod : ShyftBuild) (planned : Experiment)
    (h : planned.runsOn pod = false) :
    decideLaunch pod planned = .requestImage planned shyftPin.commit := by
  simp [decideLaunch, h]

/-! ## Result filing -/

/-- One calibrated-and-simulated series, as collected from the DTSS or a result file. -/
structure ResultKey where
  experimentId : String
  stack : Stack
  goal : Goal
  station : StationId
  pcorr : Bool
  shyftCommit : String
  deriving Repr, BEq

/-- A result is filed under `e` only if `e` planned exactly that run. -/
def Experiment.accepts (e : Experiment) (r : ResultKey) : Bool :=
  r.experimentId == e.id && e.stacks.contains r.stack && e.goals.contains r.goal &&
    e.catchments.contains r.station && e.pcorr.contains r.pcorr

theorem Experiment.accepts_stack (e : Experiment) (r : ResultKey) (h : e.accepts r = true) :
    r.stack ∈ e.stacks := by
  simp only [Experiment.accepts, Bool.and_eq_true, List.contains_iff_mem] at h
  exact h.1.1.1.2

/-! ## Matched comparisons -/

/-- Two experiments are comparable when they share forcing, periods, optimiser, goals and
pcorr variants; only their common catchments are compared. -/
def Experiment.comparableWith (a b : Experiment) : Bool :=
  a.forcing == b.forcing && a.calibration == b.calibration && a.simulation == b.simulation &&
    a.optimizer == b.optimizer && a.goals == b.goals && a.pcorr == b.pcorr

def Experiment.matchedCohort (a b : Experiment) : List StationId :=
  a.catchments.filter b.catchments.contains

theorem Experiment.matchedCohort_mem (a b : Experiment) (s : StationId)
    (h : s ∈ a.matchedCohort b) : s ∈ a.catchments ∧ s ∈ b.catchments := by
  simp [Experiment.matchedCohort] at h
  exact h

end ShyftBench
