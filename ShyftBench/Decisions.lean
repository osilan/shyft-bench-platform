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
    decided := "Superseded for the active FSM2 plan by D-016: the original first new experiment was RPMFSM2K (r_pm_fsm2_k) on the snow-dominated cohort, pinned to shyft origin/master at bfbdbe63c or later."
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
  { id := "D-016", date := "2026-10-08"
    decided := "PTFSM2K is the active FSM2 experiment; RPMFSM2K is a future experiment with Provenance.future. D-001 is superseded for the active plan."
    why := "The active plan uses the stack available on the current pod; RPMFSM2K remains catalogued for a later compatible pod."
    refines := ["bench.experiment.catalogue", "bench.shyft.pinned"] },
  { id := "D-017", date := "2026-10-08"
    decided := "Store the internal long metrics table as Parquet; store each published figure's data table as CSV and the manifest, figure index, canon and catalogue as JSON. The site publishes SVG figures and their CSV tables, but no daily series. Use figure-grid option 2: at most 48 aggregate figures and 10 catchment-detail figures; build the first-slice option 1 scoreboard first, with one figure for each pcorr setting."
    why := "Parquet serves internal analysis; CSV tables are simple for publication; JSON keeps small metadata inspectable. The bounded grid supports the paper views without unbounded variant expansion, and the two-figure first slice verifies the pipeline."
    refines := ["bench.export", "bench.dashboard"] },
  { id := "D-018", date := "2026-10-08"
    decided := "Compare results along exactly one selected axis (model, goal, direction, pcorr, optimiser or seed), matching every other axis and forcing over the matched catchments. Forcing is never an axis and cross-forcing comparison is forbidden."
    why := "This permits the intended forward/reverse, BOBYQA/SCE-UA and model comparisons without mixing forcing effects."
    refines := ["bench.compare.matched"] },
  { id := "D-019", date := "2026-10-08"
    decided := "Define validation as simulation minus calibration. Derive direction and validation intervals from periods and guard both D-010 forward and reverse cases."
    why := "Validation is the simulated interval not used in calibration; daily intervals are represented exactly even when subtraction leaves two disjoint segments."
    refines := ["bench.experiment.catalogue", "bench.dashboard"] },
  { id := "D-020", date := "2026-10-08"
    decided := "Publish paper-quality SVG figures with a CSV data table below each figure. The static site uses only the Lean-generated figure index, selects forcing first and then variants, computes nothing, and publishes no daily series. Python renders every figure for both the site and paper."
    why := "The publication should present final reproducible figures rather than browser calculations or a large raw-series payload."
    refines := ["bench.dashboard", "bench.export"] },
  { id := "D-021", date := "2026-10-08"
    decided := "D-002 stands: when the pod lacks a planned stack, the founder chooses either a separately identified, runnable fallback experiment or an image request. Fallback results are never relabelled as the planned experiment."
    why := "Fallback runs remain useful while preserving experiment identity and provenance."
    refines := ["bench.launch.fallback", "bench.results.filing"] },
  { id := "D-022", date := "2026-10-08"
    decided := "Choose one station uniformly from Regime.mountain using recorded seed 20261008; it selected station 122.14. Fix that station in the CI smoke experiment and guard that it is in the frozen mountain cohort. Keep PTFSM2K, KGE and pcorr enabled."
    why := "A single recorded draw gives a representative mountain smoke catchment while keeping CI deterministic."
    refines := ["bench.ci.smoke"] },
  { id := "D-023", date := "2026-10-08"
    decided := "The founder approves the 35-figure seNorge2018 aggregate grid. AIFS is future work and has no figures. The 10 catchment-detail figures are the 5 best and 5 worst catchments by KGE (Gupta et al., 2009) for rpmstk with pcorr on, listed in Lean once the metrics are computed."
    why := "Best and worst cases show the range of model behaviour without a hand-picked list."
    refines := ["bench.export", "bench.dashboard"] },
  { id := "D-024", date := "2026-10-09"
    decided := "Validation segments shorter than one year are dropped. The legacy reverse run's validation is therefore 1979-09-01 to 1999-09-01; the one-day segment at 2020-12-31 left by its 7792-day calibration is not validation. A calibration is reverse only when it starts after the simulation and ends at the simulation's end within one year; a calibration in the middle of the simulation has no direction."
    why := "The one-day tail is an artefact of the legacy configuration's day count, not an evaluation period; a mid-period calibration is neither forward nor reverse."
    refines := ["bench.experiment.catalogue", "bench.dashboard"] },
  { id := "D-025", date := "2026-10-09"
    decided := "The CI smoke run uses seNorge2018 with calibration 2015-09-01 to 2017-09-01 and simulation 2015-09-01 to 2018-09-01, on the D-022 station, PTFSM2K, KGE and pcorr on."
    why := "Three years inside seNorge2018 coverage keep the smoke run short while still having an unseen validation year."
    refines := ["bench.ci.smoke"] },
  { id := "D-026", date := "2026-10-09"
    decided := "Seed is not a selector on the site: seed spread is shown inside the figures. The figure grid has no seed axis."
    why := "Seeds exist for the equifinality discussion, which needs the spread in one view; a selector would multiply the figures and invite picking one seed."
    refines := ["bench.dashboard", "bench.export"] },
  { id := "D-027", date := "2026-10-09"
    decided := "Five agents instead of ten: Architect (spec and issues only, never builds), Builder (Backend, Frontend, DevOps and Documentation merged; also the cloud agent's rules), Reviewer (Lean and Code Reviewer merged), Sigma2 Guru and Independent Auditor; the Researcher's experiment plans move to the Architect. Supersedes D-008's separate Documentation agent. Work is handed out only as GitHub issues, one pull request per issue straight into main; no integration branches or review rounds. In pull requests the gate accepts added statements only, and a changed statement needs the founder's label statements-approved. Briefs in docs/briefs/ are history."
    why := "The Architect carried the whole brief history in context and did the work itself instead of delegating; three coordination channels (brief, subagents, issues) and two branch levels added steps without adding checks."
    refines := ["bench.docs", "bench.audit.independent"] },
  { id := "D-028", date := "2026-10-09"
    decided := "Render cumulative distributions as small multiples by goal and metric: both specified KGE formulations, KGE(1/Q), and each Ruzzante decomposition metric. Within each panel, model curves use the same finite matched cohort; keep forcing, direction, pcorr and optimiser fixed, and preserve distinct seed observations rather than choosing a best seed."
    why := "This exposes the selected metric variants while keeping each model comparison matched and making seed spread visible without silently selecting a seed."
    refines := ["bench.dashboard", "bench.export", "bench.compare.matched"] },
  { id := "D-029", date := "2026-10-09"
    decided := "The published first slice is the seNorge forward BOBYQA scoreboard for all five legacy Shyft stacks: ptgsk, ptstk, ptsthbv, rpmgsk and rpmstk. Publish one SVG figure with its CSV table for each precipitation-correction setting; include all five stacks in canonical model order and use matched catchment cohorts for model-goal medians."
    why := "A PTGSK-only first slice cannot exercise the planned matched cross-stack comparison; the five named legacy stacks share the selected forcing, direction and optimiser."
    refines := ["bench.dashboard", "bench.export", "bench.compare.matched"] }
]

end ShyftBench
