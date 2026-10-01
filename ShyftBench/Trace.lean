import LeanSpec.Elab.Verification
import ShyftBench.Design
import ShyftBench.Decisions

/-!
# Traceability and verification statement

Brief -> decisions -> requirements -> design units -> kernel theorems. The build fails on
an orphan requirement, a dangling decision link, or a proof that uses `sorry`.
-/

open LeanSpec

namespace ShyftBench

def requirementIds : List String := allRequirements.toList.map (·.id.value)

-- Every requirement registered with the `requirement` command is in the snapshot.
#guard (registeredSpecs%.map (·.2.id.value)).toList.all requirementIds.contains
#guard requirementIds.eraseDups.length == requirementIds.length

-- Every decision link names a requirement, and every decision refines something.
#guard decisions.all fun d => !d.refines.isEmpty && d.refines.all requirementIds.contains
#guard (decisions.map (·.id)).eraseDups.length == decisions.length

-- No orphans: each requirement has a design unit or only deferred scenarios.
#guard allRequirements.all fun r =>
  allDesigns.any (·.id == r.id) || r.scenarios.toArray.all fun s => s.check matches .deferred _

#guard specSnapshot.wellFormed

verification_statement shyftBenchVerified for specSnapshot

def verificationText : String := emitVerificationStatement shyftBenchVerified

#guard shyftBenchVerified.checkable
#guard shyftBenchVerified.citationsOk
#guard shyftBenchVerified.disjoint
#guard !(shyftBenchVerified.axioms.any (· == "sorryAx"))
#guard shyftBenchVerified.extraAxioms.isEmpty
-- Every executable scenario is covered by a kernel theorem; only deferred ones stay open.
#guard shyftBenchVerified.openObligations.all (·.kind == .deferred)
#guard shyftBenchVerified.proved.size == allDesigns.size

end ShyftBench
