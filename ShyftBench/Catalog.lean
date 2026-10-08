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
  | planned                      -- active experiment to be launched by this platform
  | future                       -- catalogued, but not yet eligible to launch
  deriving Repr, BEq

structure Entry where
  experiment : Experiment
  provenance : Provenance
  deriving Repr, BEq

def Entry.legacy (e : Entry) : Bool :=
  match e.provenance with
  | .planned | .future => false
  | _ => true

/-- Future experiment (D-001 superseded for the active plan): RPMFSM2K, seNorge2018, and the
70 snow-dominated stations. It is not eligible to launch until the pod provides its stack. -/
def rpmfsm2kSnow : Experiment where
  id := "rpmfsm2k-senorge-snow"
  models := [.shyft .rpmfsm2k]
  forcing := .seNorge2018
  goals := Goal.all
  catchments := snowDominatedStations
  calibration := benchCalibration
  simulation := benchSimulation
  pcorr := [false, true]

/-- Active FSM2 experiment (D-016); results remain distinct from RPMFSM2K. -/
def ptfsm2kSnow : Experiment := rpmfsm2kSnow.withModels "ptfsm2k-senorge-snow" [.shyft .ptfsm2k]

/-- Legacy seNorge benchmark for one stack. Its catchment list is filled when the archive is
imported; until then it is empty and the entry is not comparable with anything. -/
def legacyBench (s : Stack) : Experiment where
  id := s!"legacy-{s.key}-senorge"
  models := [.shyft s]
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
     .dtssCollect "/shyft-var/dtss/db/se-bench"⟩,
   ⟨rpmfsm2kSnow, .future⟩,
   ⟨ptfsm2kSnow, .planned⟩]

/-- D-022: drawn once with Python `random.Random(smokeSeed).choice` over the mountain stations
of the frozen regime table in CSV order (index 18 of 43). Fixed here so the CI reference is
deterministic. -/
def smokeSeed : Nat := 20261008
def smokeStation : StationId := "122.14"

/-- CI smoke calibration: one PTFSM2K KGE run, pcorr on, on the drawn mountain station. -/
def smokeExperiment : Experiment :=
  { ptfsm2kSnow with
    id := "ptfsm2k-smoke"
    goals := [.kge]
    catchments := [smokeStation]
    pcorr := [true] }

def Catalog.ids (c : List Entry) : List String := c.map (·.experiment.id)

def Catalog.planned (c : List Entry) : List Entry :=
  c.filter fun e => e.provenance == .planned

/-! ## Catalogue invariants -/

/-- Unique ids, planned experiments well formed and runnable on the pinned Shyft. -/
def Catalog.ok (c : List Entry) : Bool :=
  (Catalog.ids c).eraseDups.length == c.length &&
    c.all fun e => e.legacy || (e.experiment.wellFormed && e.experiment.runsOn shyftPin)

/-- Liveness: at least one planned experiment with work to do, so an empty plan
cannot satisfy the specification. -/
def Catalog.live (c : List Entry) : Bool :=
  c.any fun e => e.provenance == .planned && e.experiment.runCount > 0

#guard Catalog.ok catalog
#guard Catalog.live catalog
#guard Catalog.planned catalog == [⟨ptfsm2kSnow, .planned⟩]
#guard (stationsIn .mountain)[18]? == some smokeStation
#guard smokeExperiment.wellFormed
#guard smokeExperiment.runCount == 1
#guard smokeExperiment.runsOn shyftPin
#guard rpmfsm2kSnow.wellFormed
#guard rpmfsm2kSnow.runCount == 1 * 10 * 70 * 2
#guard rpmfsm2kSnow.runsOn shyftPin
#guard !rpmfsm2kSnow.runsOn shyftLocalMaster
#guard ptfsm2kSnow.runsOn shyftLocalMaster
#guard rpmfsm2kSnow.comparableWith .model ptfsm2kSnow
#guard decideLaunch shyftLocalMaster rpmfsm2kSnow ptfsm2kSnow .runFallback
  == .launchFallback rpmfsm2kSnow ptfsm2kSnow
#guard decideLaunch shyftLocalMaster rpmfsm2kSnow ptfsm2kSnow .requestImage
  == .requestImage rpmfsm2kSnow "bfbdbe63c"
#guard decideLaunch shyftLocalMaster ptfsm2kSnow rpmfsm2kSnow .runFallback == .launch ptfsm2kSnow
#guard decideLaunch shyftPin ptfsm2kSnow rpmfsm2kSnow .requestImage == .launch ptfsm2kSnow
-- A PTFSM2K result is never filed as RPMFSM2K, even under the RPMFSM2K id.
#guard !rpmfsm2kSnow.accepts
  { experimentId := rpmfsm2kSnow.id, model := .shyft .ptfsm2k, goal := .kge,
    station := "109.29", pcorr := false, optimizer := .bobyqa, direction := .forward,
    seed := none, shyftCommit := "8c038f006" }
#guard rpmfsm2kSnow.accepts
  { experimentId := rpmfsm2kSnow.id, model := .shyft .rpmfsm2k, goal := .kge,
    station := "109.29", pcorr := false, optimizer := .bobyqa, direction := .forward,
    seed := none, shyftCommit := "bfbdbe63c" }

/-- The active PTFSM2K experiment is launched on a build that provides its stack. -/
theorem ptfsm2kSnow_launches_on_pin (fallback : Experiment) (choice : FallbackChoice) :
    decideLaunch shyftPin ptfsm2kSnow fallback choice = .launch ptfsm2kSnow :=
  decideLaunch_planned _ _ _ _ (by decide)

/-- The smoke experiment is one PTFSM2K KGE calibration with pcorr on, on a mountain station. -/
theorem smoke_ok :
    smokeStation ∈ stationsIn .mountain ∧ smokeExperiment.models = [.shyft .ptfsm2k] ∧
      smokeExperiment.goals = [.kge] ∧ smokeExperiment.pcorr = [true] ∧
      smokeExperiment.catchments = [smokeStation] :=
  ⟨by decide, rfl, rfl, rfl, rfl⟩

/-- The catalogue is consistent and plans at least one run (kernel-checked). -/
theorem catalog_ok_live : Catalog.ok catalog = true ∧ Catalog.live catalog = true := by
  decide

/-- No result from another model is ever filed under the RPMFSM2K experiment. -/
theorem rpmfsm2kSnow_rejects_other_models (r : ResultKey)
    (h : r.model ≠ .shyft .rpmfsm2k) :
    rpmfsm2kSnow.accepts r = false := by
  cases hr : rpmfsm2kSnow.accepts r
  · rfl
  · have := Experiment.accepts_model _ _ hr
    simp [rpmfsm2kSnow] at this
    exact absurd this h

end ShyftBench
