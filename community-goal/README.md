# Community Goal — a town's first data center

An interactive guide and open JSON API built from
*"A town's first data center: what to require before saying yes."*

**Site:** https://caffeinated1.github.io/configurationRotBot/
**API root:** https://caffeinated1.github.io/configurationRotBot/api/v1/index.json

The point is to make one community's goal legible to another. A town facing its
first data center proposal usually has weeks, a volunteer board, and an
applicant with full-time counsel. This publishes the goal, the ten sections of
requirements that carry it, the evidence behind each one, and a readiness score
that says — in a number a council can defend — how much of the deal is actually
written down.

## The goal

> Before the final vote, the town should be able to tell residents in plain
> language: what will be built, what it will consume, what the public receives,
> what happens if it fails, who enforces the agreement, and who pays to take it
> down.
>
> If any of those answers is incomplete, resolve it before granting the approval
> that spends the last of the town's leverage.

## The basic rule, and why the score works the way it does

> Every important promise needs a **stated limit**, a **reliable way to check
> it**, a **responsible party with money behind it**, and a **practical response
> when it is broken**.

That is the whole scoring model. Each of the 54 commitments is assessed against
those four pillars; each of the 17 actions is done or not; both are weighted
`3` critical / `2` important / `1` supporting. A commitment with a number but no
verification scores 25%, which is roughly what it is worth.

The score is published at `api/v1/scoring.json` so the number is auditable
rather than atmospheric.

## What ships

| Path | What it is |
| --- | --- |
| `data/guide.json` | Goal, framing facts, basic rule, the six instruments, the six pre-vote questions |
| `data/sections.json` | Ten sections, 71 requirements |
| `data/evidence.json` | 18 factual claims, what each is good for, and how to check it locally |
| `schema/guide.schema.json` | Shape of the data files |
| `build.py` | Validates the data and generates `dist/` — the API and the site |
| `serve.py` | Builds and serves locally over HTTP |
| `site/` | The interactive site (no framework, no build step, no third-party requests) |

## API

Every endpoint is a static file, so there is no key, no rate limit, and no
server to go down. `GET` only.

```
api/v1/index.json                     goal, counts, and the endpoint list
api/v1/goal.json                      the goal and the six pre-vote questions
api/v1/rule.json                      the basic rule and its four pillars
api/v1/framing.json                   the two facts that frame the decision
api/v1/instruments.json               the six documents and what each can carry
api/v1/sections.json                  all ten sections with their requirements
api/v1/sections/{id|slug}.json        one section (s5 or noise-standards)
api/v1/requirements.json              all 71 requirements, flattened
api/v1/requirements/{id}.json         one requirement with its evidence inlined
api/v1/evidence.json                  every claim, with how to verify it
api/v1/evidence/{id}.json             one claim
api/v1/questions.json                 the six questions
api/v1/checklist.json                 blank assessment template + scoring model
api/v1/scoring.json                   how the readiness score is computed
api/v1/tags.json                      tag facets with counts
api/v1/search.json                    client-side search index
api/v1/guide.json                     the entire guide in one document
api/v1/guide.md                       the entire guide as Markdown
api/v1/openapi.json                   OpenAPI 3.1 description of all of the above
```

```bash
BASE=https://caffeinated1.github.io/configurationRotBot/api/v1

# what is the town trying to achieve?
curl -s $BASE/goal.json | jq -r .goal.statement

# every critical requirement, and which document has to carry it
curl -s $BASE/requirements.json \
  | jq '.requirements[] | select(.weight == 3) | {id, title, instruments}'

# what has to be in place before the certificate of occupancy
curl -s $BASE/sections/on-site-generation.json | jq '.section.requirements[].title'

# a blank assessment your council can fill in and publish
curl -s $BASE/checklist.json -o assessment.json
```

## The site

Four views, all client-side, all rendered from the same API:

- **Guide** — the full text, all ten sections and every subsection, with search,
  filters by document type and weight, and an inline four-pillar assessment on
  each requirement.
- **Readiness** — a weighted score, per-section progress, the six pre-vote
  questions answered or not, an open-gaps list ordered by weight, and export to
  a Markdown council report or JSON.
- **Evidence** — every claim the guide relies on, what it is useful for, and how
  to check it in your own jurisdiction before repeating it at a hearing.
- **API** — a live explorer over the endpoints above.

Assessment state lives in `localStorage` only. Nothing is uploaded, because a
half-finished evaluation of a live proposal is not something a town should have
to put on someone else's server. Export to JSON to move it between machines or
share it with counsel.

## Local development

```bash
python3 community-goal/build.py --check      # validate the data, write nothing
python3 community-goal/build.py              # generate community-goal/dist/
python3 community-goal/serve.py              # build and serve on :8000
python3 tests/test_community_goal.py         # 26 checks over data, API, and site
```

Standard library only, like the rest of this repository. `build.py` fails on a
dangling evidence id, a requirement filed under the wrong section, or an unknown
instrument — a broken reference should fail the build, not become a dead link on
a public page.

## Editing the content

Change `data/*.json` and rebuild; nothing in `site/` hardcodes the content.
Adding a requirement means adding an object to a section's `requirements` array
with a unique `s{n}-r{n}` id, a `type`, a `weight`, and the `instruments` that
can carry it. The tests will tell you what you missed.

## Provenance and limits

The content is a structured rendering of the source guide. Figures and case
references are reproduced as stated there; the source does not name its
citations, which is why every evidence item ships with a `verify` field instead
of a footnote. Treat each one as a claim to confirm locally before relying on it
in a hearing.

**This is not legal advice.** Authority for zoning conditions, exactions,
payments, and utility commitments varies by state. Confirm every item with
counsel licensed in your jurisdiction.

Content: CC BY 4.0. Code: MIT, with the rest of this repository.
