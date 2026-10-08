/-!
# Decision log

Founder decisions, each linked to the requirements it refines. `ShyftBench/Trace.lean`
fails the build if a link names no requirement.
-/

namespace ShyftBench

structure Decision where
  id : String
  date : String
  decided : String
  why : String
  refines : List String
  deriving Repr

def decisions : List Decision := [
  { id := "D-001", date := "2026-10-01"
    decided := "First new experiment: RPMFSM2K (r_pm_fsm2_k) on the snow-dominated cohort, pinned to shyft origin/master at bfbdbe63c or later."
    why := "r_pm_fsm2_k is on origin/master with Python bindings and DRMS support; the local master (2026-04-06) and the fsm_tin_1403 checkout lack it."
    refines := ["bench.shyft.pinned", "bench.experiment.catalogue"] },
  { id := "D-002", date := "2026-10-01"
    decided := "Before launch, check the pod's Shyft build for r_pm_fsm2_k. If it is missing, run PTFSM2K on Sigma2 instead, or ask the Sigma2 team for a new image."
    why := "The pod's Shyft version is not known; a run must not start on a build that lacks its stack."
    refines := ["bench.launch.precondition", "bench.launch.fallback", "bench.results.filing"] },
  { id := "D-003", date := "2026-10-01"
    decided := "The snow-dominated cohort is the mountain and inland stations of calc_hydrological_regime.r's output as it is now (70 stations); the classification is not extended."
    why := "Most other catchments in the list have no discharge data; only some AIFS catchments do."
    refines := ["bench.cohort.snow"] },
  { id := "D-004", date := "2026-10-01"
    decided := "Start FSM2 testing with seNorge2018 forcing."
    why := "seNorge2018 (1958-2020) covers the benchmark periods and matches the legacy runs."
    refines := ["bench.experiment.catalogue", "bench.compare.matched"] },
  { id := "D-005", date := "2026-10-01"
    decided := "Repository shyft-bench-platform, hosted on GitHub as primary."
    why := "The Copilot cloud agent, pull-request review and Actions need GitHub; a GitLab-to-GitHub mirror is one-way."
    refines := ["bench.ci.smoke", "bench.audit.independent"] },
  { id := "D-006", date := "2026-10-01"
    decided := "Do not re-run legacy results; import them read-only and collect the finished rpmstk reverse run."
    why := "The published benchmark is the baseline; re-running it would cost compute and break provenance."
    refines := ["bench.legacy.read-only", "bench.collect.reverse-run"] },
  { id := "D-007", date := "2026-10-03"
    decided := "The Sigma2 Guru's first task is to collect the finished rpmstk reverse run, which is stored in DTSS container se-bench. The full check of how the pod code diverged from the repository comes later, before any new experiment is launched; collection only snapshots the pod code's checksums."
    why := "Getting the finished results home is the first value; the earlier split between containers and the store's top level is resolved by the founder in the store."
    refines := ["bench.collect.reverse-run", "bench.sigma2.code-divergence"] },
  { id := "D-008", date := "2026-10-02"
    decided := "Add a Documentation agent to the crew, responsible for documentation and for web search of hydrological benchmarking studies."
    why := "Docs must stay true to the spec, and experiment plans need verified literature behind them."
    refines := ["bench.docs"] },
  { id := "D-009", date := "2026-10-05"
    decided := "All Sigma2 work goes through the deterministic tool scripts/sigma2.py (Python standard library; versioned pod scripts piped to the pod's python, context and namespace pinned in config/sigma2.json, every step in runs/<run_id>/manifest.json). A workspace hook blocks raw kubectl, the auth helper and kubeconfig for every agent. First slice: preflight, inventory, snapshot, complete, extract, fetch."
    why := "Results must be reproducible without an agent: same inputs give the same outputs, and the founder can repeat any step. The founder authenticates; the tool never handles credentials."
    refines := ["bench.sigma2.safety", "bench.collect.reverse-run"] },
  { id := "D-010", date := "2026-10-05"
    decided := "Collect the legacy reverse run as it was actually launched: by hand, in batches, from the old run_benchmark_experiment.py and fill_benchmark_data.py, not from the new config. A run is reverse when its calibration starts after its simulation starts (T0_CAL 1999-09-01 + 7792 days, T0_SIM 1979-09-01 + 15098 days); the series names carry no _rev. The founder confirms which stations the run covered. Only collection reads the old code; this repository does not otherwise depend on shyft-hydro-benchmarking."
    why := "The new benchmark config was never used for this run, so reading it gave an empty expected set and a forward direction. New experiments run from this repository's own scripts once the old results are home."
    refines := ["bench.collect.reverse-run", "bench.legacy.read-only"] },
  { id := "D-011", date := "2026-10-08"
    decided := "Use GitHub for delivery: the Copilot cloud agent gets a prepared environment (.github/workflows/copilot-setup-steps.yml: Python requirements and a built Lean package); the static dashboard is published on GitHub Pages only from a main commit that passed the Lean gate, with every published file checksummed and given a build-provenance attestation; rulesets on main forbid deletion and force-push, require signed commits, and require a pull request with the gate passing for everyone but the founder."
    why := "Agents can then work from issues in GitHub's cloud and still meet the gate; results reach readers only from checked commits; and anyone can verify which commit and workflow built a published file."
    refines := ["bench.dashboard", "bench.audit.independent"] },
  { id := "D-012", date := "2026-10-06"
    decided := "Lean is the source of truth for vocabularies, canonical order and colours, catalogue, metric list and generated export format. Python computes numeric results; the TypeScript dashboard is static, reads the export and computes no metrics."
    why := "One specification must define what is computed and presented, with computation and rendering kept at the appropriate boundaries."
    refines := ["bench.dashboard", "bench.export"] },
  { id := "D-013", date := "2026-10-06"
    decided := "Recompute metrics from daily series for legacy Shyft, reverse-run, LSTM and new results; never display metric columns from legacy CSVs. Use hydroeval for NSE, KGE (Gupta et al., 2009), KGE' (Kling et al., 2012), PBIAS and KGE(1/Q); provisionally map hydroeval kge and kgeprime to the two KGE formulations pending verification against a pinned hydroeval version. Port and characterize the old repository's Ruzzante et al. (2025) NSE decomposition from ../shyft-hydro-benchmarking/catchments_simulation/service_based/analysis/decomp_utils.py and compute_ruzzante_metrics.py. For KGE(1/Q), use ε = 0.01 × mean observed flow over evaluation, add ε to both series, and retain zero-flow days."
    why := "The dashboard must expose explicitly defined metrics and reconcile existing formulation differences; the historical Ruzzante output and zero-flow behavior need characterization rather than silent reinterpretation."
    refines := ["bench.metrics.canonical"] },
  { id := "D-014", date := "2026-10-06"
    decided := "A dashboard model is either a Shyft stack or LSTM. Assign LSTM #e31a1c, PTFSM2K #e7298a and RPMFSM2K #980043; these hex values are founder-approved."
    why := "LSTM belongs in the canonical model vocabulary and palette without being represented as a Shyft stack; the colours distinguish it and the FSM2 pair."
    refines := ["bench.dashboard", "bench.export"] },
  { id := "D-015", date := "2026-10-06"
    decided := "Forcing selects the experiment and is not a comparison axis: seNorge2018 is the main/default experiment, AIFS is separate, and results are never compared across forcings. Derive direction from calibration and simulation periods. Import SCE-UA alongside BOBYQA. Preserve seeds v00-v04 as a variant axis and show their spread without silently selecting the best."
    why := "Forcings have different coverage and catchments; direction, optimiser and seed are analysis dimensions whose effects must remain explicit."
    refines := ["bench.experiment.catalogue", "bench.compare.matched", "bench.dashboard", "bench.export"] },
  { id := "D-016", date := "2026-10-06"
    decided := "Supersede D-001 for the active FSM2 plan and D-002's PTFSM2K fallback clause: PTFSM2K is the only active planned FSM2 stack; RPMFSM2K is future work. Keep the pod-build precondition, but do not substitute another stack for the active PTFSM2K experiment; request a suitable image if the pod lacks it. Catalogue AIFS experiments with their own periods and catchments; LSTM forward/reverse runs from lstm_baseline/runs/shyft_lstm_{forward,reverse}_*; seeds v00-v04; SCE-UA legacy runs such as ptgsk_bc/*_sceua.csv; and actual legacy catchment lists. The first vertical slice is the read-only legacy PTGSK seNorge forward result, both pcorr settings and BOBYQA. The CI smoke calibration is PTFSM2K, KGE, cid-10-178.1.0 and pcorr enabled."
    why := "The currently available pod supports PTFSM2K, while the export and dashboard can be developed against a small, reproducible legacy slice. The smoke parameters are fixed to make the CI reference deterministic."
    refines := ["bench.experiment.catalogue", "bench.shyft.pinned", "bench.launch.precondition", "bench.launch.fallback", "bench.results.filing", "bench.ci.smoke", "bench.dashboard"] },
  { id := "D-017", date := "2026-10-08"
    decided := "Use a mixed dashboard export: JSON for canonical definitions, catalogue and manifest; GeoJSON for catchment geometries; partitioned Parquet for the metrics table and per-catchment, per-experiment series."
    why := "JSON keeps small specification metadata inspectable, GeoJSON is directly usable for map features, and columnar Parquet suits the larger tabular metrics and time-series data without requiring clients to load the full dataset."
    refines := ["bench.export"] }
]

end ShyftBench
