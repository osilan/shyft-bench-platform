import LeanSpec.Elab.Sugar

/-!
# Requirements: metrics

The canonical metric implementations and their reference checks.
-/

open LeanSpec

namespace ShyftBench

requirement canonicalMetrics where
  id "bench.metrics.canonical"
  shall "Recompute dashboard metrics from daily observed and simulated discharge series for every legacy Shyft, reverse-run, LSTM and new result; do not display metric columns stored in legacy CSVs. Use hydroeval for NSE, KGE (Gupta et al., 2009), KGE' (Kling et al., 2012), PBIAS and KGE(1/Q), and a characterized port of the old repository's Ruzzante et al. (2025) NSE decomposition. KGE(1/Q) uses 1/(Q + ε), where ε is 0.01 times mean observed flow over the evaluation period, added to both series; retain zero-flow days. Check each implementation against fixed reference values."
  strength must

  scenario "pinned hydroeval formulations"
    given "a pinned hydroeval version"
    when "the metric implementations are selected"
    then_ "the version and the mapping of hydroeval kge and kgeprime to the two specified KGE formulations are verified and recorded"
    check deferred "Python pins hydroeval 0.1.0 and tests the mapping, but LeanSpec has no Python target"

  scenario "reference series"
    given "a fixed observed and simulated series with known metric values"
    when "the metrics are computed"
    then_ "NSE, both KGE formulations and PBIAS match their fixed references within the stated tolerance"
    check deferred "Python reference tests cover the port, but LeanSpec has no Python target"

  scenario "low-flow metric retains zero-flow days"
    given "an evaluation series containing zero-flow days"
    when "KGE(1/Q) is computed with ε equal to 0.01 times mean observed flow"
    then_ "ε is added to observed and simulated flow, no zero-flow day is dropped, and the value matches its fixed reference"
    check deferred "Python tests cover epsilon and zero-flow behavior, but LeanSpec has no Python target"

  scenario "Ruzzante port is characterized"
    given "fixed series and output from the old repository's Ruzzante implementation"
    when "the ported seasonal, interannual and irregular NSE decomposition is computed"
    then_ "NSE components, r, α and variance shares match the characterized old output within the stated tolerance"
    check deferred "Python tests compare the port with pinned old outputs, but LeanSpec has no Python target"

end ShyftBench
