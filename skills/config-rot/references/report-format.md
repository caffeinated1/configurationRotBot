# Report format

Write to `ROT-REPORT.md` at the repo root (or wherever the user asked). People
scan these; they do not read them. The structure is fixed so a returning reader
knows where to look.

## Template

```markdown
# Configuration Rot Report — <repo name>

**Rot index: <N>/100** (lower is better) · <M> findings · <trend, if history exists>

<Two or three sentences. What is the actual state of this repo, and what is the
single most important thing to do about it. No preamble, no restating the
request. If one change unblocks several findings, this is where that goes.>

## Do these first

1. **<Finding title>** — <one line on why it leads> (`<id>`, <effort>)
2. ...

## Findings

### CRITICAL / HIGH / MEDIUM / LOW — grouped by category, sorted by severity

<One block per finding: title, id, severity, effort, evidence with file:line,
what it means, and the fix. `scan.py --format markdown` already produces this;
edit it rather than rewriting it from scratch.>

## Remediation sequence

<The findings above in dependency order, not severity order. Explain the
ordering — this section is the one people actually act on.>

1. Reconcile the Node version declarations (unblocks 4 findings below)
2. Move the Docker base image to Node 22
3. ...

## What I could not check

- <every entry from `skipped` in findings.json, in plain language>

## Observations

<Anything real you noticed that the scanner did not produce. Clearly separated
from the findings above, because these are not evidence-backed. If an
observation generalizes, say it should become a rule in data/rules.json.>
```

## Worked opening

Weak:

> This report identifies several configuration issues in the repository. There
> are 30 findings across 6 categories with an overall rot index of 41.

The reader learns nothing they could not get from the header line.

Strong:

> This repo has not had a dependency touched since 2022. The blocker is
> `node-sass@4`, whose native bindings do not compile on any supported Node
> release — which is why the runtime is pinned to Node 16 (EOL September 2023)
> and why the last four upgrade attempts in the git history were reverted.
> Replacing it with `sass` is a one-line change and unblocks the whole chain:
> the Node bump, the CRA-to-Vite migration, and 9 of the 14 advisories.

The reader now knows what to do on Monday morning.

## Rules

**Lead with the blocker, not the count.** Most rotten repos have one thing
holding everything else hostage. Finding it is the analytical work; the list is
just bookkeeping.

**Say what breaks and when.** "Node 18 is EOL" is a fact. "Node 18 stopped
receiving security patches in April 2025, so the base image ships known
unpatched CVEs" is a reason to act.

**Never inflate.** If the repo is in decent shape, say so in one line and keep
the report short. A five-page report on a healthy repo teaches the reader that
this tool cries wolf, and the next report gets ignored.

**Always include "What I could not check".** A scan that silently skipped the
advisory check because `npm` was missing has manufactured confidence. This
section is what makes the rest of the report trustworthy.

**Attribute confidence honestly.** "5 dependencies appear unused (text search;
verify before removing)" — not "5 unused dependencies".

## After remediation

When the report follows actual changes, add:

```markdown
## Changes made

| Change | Findings resolved | Verified by |
|---|---|---|
| Replaced node-sass with sass | `DECAY.node-sass`, `HAZARD.abandoned.node-sass` | `npm run build`, `npm test` |

## Attempted and reverted

| Change | Why it was reverted |
|---|---|
| CRA → Vite | Three internal packages import `react-scripts/config/env` directly. Needs an owner decision on those packages first. |
```

The reverted table is not an admission of failure — it is the most valuable part
of the report for whoever picks this up next, and it is what stops the next
scheduled run from walking into the same wall.
