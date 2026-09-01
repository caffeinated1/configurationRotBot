# Configuration Rot Report — <repo name>

**Rot index: <N>/100** (lower is better) · <M> findings · <trend line, if `.configrot/state.json` has history>

<Two or three sentences of actual analysis. What state is this repo in, and what
is the one thing to do about it first? If a single change unblocks several
findings, say so here — that sentence is what gets a modernization approved.
Do not restate the request or list category counts; the header already did.>

## Do these first

1. **<Finding title>** — <why it leads; what it unblocks> (`<id>`, <effort>)
2. **<Finding title>** — <...> (`<id>`, <effort>)
3. **<Finding title>** — <...> (`<id>`, <effort>)

## Findings

<Paste and edit the output of `scan.py --format markdown`. Grouped by category,
sorted by severity, each with evidence at file:line, what it means, and the fix.
Do not rewrite it from scratch — the generated form is already the right shape.>

## Remediation sequence

<The same findings in dependency order rather than severity order, with a word
on why the order is what it is. This is the section people act on.>

1. <Reconcile the version declarations — unblocks items 2 and 4>
2. <Runtime / package manager>
3. <Build and test tooling>
4. <Framework majors, one at a time>
5. <Hazard cleanup>
6. <Cruft>

## Changes made

<Omit this section if you only diagnosed.>

| Change | Findings resolved | Verified by |
|---|---|---|
| <what you did> | `<id>`, `<id>` | `<the commands you ran>` |

## Attempted and reverted

<Omit if nothing was reverted. Otherwise this is the most valuable section in
the report for whoever picks this up next — and it is what stops the next
scheduled run walking into the same wall.>

| Change | Why it was reverted |
|---|---|
| <what you tried> | <what blocked it, concretely, and what would unblock it> |

## What I could not check

<Every entry from `skipped` in findings.json, in plain language. Never omit this
section — a scan that silently skipped the advisory check because npm was
missing has manufactured confidence, and this is what keeps the rest honest.>

- <detector>: <reason>

## Observations

<Anything real you noticed that the scanner did not produce, clearly separated
from the evidence-backed findings above. If an observation generalizes beyond
this repo, note that it should become a rule in `data/rules.json`.>
