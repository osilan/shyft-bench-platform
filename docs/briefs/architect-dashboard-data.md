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

## Decisions to record (`ShyftBench/Decisions.lean`, next free ids from D-011)

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
