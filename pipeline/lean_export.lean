import Lean.Data.Json
import ShyftBench.Catalog
import ShyftBench.Figures

/-! Prints the canon, the catalogue and the figure grid as JSON. Run by `python3 -m pipeline.canon`. -/

open Lean ShyftBench

private def arr (l : List Json) : Json := Json.arr l.toArray
private def str (x : String) : Json := Json.str x
private def optStr (o : Option String) : Json := (o.map Json.str).getD Json.null
private def pad (n : Nat) : String := if n < 10 then s!"0{n}" else toString n
private def dateStr (d : Date) : String := s!"{d.year}-{pad d.month}-{pad d.day}"

private def periodJson (p : Period) : Json :=
  Json.mkObj [("start", str (dateStr p.start)), ("days", toJson p.days),
    ("startDay", toJson p.startDay), ("endDay", toJson p.endDay)]

private def intervalJson (i : DayInterval) : Json :=
  Json.mkObj [("startDay", toJson i.startDay), ("endDay", toJson i.endDay)]

private def provenanceKey : Provenance → String
  | .zenodoImport _ => "zenodo-import" | .dtssCollect _ => "dtss-collect"
  | .planned => "planned" | .future => "future"

private def entryJson (e : Entry) : Json :=
  let x := e.experiment
  Json.mkObj [
    ("id", str x.id), ("provenance", str (provenanceKey e.provenance)),
    ("models", arr (x.models.map (str ·.key))), ("forcing", str x.forcing.key),
    ("goals", arr (x.goals.map (str ·.key))), ("optimizer", str x.optimizer.key),
    ("direction", optStr (x.direction?.map Direction.key)),
    ("pcorr", arr (x.pcorr.map toJson)),
    ("calibration", periodJson x.calibration), ("simulation", periodJson x.simulation),
    ("validation", match x.validationPeriods? with
      | some ps => arr (ps.map intervalJson) | none => Json.null)]

private def figureJson (f : FigureSpec) : Json :=
  Json.mkObj [
    ("id", str f.id), ("view", str f.view.key), ("forcing", str f.forcing.key),
    ("direction", optStr (f.direction.map Direction.key)),
    ("pcorr", match f.pcorr with | some p => toJson p | none => Json.null),
    ("optimizer", str f.optimizer.key), ("station", optStr f.station)]

private def canon : Json :=
  Json.mkObj [
    ("shyftPin", str shyftPin.commit),
    ("models", arr (Model.all.map fun m =>
      Json.mkObj [("key", str m.key), ("colour", optStr m.colour?)])),
    ("goals", arr (Goal.all.map (str ·.key))),
    ("regimes", arr (Regime.all.map fun r =>
      Json.mkObj [("name", str r.name), ("colour", str r.colour), ("code", toJson r.code)])),
    ("metrics", arr (Metric.all.map fun m =>
      Json.mkObj [("key", str m.key), ("higherIsBetter", toJson m.higherIsBetter)])),
    ("stations", arr (regimeTable.map fun (s, r) =>
      Json.mkObj [("id", str s), ("regime", str r.name)])),
    ("catalogue", arr (catalog.map entryJson)),
    ("firstSlice", arr (firstSlice.map (str ·.id))),
    ("figureGrid", arr (figureGrid.map figureJson))]

def main : IO Unit := IO.println canon.pretty
