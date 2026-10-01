import ShyftBench.Domain
import ShyftBench.Generated.Regime

/-!
# Catchment sets

The regime table is the frozen output of `calc_hydrological_regime.r` (109 stations).
Decision D-003: the FSM2 subset is its mountain and inland stations as they are now;
the classification is not extended to other catchments.
-/

namespace ShyftBench

/-- A gauged catchment, by NVE station id (`regine.number`, e.g. `"109.29"`). -/
abbrev StationId := String

/-- Stations with a valid regime code, in CSV order. -/
def regimeTable : List (StationId × Regime) :=
  Generated.regimeRows.filterMap fun (sid, code) => (Regime.ofCode? code).map (sid, ·)

def stationsIn (r : Regime) : List StationId :=
  regimeTable.filterMap fun (sid, r') => if r' == r then some sid else none

/-- The FSM2 subset: snow-dominated (mountain + inland) stations. -/
def snowDominatedStations : List StationId :=
  regimeTable.filterMap fun (sid, r) => if r.snowDominated then some sid else none

-- Every CSV row has a valid code and a distinct station id.
#guard regimeTable.length == Generated.regimeRows.length
#guard regimeTable.length == 109
#guard (regimeTable.map (·.1)).eraseDups.length == 109
-- Counts per regime, as read from the CSV on 2026-10-01.
#guard (stationsIn .mountain).length == 43
#guard (stationsIn .inland).length == 27
#guard (stationsIn .atlantic).length == 16
#guard (stationsIn .baltic).length == 11
#guard (stationsIn .transition).length == 12
#guard snowDominatedStations.length == 70
#guard snowDominatedStations.all fun s => (stationsIn .mountain).contains s || (stationsIn .inland).contains s
-- Pinned inputs: changing the CSV or the R script must be a visible decision.
#guard Generated.regimeCsvSha256 == "5a418b8b7185adc5c066484c36a9b951a8bd9d55fb4c90ba92862a9ca1975a24"
#guard Generated.regimeScriptSha256 == "33f0ddc0a9e38d1663bec5c84a724cb9cd60ff571e43d3b00d27bb0f0eb2799b"

/-- The FSM2 cohort, as a kernel-checked statement over the frozen table. -/
theorem snowCohort_counts :
    snowDominatedStations.length = 70 ∧ (stationsIn .mountain).length = 43 ∧
      (stationsIn .inland).length = 27 ∧ snowDominatedStations.eraseDups.length = 70 := by
  decide

end ShyftBench
