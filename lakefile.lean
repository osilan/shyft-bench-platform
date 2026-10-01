import Lake
open Lake DSL

package shyftBenchPlatform

-- Vendored release v1.0.0 (commit 3e13dffe), so agents can read the source.
-- Update with scripts/vendor_lean_spec.sh; see open-lean-spec/VENDORED.md.
require «lean-spec» from "open-lean-spec"

@[default_target]
lean_lib ShyftBench
