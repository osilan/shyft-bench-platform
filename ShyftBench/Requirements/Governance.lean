import LeanSpec.Elab.Sugar

/-!
# Requirements: governance

Documentation and the independent audit.
-/

open LeanSpec

namespace ShyftBench

requirement documentation where
  id "bench.docs"
  shall "Keep README, AGENTS and generated documentation consistent with the Lean specification, and maintain the project's literature on hydrological benchmarking as typed references, each verified against its publisher record and linked to the requirements or experiments it informs."
  strength must

  scenario "unverified reference"
    given "a reference whose DOI or publisher record could not be opened"
    when "it is recorded"
    then_ "it is marked unverified and is not cited as read"
    check deferred "the literature module is not built"

requirement independentAudit where
  id "bench.audit.independent"
  shall "Have an independent auditor, outside the architect's crew and reporting to the founder, check security and quality; audit thresholds may only become stricter."
  strength must

  scenario "audit blocks a weakened check"
    given "a change loosens a gate threshold or removes a check"
    when "the gate runs"
    then_ "the gate fails and the auditor reports the finding verbatim"
    check deferred "audit gate is not installed"

end ShyftBench
