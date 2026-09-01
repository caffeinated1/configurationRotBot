---
# How much autonomy this repo grants. off | ondemand | scheduled | keeper
mode: scheduled

# Budget. A maintenance bot that floods a repo gets muted, and then it is worse
# than useless because everyone assumes it is covering the problem.
max_open_prs: 3
max_prs_per_week: 5

# Which autofix classes may merge without a human. [] requires review on all.
# Only `safe` changes are ever eligible, and only when CI is green.
auto_merge: []

# Hard boundary. Findings whose evidence lies entirely under these paths are
# reported as suppressed, never acted on.
never_touch:
  - "terraform/**"
  - "charts/**"

# The commands that define "working" for this repo. The agent runs these before
# and after every change; a change that turns any of them red gets reverted.
# If omitted, they are inferred from CI.
verify:
  - "npm ci"
  - "npm run lint"
  - "npm test"
  - "npm run build"

# Finding ids to ignore. Re-affirm these periodically — a permanent suppression
# is just rot with paperwork.
suppress: []
---

## Constraints

Write these as prose. Constraints like the ones below cannot be expressed in
YAML, and an agent can act correctly on the reasoning, not just the rule.

- Pinned to Node 20 until the Q3 platform migration; the vendor SDK is not
  certified above 20. Revisit after 2026-10-01.
- Do not migrate away from Jest. We know Vitest is faster; the team decided the
  churn isn't worth it this year.
- `src/legacy/` is scheduled for deletion in Q4. Don't invest in modernizing it.

## Priorities

- Security and EOL findings are always in scope.
- Build and CI reliability next.
- Cosmetic modernization only if it is genuinely trivial.
