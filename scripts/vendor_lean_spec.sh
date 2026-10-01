#!/usr/bin/env bash
# Replace open-lean-spec/ with a release, as plain files (no nested git repo).
#   scripts/vendor_lean_spec.sh v1.0.0
set -euo pipefail
tag="${1:?usage: $0 <tag>}"
url="https://github.com/Bevisera-AS/open-lean-spec.git"
root="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
git clone --quiet --depth 1 --branch "$tag" "$url" "$tmp/src"
commit="$(git -C "$tmp/src" rev-parse HEAD)"
rm -rf "$root/open-lean-spec"
git -C "$tmp/src" archive --prefix=open-lean-spec/ HEAD | tar -x -C "$root"
rm -f "$root/open-lean-spec/.gitignore" "$root/open-lean-spec/.gitlab-ci.yml"
cat > "$root/open-lean-spec/VENDORED.md" <<MD
# Vendored: open-lean-spec

| | |
|---|---|
| Source | $url (canonical: gitlab.com/bevisera/open-lean-spec) |
| Release | $tag |
| Commit | $commit |
| Licence | Apache-2.0 (see \`LICENSE\`, \`NOTICE\`) |

Plain files from \`git archive $tag\`, with no \`.git\`, so this is not a nested
repository and Copilot can read the source. Removed from the archive:
\`.gitignore\`, \`.gitlab-ci.yml\`. Nothing else is changed; do not edit files here.
Update with \`scripts/vendor_lean_spec.sh <tag>\`.
MD
sed -i.bak -E "s/^-- Vendored release .*/-- Vendored release $tag (commit ${commit:0:8}), so agents can read the source./" "$root/lakefile.lean" && rm -f "$root/lakefile.lean.bak"
(cd "$root" && lake update && lake build LeanSpec)
echo "vendored open-lean-spec $tag ($commit)"
