# Brief for the Architect: the dashboard's data

From the founder, 2026-10-06. Branch `spec/dashboard-data`.

## Goal

Specify, in Lean first, everything the dashboard shows, so the Backend Developer can
compute and export it and the Frontend Developer only reads it. Then plan one thin
vertical slice: one experiment, through metrics and export, into one dashboard view.

**Architecture (founder decision):** Lean is the source of truth. It owns the vocabularies,
canonical order and colours, the catalogue, the list of metrics and the export format.
Python computes the numbers. TypeScript renders a **static** site from the export. It
shows the variants the Backend computed and computes nothing itself.

## Decisions to record (`ShyftBench/Decisions.lean`, next free ids from D-012; D-011 is the GitHub delivery set-up)

Each one links to the requirement ids it refines.

1. **Dashboard architecture.** As described above. The export format is generated from
   Lean, the same way the catalogue is. Refines `bench.dashboard` and the new
   `bench.export`.
2. **Metrics are recomputed from the daily series** for every result: legacy Shyft, the
   reverse run, LSTM and new runs. The metric columns in the legacy CSVs (`kge_shyft`,
   `nse_shyft`, `kge`, ...) are not shown. Refines `bench.metrics.canonical`.
   - **hydroeval** for NSE, KGE, PBIAS and the low-flow KGE(1/Q).
   - **Both KGE formulations** are shown: Gupta et al. (2009) and Kling et al. (2012).
     The old `kge_shyft` vs `kge` disagreement comes from this difference. In hydroeval
     these should be `kge` and `kgeprime`; the Backend confirms against the pinned
     hydroeval version (marked **unverified** until then).
   - **Ruzzante et al. (2025) NSE decomposition** (seasonal, interannual and irregular
     NSE, with their r, α and variance shares) needs its own code, which already
     exists in the old repo:
     `../shyft-hydro-benchmarking/catchments_simulation/service_based/analysis/decomp_utils.py`
     and `compute_ruzzante_metrics.py`. Port it with a characterisation test that pins
     the old output first. The Documentation agent records the paper as a verified
     reference.
   - **KGE(1/Q):** KGE on 1/(Q + ε) with ε = 0.01 × mean observed flow over the
     evaluation period, added to both observed and simulated flow. Zero-flow days are not
     dropped. This replaces the old LSTM code's rule (drop q ≤ 0); the reference-value
     test must show the difference on a series with zero-flow days.
3. **Models, not just stacks.** A model is either a Shyft stack or LSTM. This keeps
   LSTM in the canonical order and colours without pretending it is a Shyft stack.
4. **Colours.** LSTM `#e31a1c` (red). PTFSM2K `#e7298a` (magenta). RPMFSM2K
   `#980043` (dark magenta), kept for later. The PT/RPM pairs follow the existing rule:
   PT is lighter, RPM is darker. Distances in CIELAB ΔE from the nearest existing colour:
   LSTM is 33 from RPMGSK `#d6604d`, PTFSM2K is 45 from PTSTHBV `#762a83`, and LSTM vs
   PTFSM2K is 59. The founder approved these hex values on 2026-10-06.
5. **Result variants.** The dashboard can filter and group by each of these:
   - **Forcing selects the experiment; it is not a comparison axis.** seNorge2018 (109
     catchments, its periods) and AIFS (70 catchments, its own periods, 2010–2022
     coverage) are two separate experiments. **Results are never compared across
     forcings.** The forcing selector comes first and decides what the dashboard shows.
     **seNorge2018 is the main experiment and the default.** AIFS has only rpmstk runs,
     so its views compare within AIFS only. Make cross-forcing comparison impossible to
     state: `comparableWith` requires the same forcing, with a theorem.
   - **Direction:** forward or reverse, derived from the calibration and simulation
     periods (D-010), and shown as a label.
   - **Precipitation correction:** on or off.
   - **Optimiser:** import the legacy **SCE-UA** runs (for example `ptgsk_bc/*_sceua.csv`)
     alongside BOBYQA. They support the discussion of how the choice of optimiser
     affects results. Add `Optimizer.sceua`; BOBYQA remains the default.
   - **Seed / variant** (`v00`–`v04`, for example `lstmmip-all/rpmstk/`). These support
     the **equifinality** discussion: show the spread across seeds, never pick the best
     one silently.

## Spec work (Lean first)

- `Domain.lean`: `Model` (stack or LSTM), `Direction`, metric vocabulary (key, family,
  formulation, library, range, whether higher is better), colours for the new models,
  `Optimizer.sceua`.
- `Experiment.lean` / `Catalog.lean`:
  - **RPMFSM2K is not available on Sigma2 now** (D-002 fallback applies). PTFSM2K is
    the active planned FSM2 experiment. Keep RPMFSM2K in the catalogue as a future
    experiment that nothing launches until the pod has `r_pm_fsm2_k`.
  - AIFS experiments with their catchment list and periods.
  - LSTM forward and reverse entries (`lstm_baseline/runs/shyft_lstm_{forward,reverse}_*`).
  - Seeds as a variant axis.
  - Fill the legacy catchment lists, which are still `[]`.
- `Requirements.lean`:
  - Amend `bench.metrics.canonical` (hydroeval, both KGE formulations, KGE(1/Q)). The
    founder approves this statement change by this brief.
  - New `bench.export` with scenarios.
  - Amend `bench.dashboard` to cover variants, seeds and forward vs reverse.

## The export (`bench.export`)

Offer two or three options with trade-offs (for example JSON plus CSV, Parquet, Arrow)
and recommend one. Whatever is chosen, the export contains:

- **Canon:** model, goal, regime and metric order and colours, generated from Lean.
- **Catalogue:** experiments with their variants, catchment lists, periods, Shyft commit
  and provenance.
- **Metrics:** one long table with one row per (experiment, model, goal, forcing,
  direction, pcorr, optimiser, seed, station, period kind, metric).
- **Series:** daily observed and simulated discharge, plus SWE and snow-covered area where
  they exist. Split per catchment and experiment, because the raw output is 15 GB and a
  browser cannot load it.
- **Catchments:** geometry converted to GeoJSON from
  `../shyft-hydro-benchmarking/shyft-data/Data/GIS/*_catchment*_all_attributes.shp`, with
  the regime by name.
- **Manifest:** source files, their SHA-256, the code version and the Shyft commit, so
  every number traces to a run manifest (`bench.workflow` scenario).

## Dashboard views this must support (for the Frontend's brief)

Scoreboard (models × goals, median over the matched cohort), cumulative-distribution
explorer, model A vs model B per catchment, calibration → validation drop, effect of
precipitation correction, KGE components compass (both formulations), Ruzzante
decomposition bars, low-flow panel (KGE(1/Q) and flow-duration curve), forward vs reverse,
LSTM vs Shyft stacks, seed spread (equifinality), map, and catchment detail (hydrograph
with SWE and snow-covered area).

## Agents

The handoffs are already updated on this branch: Backend ↔ Frontend, and Backend →
Documentation for the Ruzzante paper. Canonical copies are in
`copilot-agents/variants/shyft-bench-platform/`.

## First slice (proposal)

Legacy PTGSK, seNorge, forward, both pcorr settings, BOBYQA. Steps:

1. Import the result files read-only.
2. Recompute hydroeval metrics plus Ruzzante.
3. Export.
4. Build one view: the scoreboard, with its data table.

One reference-value test per metric. A check that the view rejects unmatched experiments.

## Do not touch

Gate and `audit/` (Independent Auditor). The legacy result files (read-only). Sigma2 work
(Sigma2 Guru; the reverse-run collection is in progress on `feat/sigma2-cli`).

## Founder decisions already made (2026-10-06)

KGE(1/Q) uses ε = 0.01 × mean flow. SCE-UA runs are imported. RPMFSM2K is for later. seNorge
and AIFS are never compared, and seNorge is the main experiment. The colours are LSTM
`#e31a1c`, PTFSM2K `#e7298a` and RPMFSM2K `#980043`. No questions are open.

## Founder decisions, 2026-10-08 (these replace anything above that disagrees)

Record each one in `Decisions.lean` (numbering: see the review section below), linked to the
requirements it refines.

1. **Compare along one axis.** Two results are comparable when they differ in exactly one
   chosen axis (model, goal, direction, pcorr, optimiser or seed) and agree on all the
   others, over their matched catchments. **Forcing is never a comparison axis**: results
   from different forcings are never compared. This replaces the current
   `comparableWith`, which requires equal periods and optimiser and so rules out forward
   vs reverse and BOBYQA vs SCE-UA. It changes the meaning of `bench.compare.matched`,
   which the founder approves by this decision. Prove it in Lean: a comparison never spans
   two forcings, and the arms differ only in the chosen axis. LSTM enters as a model, so
   LSTM vs Shyft is a comparison along the model axis.
2. **Validation period = simulation period minus calibration period.** The validation
   period is the part of the simulation the model never saw during calibration. Define it
   in Lean from the two periods. For forward runs it lies before the calibration period;
   for reverse runs it lies after. Check that both come out right with `#guard`s on the
   legacy forward and reverse periods (D-010). "Calibration → validation drop" means the
   metric on the calibration period vs the metric on this period.
3. **The site shows final figures, not live calculations.** It is like a paper or poster
   with selectors.
   - Python draws every figure in advance as SVG, in paper quality. The same files go
     into the paper.
   - The site is a thin static page. Its selectors (forcing first, then the variants)
     pick the matching figure, and each figure has its data table below it.
   - Nothing is computed in the browser, and **daily series are not published on the
     site**. The catchment-detail hydrographs are figures like the rest.
   - The **figure grid** (views × variant combinations, including which catchments get a
     detail figure) is declared in Lean. The export check fails if a declared figure is
     missing or an undeclared one appears. Keep the grid bounded; propose its size to the
     founder before rendering.
   - Every figure and table carries its provenance in the manifest: source files,
     SHA-256, code version and Shyft commit. The Pages workflow lists and attests every
     published file (D-011).

What changes in the plan above:

- **Export:** it is now figures (SVG), their data tables (CSV), the canon, the catalogue
  and the manifest. The metrics long table stays as the internal compute output. The
  per-catchment series are no longer exported to the site.
- **Frontend:** a thin TypeScript page (or plain HTML, if that is enough; offer both).
  Its only data is the figure index. It must build into `dashboard/dist/` with `npm ci`
  and `npm run build` and a lock file in `dashboard/`, which is what
  `.github/workflows/pages.yml` runs.
- **Backend:** also owns the figure rendering, with Python, a pinned plotting library and
  the canonical colours from the export.
- **First slice:** the scoreboard figure for legacy PTGSK, seNorge, forward, both pcorr
  settings, BOBYQA, with its table, published through Pages.
- **Cloud agent:** GitHub's cloud agent sees only this repository. The legacy results,
  `../shyft`, the LSTM pickles and the shapefiles are local. Spec work and the thin page
  can run in the cloud; import, compute and rendering run in local VS Code.

## Review of the first Architect run, 2026-10-08

The first run (branch `copilot/vscode-muzen4go-w4b3`) added D-012 to D-017 and amended the
requirements, but it did not have the decisions above. Continue on that branch and fix the
following. The founder approves the resulting statement changes; **do not run
`python3 scripts/gate.py update` and then report the fingerprint as accepted**. List the
changed statements for the founder instead.

The gate's fingerprint check therefore **fails, as expected**, once a statement changes. All
other checks must pass. When only the fingerprint fails and every changed statement is one
this brief asks for, stop and report the list. Do not keep editing to make the gate pass.
The Stop hook asks up to three times; answer each time with the same list.

Requirements are now one file per area under `ShyftBench/Requirements/` (the index is in
`ShyftBench/Requirements.lean`). Edit one requirement at a time, and never re-create a file
(see "Editing spec files" in the Architect's instructions). The first attempt at this brief
mixed requirements together by patching one large file, then rewrote it from memory and
changed 14 statements without asking. Start from the committed requirement files, not from
that attempt.

### Founder decisions on that run

1. **Keep the fallback (D-002 stands).** If the pod lacks the planned experiment's stack,
   the founder chooses either to run the fallback experiment, if the pod provides its
   stacks, or to request an image. A fallback is never relabelled as the planned
   experiment. Restore `FallbackChoice`, `launchFallback` and the `bench.launch.fallback`
   text, together with their theorems and guards. Rewrite D-016 so that it only says this:
   PTFSM2K is the active FSM2 experiment, RPMFSM2K is future (`Provenance.future`), and
   D-001 is superseded for the active plan. Mark D-001 as superseded where it is listed.
2. **The smoke catchment is a random mountain station.** Draw one station at random from
   the mountain stations of the frozen regime table (`Regime.mountain`, `data/regime/`). Do
   it once, with a recorded seed, and fix it in Lean, so the CI reference stays
   deterministic. A `#guard` checks that the station is in the mountain cohort. Remove the
   hard-coded `cid-10-178.1.0`. Keep PTFSM2K, KGE and pcorr on unless the founder says
   otherwise.

### Findings to fix

3. **Statements ahead of the model.** `bench.experiment.catalogue` now names model (stack
   or LSTM), seed and derived direction, and its check stays executable, but none of these
   exist in Lean. Add `Model` (stack or LSTM), `Direction` (derived from periods),
   `Optimizer.sceua`, the seed or variant axis and the metric vocabulary in `Domain.lean`,
   and extend `ResultKey` with them. Until a part exists, its scenario is `check deferred`
   with the reason.
4. **Colours are not recorded.** D-014 approves the colours for LSTM, PTFSM2K and
   RPMFSM2K, but `Stack.colour?` still returns `none` for both FSM2 stacks. Record all
   three, and add a guard that every model has a colour.
5. **The comparison rule contradicts the views.** `bench.compare.matched` still requires
   equal periods and optimiser, which rules out forward vs reverse and BOBYQA vs SCE-UA.
   Replace it with the one-axis rule (decision 1 above), with the theorems asked for there.
6. **Wrong reason for a deferred check.** The scenario "different forcings cannot be
   compared" is deferred because "forcing equality is not yet enforced". It is enforced:
   `comparableWith` requires the same forcing. Make the scenario executable, with a
   theorem.
7. **D-017 was not the founder's choice, and it no longer fits.** The brief asked for
   export options and a wait for the founder's choice. D-017 also publishes daily series
   as Parquet, which decision 3 above removes from the site. Replace D-017. Offer the
   options for the internal compute output (the metrics table, the figure data tables and
   the manifest), and for the figure grid and its size, then wait for the founder's
   choice.
8. **The dashboard text describes the wrong product.** `bench.dashboard` describes an
   interactive TypeScript dashboard. Rewrite it for paper figures selected by variant
   (decision 3 above), and do the same for the scenarios of `bench.export`.
9. **Housekeeping.** Fix the typo "PTFFSM2K" in `Design.lean` and the indentation of the
   catalogue list. Fill the legacy catchment lists from the import (still `[]`), or keep
   a deferred scenario that says why they are empty.

### Numbering

D-012 to D-016 keep their numbers (D-016 is rewritten). D-017 is replaced by the
founder's export decision once it is made. Today's decisions (one-axis comparison,
validation period, paper figures, fallback kept, smoke catchment) get the next free ids.
