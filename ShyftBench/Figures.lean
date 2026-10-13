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
  -- Page views (D-032).
  | regimeMap | varianceByRegime | pcorrCompare | pcorrByRegime | pcorrMap
  | goalGeneralism | biasVariability | directionMap
  deriving Repr, DecidableEq

def FigureView.key : FigureView → String
  | .scoreboard => "scoreboard" | .cdf => "cdf" | .modelPair => "model-pair"
  | .validationDrop => "validation-drop" | .pcorrEffect => "pcorr-effect"
  | .kgeCompass => "kge-compass" | .ruzzante => "ruzzante" | .lowFlow => "low-flow"
  | .directionCompare => "direction-compare" | .lstmVsShyft => "lstm-vs-shyft"
  | .seedSpread => "seed-spread" | .map => "map" | .catchmentDetail => "catchment-detail"
  | .regimeMap => "regime-map" | .varianceByRegime => "variance-by-regime"
  | .pcorrCompare => "pcorr-compare" | .pcorrByRegime => "pcorr-by-regime"
  | .pcorrMap => "pcorr-map" | .goalGeneralism => "goal-generalism"
  | .biasVariability => "bias-variability" | .directionMap => "direction-map"

/-- One published figure. `none` marks an axis the view compares across (or that the experiment
fixes itself) instead of selecting one value. -/
structure FigureSpec where
  view : FigureView
  forcing : Forcing
  direction : Option Direction
  pcorr : Option Bool
  optimizer : Optimizer := .bobyqa
  station : Option StationId := none
  /-- The one model a page selector picks (D-032); `none` when the figure shows all models. -/
  model : Option Model := none
  /-- The one calibration goal a page selector picks (D-032); `none` when the figure shows all. -/
  goal : Option Goal := none
  deriving Repr, DecidableEq

def Optimizer.key : Optimizer → String
  | .bobyqa => "bobyqa" | .sceua => "sceua"

def FigureSpec.id (f : FigureSpec) : String :=
  let part (name : String) : Option String → String
    | some v => s!"-{name}-{v}"
    | none => ""
  s!"{f.view.key}-{f.forcing.key}" ++ part "dir" (f.direction.map Direction.key) ++
    part "pcorr" (f.pcorr.map fun p => if p then "on" else "off") ++
    s!"-{f.optimizer.key}" ++ part "model" (f.model.map Model.key) ++
    part "goal" (f.goal.map Goal.key) ++ part "station" f.station

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

/-- The first published export: five forward legacy views, each with both pcorr settings. -/
def published : List FigureSpec :=
  let s := Forcing.seNorge2018
  [fig .scoreboard s (some .forward) (some false), fig .scoreboard s (some .forward) (some true),
   fig .cdf s (some .forward) (some false), fig .cdf s (some .forward) (some true),
   fig .kgeCompass s (some .forward) (some false), fig .kgeCompass s (some .forward) (some true),
   fig .lowFlow s (some .forward) (some false), fig .lowFlow s (some .forward) (some true),
   fig .ruzzante s (some .forward) (some false), fig .ruzzante s (some .forward) (some true)]

/-- Detail catchments are the 5 best and 5 worst by KGE (Gupta 2009, `Metric.kgeGupta`) for rpmstk with pcorr on (D-023). The
stations come from computed metrics, so they are listed here once the metrics exist. -/
def detailBest : Nat := 5
def detailWorst : Nat := 5

/-- Catchment-detail figures (at most 10): empty until the metrics select the stations. -/
def detailFigures : List FigureSpec := []

def figureGrid : List FigureSpec := aggregateFigures ++ detailFigures

def maxAggregateFigures : Nat := 48
def maxDetailFigures : Nat := 10

/-- Size limits of a published export (D-031), in bytes: 1 MB is 1,048,576 bytes. -/
def maxSvgBytes : Nat := 2 * 1024 * 1024
def maxCsvBytes : Nat := 1024 * 1024
def maxExportBytes : Nat := 15 * 1024 * 1024

/-- Percentiles at which published distributions are summarised (D-031): CDF curves use all
nineteen, boxes the five in `boxPercents` (whiskers at 5 and 95). -/
def cdfPercents : List Nat := [5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95]
def boxPercents : List Nat := [5, 25, 50, 75, 95]

/-! ## Pages (D-032)

The site is organised by research question. Each page lists its figures explicitly, one per
selector value, so the export check can compare ids. A `planned` page is declared but not
published until its data are in the catalogue. `published` above stays the release set until the
build that renders the published pages sets it to `pagesPublished` (D-032). -/

inductive Selector where
  | pcorr | model | goal
  deriving Repr, DecidableEq

def Selector.key : Selector → String
  | .pcorr => "pcorr" | .model => "model" | .goal => "goal"

inductive PageStatus where
  | published | planned
  deriving Repr, DecidableEq

def PageStatus.key : PageStatus → String
  | .published => "published" | .planned => "planned"

structure Page where
  key : String
  title : String
  status : PageStatus
  selectors : List Selector
  figures : List FigureSpec
  deriving Repr

/-- The five legacy Shyft stacks, in canonical model order. -/
def legacyModels : List Model := [.ptstk, .rpmstk, .ptgsk, .rpmgsk, .ptsthbv].map .shyft

private def onPage (view : FigureView) (direction : Option Direction) (pcorr : Option Bool)
    (model : Option Model := none) (goal : Option Goal := none) : FigureSpec :=
  { view, forcing := .seNorge2018, direction, pcorr, model, goal }

def studyAreaPage : Page where
  key := "study-area"
  title := "Study area"
  status := .published
  selectors := []
  figures := [onPage .regimeMap none none, onPage .varianceByRegime none none]

def modelsPcorrPage : Page where
  key := "models-pcorr"
  title := "Models and precipitation correction"
  status := .published
  selectors := [.pcorr]
  figures := firstSlice ++
    [onPage .cdf (some .forward) (some false), onPage .cdf (some .forward) (some true),
     onPage .pcorrCompare (some .forward) none, onPage .pcorrByRegime (some .forward) none,
     onPage .pcorrMap (some .forward) none]

def goalFunctionsPage : Page where
  key := "goal-functions"
  title := "Goal functions"
  status := .published
  selectors := [.model, .pcorr]
  figures := legacyModels.flatMap fun m => [false, true].flatMap fun p =>
    [onPage .goalGeneralism (some .forward) (some p) (some m),
     onPage .biasVariability (some .forward) (some p) (some m)]

/-- Direction and equifinality for RPMSTK. Empty until the reverse run is collected: its figures,
and how the unseeded forward run is compared with the reverse seeds, follow a later decision
(D-032). -/
def robustnessPage : Page where
  key := "robustness"
  title := "Robustness: direction and equifinality"
  status := .planned
  selectors := []
  figures := []

/-- Empty until the LSTM runs are in the catalogue. -/
def lstmPage : Page where
  key := "lstm"
  title := "Against the regional LSTM"
  status := .planned
  selectors := []
  figures := []

def pages : List Page :=
  [studyAreaPage, modelsPcorrPage, goalFunctionsPage, robustnessPage, lstmPage]

def pageFigures : List FigureSpec := pages.flatMap (·.figures)

/-- The release set once the page build lands (D-032). -/
def pagesPublished : List FigureSpec :=
  (pages.filter (·.status == .published)).flatMap (·.figures)

def maxPageFigures : Nat := 32
/-- All pages together, published or planned (D-032). -/
def maxAllPageFigures : Nat := 64

#guard (pages.map (·.key)).eraseDups.length == pages.length
#guard (pageFigures.map FigureSpec.id).eraseDups.length == pageFigures.length
#guard pages.all fun p => p.figures.length ≤ maxPageFigures
#guard pageFigures.all fun f => f.forcing == .seNorge2018 && f.station.isNone
#guard firstSlice.all pagesPublished.contains
#guard pagesPublished.length == 29
#guard pageFigures.length ≤ maxAllPageFigures
#guard pagesPublished.all pageFigures.contains
#guard legacyModels == (Stack.all.take 5).map .shyft
#guard goalFunctionsPage.figures.length == legacyModels.length * 2 * 2
#guard goalFunctionsPage.figures.all fun f => f.model.isSome && f.pcorr.isSome
#guard robustnessPage.figures.isEmpty && robustnessPage.status == .planned
#guard lstmPage.figures.isEmpty && lstmPage.status == .planned

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
#guard published.length == 10
#guard published.all aggregateFigures.contains
#guard firstSlice.all published.contains
#guard (published.map FigureSpec.id).eraseDups.length == published.length
#guard maxSvgBytes ≤ maxExportBytes && maxCsvBytes ≤ maxExportBytes
#guard cdfPercents.length == 19
#guard (cdfPercents.zip cdfPercents.tail).all fun p => p.1 < p.2
#guard (boxPercents.zip boxPercents.tail).all fun p => p.1 < p.2
#guard boxPercents.all cdfPercents.contains
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
