/-!
# Domain vocabulary

Closed sets for everything an experiment names: Shyft model stacks, forcings,
goal functions, regimes, and calendar periods. A typo cannot inhabit these types.
-/

namespace ShyftBench

/-- Shyft hydrology model stacks used by the benchmark. -/
inductive Stack where
  | ptgsk     -- Priestley-Taylor + Gamma Snow + Kirchner
  | ptstk     -- Priestley-Taylor + Snow Tiles + Kirchner
  | ptsthbv   -- Priestley-Taylor + Snow Tiles + HBV
  | rpmgsk    -- Penman-Monteith + Gamma Snow + Kirchner
  | rpmstk    -- Penman-Monteith + Snow Tiles + Kirchner
  | ptfsm2k   -- Priestley-Taylor + FSM2 + Kirchner
  | rpmfsm2k  -- Penman-Monteith + FSM2 + Kirchner
  deriving Repr, DecidableEq

/-- Directory of the stack in the Shyft source: `cpp/shyft/hydrology/stacks/<dir>`. -/
def Stack.shyftDir : Stack → String
  | .ptgsk => "pt_gs_k"
  | .ptstk => "pt_st_k"
  | .ptsthbv => "pt_st_hbv"
  | .rpmgsk => "r_pm_gs_k"
  | .rpmstk => "r_pm_st_k"
  | .ptfsm2k => "pt_fsm2_k"
  | .rpmfsm2k => "r_pm_fsm2_k"

/-- Name used in result folders and DTSS paths (`rpmstk_bc`, `seNorge_rpmstk_...`). -/
def Stack.key : Stack → String
  | .ptgsk => "ptgsk"
  | .ptstk => "ptstk"
  | .ptsthbv => "ptsthbv"
  | .rpmgsk => "rpmgsk"
  | .rpmstk => "rpmstk"
  | .ptfsm2k => "ptfsm2k"
  | .rpmfsm2k => "rpmfsm2k"

/-- Canonical display order (`compare-models`): snow-tiles pair, gamma-snow pair, HBV, then
the FSM2 pair. The FSM2 placement is provisional: the canon predates FSM2. -/
def Stack.all : List Stack := [.ptstk, .rpmstk, .ptgsk, .rpmgsk, .ptsthbv, .ptfsm2k, .rpmfsm2k]

/-- Canonical colours (`compare-models`); FSM2 stacks have none yet. -/
def Stack.colour? : Stack → Option String
  | .ptstk => some "#4393c3" | .rpmstk => some "#2166ac" | .ptgsk => some "#f4a582"
  | .rpmgsk => some "#d6604d" | .ptsthbv => some "#762a83"
  | .ptfsm2k | .rpmfsm2k => none

/-- Meteorological forcing products loaded into the DTSS geo-database. -/
inductive Forcing where
  | seNorge2018  -- 1 km grid, 1958-2020
  | aifs         -- 0.25 degree reanalysis, 2010-2022
  deriving Repr, DecidableEq

def Forcing.key : Forcing → String
  | .seNorge2018 => "seNorge"
  | .aifs => "aifs"

/-- Calibration goal functions; combined goals weight two criteria. -/
inductive Goal where
  | kge | lkge | bckge | nse | lnse | bcnse
  | kgeLkge | kgeBckge | nseLnse | nseBcnse
  deriving Repr, DecidableEq

/-- Name used in result files: `..._discharge_sim-<key>_bobyqa.csv`. -/
def Goal.key : Goal → String
  | .kge => "kge" | .lkge => "lkge" | .bckge => "bckge"
  | .nse => "nse" | .lnse => "lnse" | .bcnse => "bcnse"
  | .kgeLkge => "kge_lkge" | .kgeBckge => "kge_bckge"
  | .nseLnse => "nse_lnse" | .nseBcnse => "nse_bcnse"

/-- Canonical order: KGE family (simple, then composite), then NSE family. -/
def Goal.all : List Goal :=
  [.kge, .lkge, .bckge, .kgeLkge, .kgeBckge, .nse, .lnse, .bcnse, .nseLnse, .nseBcnse]

/-- Calibration optimiser. Only BOBYQA is used so far. -/
inductive Optimizer where
  | bobyqa
  deriving Repr, DecidableEq

/-- Hydrological regime classes from `calc_hydrological_regime.r`, by the months of
the two lowest and three highest mean monthly discharges (1961-2019). -/
inductive Regime where
  | transition  -- code 0: matches no class
  | mountain    -- code 1
  | inland      -- code 2
  | atlantic    -- code 3
  | baltic      -- code 4
  deriving Repr, DecidableEq

def Regime.ofCode? : Nat → Option Regime
  | 0 => some .transition
  | 1 => some .mountain
  | 2 => some .inland
  | 3 => some .atlantic
  | 4 => some .baltic
  | _ => none

def Regime.code : Regime → Nat
  | .transition => 0 | .mountain => 1 | .inland => 2 | .atlantic => 3 | .baltic => 4

/-- Codes are the R script's, everywhere. The old repo also had a 0 = mountain numbering
(`lstm_baseline/scripts/config.py`, `compare-models`); names, not numbers, cross module borders. -/
def Regime.name : Regime → String
  | .mountain => "Mountain" | .inland => "Inland" | .atlantic => "Atlantic"
  | .baltic => "Baltic" | .transition => "Transition"

/-- Canonical display order and colours (`compare-models`, keyed by name). -/
def Regime.all : List Regime := [.mountain, .inland, .atlantic, .baltic, .transition]

def Regime.colour : Regime → String
  | .mountain => "#2166ac" | .inland => "#92c5de" | .atlantic => "#d6604d"
  | .baltic => "#f4a582" | .transition => "#4dac26"

theorem Regime.ofCode_code (r : Regime) : Regime.ofCode? r.code = some r := by
  cases r <;> rfl

/-- Snow-dominated regimes: the subset for the FSM2 experiments. -/
def Regime.snowDominated : Regime → Bool
  | .mountain | .inland => true
  | _ => false

/-! ## Calendar -/

/-- A calendar date (proleptic Gregorian). -/
structure Date where
  year : Int
  month : Nat
  day : Nat
  deriving Repr, DecidableEq

/-- Days since 1970-01-01 (H. Hinnant's `days_from_civil`). -/
def Date.toDays (d : Date) : Int :=
  let y : Int := if d.month ≤ 2 then d.year - 1 else d.year
  let era : Int := (if y ≥ 0 then y else y - 399) / 400
  let yoe : Int := y - era * 400
  let m : Int := d.month
  let mp : Int := if m > 2 then m - 3 else m + 9
  let doy : Int := (153 * mp + 2) / 5 + d.day - 1
  let doe : Int := yoe * 365 + yoe / 4 - yoe / 100 + doy
  era * 146097 + doe - 719468

/-- A daily time axis: `start` plus `days` steps; the end is exclusive. -/
structure Period where
  start : Date
  days : Nat
  deriving Repr, DecidableEq

def Period.startDay (p : Period) : Int := p.start.toDays
def Period.endDay (p : Period) : Int := p.start.toDays + p.days

/-- `p` lies inside the closed date range `[first, last]`. -/
def Period.within (p : Period) (first last : Date) : Bool :=
  decide (first.toDays ≤ p.startDay) && decide (p.endDay ≤ last.toDays + 1)

/-- Dates covered by each forcing product (first and last day). -/
def Forcing.coverage : Forcing → Date × Date
  | .seNorge2018 => (⟨1958, 1, 1⟩, ⟨2020, 12, 31⟩)
  | .aifs => (⟨2010, 1, 1⟩, ⟨2022, 12, 31⟩)

def Forcing.covers (f : Forcing) (p : Period) : Bool :=
  p.within f.coverage.1 f.coverage.2

#guard (⟨1970, 1, 1⟩ : Date).toDays == 0
#guard (⟨2000, 3, 1⟩ : Date).toDays == 11017
#guard Stack.all.length == 7
#guard Goal.all.length == 10
#guard Goal.all.eraseDups.length == 10
#guard Stack.all.eraseDups.length == 7
#guard Regime.ofCode? 1 == some .mountain && Regime.ofCode? 0 == some .transition
#guard Regime.all.map (·.code) == [1, 2, 3, 4, 0]

end ShyftBench
