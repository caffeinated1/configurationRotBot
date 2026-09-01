# Taxonomy reference

## Categories

Every finding is exactly one of these. When a finding could be two, pick by
what the *fix* is, not by what the symptom looks like.

### DRIFT — behind current
Versions lagging the current release. Bumping is the fix.
*Deliberately under-reported*: Dependabot and Renovate solve this well, and
duplicating their firehose adds noise without information. Raise individual
findings only when the gap is large enough to imply migration work.

### DECAY — deprecated or end-of-life
Past EOL, or formally deprecated upstream. The distinguishing feature is a
**date**: support has ended or will end on a specific day. Highest-confidence
category because it needs no judgment, only a calendar.

### CRUFT — dead weight
Config or dependencies that no longer affect anything. Low severity, high value:
cruft is what makes a repo feel abandoned to a new contributor, and it makes
every other finding harder to reason about. Always heuristic — recommend
verification, never deletion outright.

### HAZARD — actively unsafe
Known vulnerabilities, and packages whose upstream is archived. An archived
package is a HAZARD rather than DRIFT because every future advisory against it
is permanently unfixable.

### DIVERGENCE — self-contradiction
Two config surfaces in the same repo declaring different truths. Either a latent
bug waiting for an environment difference, or a stale file. Report both; don't
pretend to know which. **The most durable detector class** — it needs no network
and no knowledge of what is currently modern, so it never goes stale.

### STAGNATION — the ecosystem moved on
A new standard was adopted and this repo never picked it up. This is where
"reinvigorate my app" actually lives, and also the category most likely to be
obnoxious — "you should move off Jest" is useful to some teams and insulting to
others. Keep it at `low`/`medium`, make the opt-out easy, and never auto-fix.

## Severity

Computed from blast radius, time pressure, and exploitability:

| Severity | Meaning | Test |
|---|---|---|
| `critical` | Broken or unsupported **now** | Is something already failing, or receiving no security patches today? |
| `high` | Breaks soon, or behaves differently across environments | EOL within 90 days; next upstream release breaks it; DIVERGENCE affecting what ships |
| `medium` | Meaningfully behind, deprecated with a working shim | Nothing breaks today, but the gap is growing |
| `low` | Cosmetic, cruft, optional modernization | Nobody would notice if it stayed |

The most common misclassification is rating something `high` because it *feels*
bad. Ask what breaks and when. If the answer is "nothing, it's just old", it is
`low` or `medium`.

## Effort

Estimate the whole change including verification, not just the edit.

| Effort | Scale |
|---|---|
| `trivial` | One line, one file. Version bump, delete a dead file |
| `small` | One file plus verification. Config key rename, base image change |
| `medium` | Several files, a real migration path exists. Flat config, requirements→pyproject |
| `large` | Cross-cutting; touches source, not just config. Framework major, test-runner swap |
| `epic` | Needs a plan and probably a person. CRA→Vite on a large app, CJS→ESM |

## Autofix

Gates what a scheduled agent may do unattended.

- **`safe`** — mechanical and fully verifiable. The change has one correct form
  and the verification either passes or doesn't. Bumping an action version,
  deleting an obsolete `version:` key.
- **`assisted`** — an agent can do it correctly, but a human should look. Any
  migration with choices in it, anything touching what ships.
- **`manual`** — needs a human decision *first*. Anything where the right answer
  depends on team priorities rather than on facts: "should we leave Jest?",
  "should we drop Node 18 support?".

Only `safe` + `trivial` is ever eligible for auto-merge, and only when
`CONFIGROT.md` opts in. When unsure between two levels, pick the more cautious
one — the cost of an unnecessary review is minutes; the cost of an unreviewed
bad merge is the project's trust in the tool.

## Confidence

- `high` — a deterministic check proved it (file exists, version compares, date passed)
- `medium` — strong signal with a plausible false-positive path (orphan config in a monorepo)
- `low` — heuristic (unused-dependency text search)

Never present `low` confidence as fact. "5 dependencies appear unused" is honest;
"5 unused dependencies" is not.
