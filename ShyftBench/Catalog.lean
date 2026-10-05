import ShyftBench.Experiment

/-!
# Experiment catalogue

Legacy experiments are read-only imports (Zenodo 10.5281/zenodo.15595323 and the
rpmstk reverse run); they are never re-run. New experiments are planned here first.
-/

namespace ShyftBench

/-- How a catalogue entry gets its results. -/
inductive Provenance where
  | zenodoImport (doi : String)  -- published archive, imported read-only
  | dtssCollect (where_ : String)  -- finished run still in the Sigma2 DTSS, collected once
  | planned                      -- to be launched by this platform
  deriving Repr, BEq

structure Entry where
  experiment : Experiment
  provenance : Provenance
  deriving Repr, BEq

def Entry.legacy (e : Entry) : Bool :=
  match e.provenance with
  | .planned => false
  | _ => true

/-- First new experiment (D-001, D-003): RPMFSM2K, seNorge2018, the 70 snow-dominated
stations. Goals, pcorr variants, optimiser and periods match the legacy benchmark so the
results are comparable with it. -/
def rpmfsm2kSnow : Experiment where
  id := "rpmfsm2k-senorge-snow"
  stacks := [.rpmfsm2k]
  forcing := .seNorge2018
  goals := Goal.all
  catchments := snowDominatedStations
  calibration := benchCalibration
  simulation := benchSimulation
  pcorr := [false, true]

/-- Fallback if the pod's Shyft lacks `r_pm_fsm2_k` (D-002). A separate experiment: its
results never count as RPMFSM2K. -/
def ptfsm2kSnow : Experiment := rpmfsm2kSnow.withStacks "ptfsm2k-senorge-snow" [.ptfsm2k]

/-- Legacy seNorge benchmark for one stack. Its catchment list is filled when the archive is
imported; until then it is empty and the entry is not comparable with anything. -/
def legacyBench (s : Stack) : Experiment where
  id := s!"legacy-{s.key}-senorge"
  stacks := [s]
  forcing := .seNorge2018
  goals := Goal.all
  catchments := []
  calibration := benchCalibration
  simulation := benchSimulation
  pcorr := [false, true]

def zenodoDoi : String := "10.5281/zenodo.15595323"

def catalog : List Entry :=
  [.ptgsk, .ptstk, .ptsthbv, .rpmgsk].map (fun s => ⟨legacyBench s, .zenodoImport zenodoDoi⟩) ++
  [⟨legacyBench .rpmstk, .zenodoImport zenodoDoi⟩,
   ⟨{ legacyBench .rpmstk with id := "legacy-rpmstk-reverse" },
     .dtssCollect "/shyft-var/dtss/db/se-bench-rev1"⟩,
   ⟨rpmfsm2kSnow, .planned⟩,
   ⟨ptfsm2kSnow, .planned⟩]

def Catalog.ids (c : List Entry) : List String := c.map (·.experiment.id)

/-! ## Catalogue invariants -/

/-- Unique ids, planned experiments well formed and runnable on the pinned Shyft. -/
def Catalog.ok (c : List Entry) : Bool :=
  (Catalog.ids c).eraseDups.length == c.length &&
    c.all fun e => e.legacy || (e.experiment.wellFormed && e.experiment.runsOn shyftPin)

/-- Liveness: at least one planned experiment with work to do, so an empty plan
cannot satisfy the specification. -/
def Catalog.live (c : List Entry) : Bool :=
  c.any fun e => !e.legacy && e.experiment.runCount > 0

#guard Catalog.ok catalog
#guard Catalog.live catalog
#guard rpmfsm2kSnow.wellFormed
#guard rpmfsm2kSnow.runCount == 1 * 10 * 70 * 2
#guard rpmfsm2kSnow.runsOn shyftPin
#guard !rpmfsm2kSnow.runsOn shyftLocalMaster
#guard ptfsm2kSnow.runsOn shyftLocalMaster
#guard rpmfsm2kSnow.comparableWith ptfsm2kSnow
#guard rpmfsm2kSnow.comparableWith (legacyBench .rpmstk)
-- On the April build the planned run cannot start; the fallback or an image request follows.
#guard decideLaunch shyftLocalMaster rpmfsm2kSnow ptfsm2kSnow .runFallback
  == .launchFallback rpmfsm2kSnow ptfsm2kSnow
#guard decideLaunch shyftLocalMaster rpmfsm2kSnow ptfsm2kSnow .requestImage
  == .requestImage rpmfsm2kSnow "bfbdbe63c"
#guard decideLaunch shyftPin rpmfsm2kSnow ptfsm2kSnow .runFallback == .launch rpmfsm2kSnow
-- A PTFSM2K result is never filed as RPMFSM2K, even under the RPMFSM2K id.
#guard !rpmfsm2kSnow.accepts
  { experimentId := rpmfsm2kSnow.id, stack := .ptfsm2k, goal := .kge, station := "109.29",
    pcorr := false, shyftCommit := "8c038f006" }
#guard rpmfsm2kSnow.accepts
  { experimentId := rpmfsm2kSnow.id, stack := .rpmfsm2k, goal := .kge, station := "109.29",
    pcorr := false, shyftCommit := "bfbdbe63c" }

/-- The planned experiment is launched on a build that provides its stack. -/
theorem rpmfsm2kSnow_launches_on_pin (fallback : Experiment) (choice : FallbackChoice) :
    decideLaunch shyftPin rpmfsm2kSnow fallback choice = .launch rpmfsm2kSnow :=
  decideLaunch_planned _ _ _ _ (by decide)

/-- The catalogue is consistent and plans at least one run (kernel-checked). -/
theorem catalog_ok_live : Catalog.ok catalog = true ∧ Catalog.live catalog = true := by
  decide

/-- No result from another stack is ever filed under the RPMFSM2K experiment. -/
theorem rpmfsm2kSnow_rejects_other_stacks (r : ResultKey) (h : r.stack ≠ .rpmfsm2k) :
    rpmfsm2kSnow.accepts r = false := by
  cases hr : rpmfsm2kSnow.accepts r
  · rfl
  · have := Experiment.accepts_stack _ _ hr
    simp [rpmfsm2kSnow] at this
    exact absurd this h

end ShyftBench
