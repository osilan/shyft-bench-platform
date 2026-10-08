import ShyftBench.Catalog

/-!
# Figure grid (D-017, D-020)

The site publishes pre-rendered figures, each with a data table. The grid of figures is declared
here as an explicit list; the export check fails if a declared figure is missing or an undeclared
one appears. A figure has exactly one forcing, so no figure compares across forcings.
-/

namespace ShyftBench

inductive FigureView where
  | scoreboard | cdf | modelPair | validationDrop | pcorrEffect | kgeCompass | ruzzante
  | lowFlow | directionCompare | lstmVsShyft | seedSpread | map | catchmentDetail
  deriving Repr, DecidableEq

def FigureView.key : FigureView → String
  | .scoreboard => "scoreboard" | .cdf => "cdf" | .modelPair => "model-pair"
  | .validationDrop => "validation-drop" | .pcorrEffect => "pcorr-effect"
  | .kgeCompass => "kge-compass" | .ruzzante => "ruzzante" | .lowFlow => "low-flow"
  | .directionCompare => "direction-compare" | .lstmVsShyft => "lstm-vs-shyft"
  | .seedSpread => "seed-spread" | .map => "map" | .catchmentDetail => "catchment-detail"

/-- One published figure. `none` marks an axis the view compares across (or that the experiment
fixes itself) instead of selecting one value. -/
structure FigureSpec where
  view : FigureView
  forcing : Forcing
  direction : Option Direction
  pcorr : Option Bool
  optimizer : Optimizer := .bobyqa
  station : Option StationId := none
  deriving Repr, DecidableEq

def Optimizer.key : Optimizer → String
  | .bobyqa => "bobyqa" | .sceua => "sceua"

def FigureSpec.id (f : FigureSpec) : String :=
  let part (name : String) : Option String → String
    | some v => s!"-{name}-{v}"
    | none => ""
  s!"{f.view.key}-{f.forcing.key}" ++ part "dir" (f.direction.map Direction.key) ++
    part "pcorr" (f.pcorr.map fun p => if p then "on" else "off") ++
    s!"-{f.optimizer.key}" ++ part "station" f.station

private def fig (view : FigureView) (forcing : Forcing) (direction : Option Direction)
    (pcorr : Option Bool) (optimizer : Optimizer := .bobyqa) : FigureSpec :=
  { view, forcing, direction, pcorr, optimizer }

/-- The legacy PTGSK seNorge forward BOBYQA scoreboards, one per pcorr setting: built first. -/
def firstSlice : List FigureSpec :=
  [fig .scoreboard .seNorge2018 (some .forward) (some false),
   fig .scoreboard .seNorge2018 (some .forward) (some true)]

/-- Aggregate figures: 35, all seNorge2018. AIFS is future work (D-023) and has none. -/
def aggregateFigures : List FigureSpec :=
  let s := Forcing.seNorge2018
  firstSlice ++
  [fig .scoreboard s (some .reverse) (some false), fig .scoreboard s (some .reverse) (some true),
   fig .scoreboard s (some .forward) (some false) .sceua,
   fig .scoreboard s (some .forward) (some true) .sceua,
   fig .cdf s (some .forward) (some false), fig .cdf s (some .forward) (some true),
   fig .modelPair s (some .forward) (some false), fig .modelPair s (some .forward) (some true),
   fig .validationDrop s (some .forward) (some false), fig .validationDrop s (some .forward) (some true),
   fig .validationDrop s (some .reverse) (some false), fig .validationDrop s (some .reverse) (some true),
   fig .pcorrEffect s (some .forward) none, fig .pcorrEffect s (some .forward) none .sceua,
   fig .pcorrEffect s (some .reverse) none,
   fig .kgeCompass s (some .forward) (some false), fig .kgeCompass s (some .forward) (some true),
   fig .ruzzante s (some .forward) (some false), fig .ruzzante s (some .forward) (some true),
   fig .lowFlow s (some .forward) (some false), fig .lowFlow s (some .forward) (some true),
   fig .directionCompare s none (some false), fig .directionCompare s none (some true),
   fig .lstmVsShyft s (some .forward) (some false), fig .lstmVsShyft s (some .forward) (some true),
   fig .lstmVsShyft s (some .reverse) (some false), fig .lstmVsShyft s (some .reverse) (some true),
   fig .seedSpread s (some .forward) (some false), fig .seedSpread s (some .forward) (some true),
   fig .seedSpread s (some .reverse) (some false), fig .seedSpread s (some .reverse) (some true),
   fig .map s (some .forward) (some false), fig .map s (some .forward) (some true)]

/-- Detail catchments are the 5 best and 5 worst by KGE for rpmstk with pcorr on (D-023). The
stations come from computed metrics, so they are listed here once the metrics exist. -/
def detailBest : Nat := 5
def detailWorst : Nat := 5

/-- Catchment-detail figures (at most 10): empty until the metrics select the stations. -/
def detailFigures : List FigureSpec := []

def figureGrid : List FigureSpec := aggregateFigures ++ detailFigures

def maxAggregateFigures : Nat := 48
def maxDetailFigures : Nat := 10

/-- The export check: published figure ids equal the declared ids, none missing, none extra. -/
def gridMatches (declared published : List String) : Bool :=
  declared.all published.contains && published.all declared.contains

#guard aggregateFigures.length == 35
#guard detailBest + detailWorst ≤ maxDetailFigures
#guard aggregateFigures.all (·.forcing == .seNorge2018)
#guard aggregateFigures.length ≤ maxAggregateFigures
#guard detailFigures.length ≤ maxDetailFigures
#guard (figureGrid.map FigureSpec.id).eraseDups.length == figureGrid.length
#guard firstSlice.all aggregateFigures.contains
#guard aggregateFigures.all fun f => f.view != .catchmentDetail && f.station.isNone
#guard detailFigures.all fun f => f.view == .catchmentDetail && f.station.isSome
#guard (figureGrid.filter (·.forcing == .aifs)).all fun f => f.view != .lstmVsShyft
#guard gridMatches (figureGrid.map FigureSpec.id) (figureGrid.map FigureSpec.id)
#guard !gridMatches (figureGrid.map FigureSpec.id) ((figureGrid.map FigureSpec.id).drop 1)
#guard !gridMatches (figureGrid.map FigureSpec.id) ("undeclared" :: figureGrid.map FigureSpec.id)

/-- The grid is within its bounds, and a passing export check means no declared figure is
missing and none is undeclared. -/
theorem figureGrid_ok :
    (aggregateFigures.length ≤ maxAggregateFigures ∧ detailFigures.length ≤ maxDetailFigures) ∧
    ∀ declared published : List String, gridMatches declared published = true ↔
      (∀ x ∈ declared, x ∈ published) ∧ (∀ x ∈ published, x ∈ declared) := by
  refine ⟨by decide, fun declared published => ?_⟩
  simp [gridMatches, List.all_eq_true]

end ShyftBench
