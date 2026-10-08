# Rulesets for `main`

GitHub does not read these files; they are the record of what is applied (D-011). The
founder applies or updates them, because they change repository settings.

Before applying `main-history.json`, add the SSH key that signs your commits to GitHub as a
**signing key** (Settings → SSH and GPG keys → New SSH key → Key type: Signing key).
Until then GitHub marks your commits `unknown_key` and the ruleset would reject your pushes.
Check with `gh api repos/osilan/shyft-bench-platform/commits/main --jq .commit.verification`.

Then:

```bash
gh api -X POST repos/osilan/shyft-bench-platform/rulesets --input .github/rulesets/main-history.json
gh api -X POST repos/osilan/shyft-bench-platform/rulesets --input .github/rulesets/main-gate.json
```

To update one, `gh api repos/osilan/shyft-bench-platform/rulesets` lists the ids; then
`gh api -X PUT repos/osilan/shyft-bench-platform/rulesets/<id> --input <file>`.

| Ruleset | Applies to | Effect |
|---|---|---|
| `main-history.json` | everyone, no bypass | `main` cannot be deleted or force-pushed; every commit must be signed |
| `main-gate.json` | everyone except repository admins | changes reach `main` only by pull request, after the Lean gate job (`gate`) passed |

The founder (admin) can still merge locally and push signed merge commits. Agents and the
Copilot cloud agent go through pull requests and the gate. Commits made by the Copilot cloud
agent and merges made in GitHub's web interface are signed by GitHub.
