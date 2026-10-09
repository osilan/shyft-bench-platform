---
name: Task
about: One bounded piece of building for the Builder (or the Copilot cloud agent)
title: ''
labels: ''
---

<!-- If this waits for another issue, say so here: "Waits for #N (same file)". -->

**Requirement:** `bench.<area>.<id>`, scenario "<scenario name>"

**Task:** <what to build, with every item named; at most 20>

**Files:** <paths this touches>

**Done when:** <a check that confirms it, e.g. guards show X; mutation-checked>

**Not in scope:** <what not to touch>

Rules (see AGENTS.md and `.github/agents/builder.agent.md`):
- One pull request into `main`.
- Do not change requirement text, theorem statements or decisions. If the task needs that, stop and say so in the pull request.
- Run `python3 scripts/gate.py update` for new guards and theorems; the check accepts additions only.
- Anything else you notice goes in the pull request description as a finding.
