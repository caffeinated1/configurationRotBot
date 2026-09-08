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
| `data/jurisdictions/` | Community-contributed local overlays — one JSON file per place |
| `schema/guide.schema.json` | Shape of the data files |
| `build.py` | Validates the data and generates `dist/` — the API and the site |
| `serve.py` | Builds and serves locally over HTTP |
| `site/` | The interactive site (no framework, no build step, no third-party requests) |
| `extract.py` | Moves the guide to its own repository, rewriting paths and URLs |
| `standalone/` | The few files that only make sense once it is standalone |
| `CONTRIBUTING.md` | How to cite a claim, add a jurisdiction, propose a requirement |
| `GOVERNANCE.md` | Who decides, how disputed claims are handled, the disclosure rule |
| `ROADMAP.md` | Specific claimable work, starting with the 18 uncited claims |

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
api/v1/jurisdictions.json             local overlays and how to add one
api/v1/jurisdictions/{id}.json        one overlay, keyed by requirement id
api/v1/coverage.json                  how many claims are traced to a source
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
- **Contribute** — citation coverage, the four ways in, and the ground rules.

A **local overlay** picker in the sidebar attaches your jurisdiction's statutes,
drought stages, and dockets to the requirements they govern, inline, without
changing the shared guide for anyone else.

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

Change `data/*.json` and rebuild; nothing in `site/` hardcodes the content, so
editing the guide never means editing the page. The build fails with the file
and field to fix, so you do not need to read the Python to correct your JSON.

## Contributing

**This is an open project and the most useful contributions need no code.** It is
open to residents, town and county staff, planning boards, state agencies,
utility consumer advocates, NGOs, law school clinics, engineers, and land use
counsel — including people who work for developers and operators, under the
disclosure rule in [GOVERNANCE.md](GOVERNANCE.md).

Four ways in, roughly by leverage:

1. **Cite a claim.** 18 of 18 claims carry no primary source. Coverage is
   published at `api/v1/coverage.json` rather than hidden, so the gap is visible
   and closable. Tracing one claim to a public document is a ten-minute
   contribution that makes the guide materially more usable at a hearing.
2. **Add a jurisdiction overlay.** The requirements are portable; statutes are
   not. Copy `data/jurisdictions/template.json`, replace the notes with your
   notice statute, drought stages, tariff docket, and security authority, and
   open a pull request. Overlays add local context — they never change or remove
   a shared requirement, so the guide stays comparable across places.
3. **Correct something.** Corrections outrank additions, including the
   maintainers' own. "I am the zoning administrator and this is not how it works
   here" is evidence.
4. **Propose a requirement**, ideally with the failure mode attached.

**[ROADMAP.md](ROADMAP.md) is the claimable-work list**: all 18 uncited claims
with a note on where each primary document probably lives, the jurisdictions
worth overlaying first, and the content gaps we already know about.

Issue forms cover all four if you would rather not touch JSON — see the
[templates](https://github.com/caffeinated1/configurationRotBot/issues/new/choose).
Full detail in [CONTRIBUTING.md](CONTRIBUTING.md); decision-making, the
conflict-of-interest rule, and how contested claims are handled in
[GOVERNANCE.md](GOVERNANCE.md).

Requirement ids are permanent, because people cite them in staff reports. `s9-r2`
will mean the same thing next year.

## Moving to its own repository

A civic guide inside a developer tooling repository is hard for a town planner or
an NGO to find or trust, so everything here is self-contained and the move is one
command:

```bash
python3 community-goal/extract.py --dest ../community-goal --git
```

That copies the content to a new repository root, rewrites every path and URL
that assumed a subdirectory, drops in a standalone CI workflow and the licence
pair, then builds and tests the result before it will let you push it. Pass
`--repo owner/name` to target a different name; the URLs follow.

The extraction is covered by the test suite, so renaming a document here cannot
silently break it.

## Provenance and limits

The content is a structured rendering of the source guide. Figures and case
references are reproduced as stated there; the source does not name its
citations, which is why every evidence item ships with a `verify` field instead
of a footnote, and why sourcing them is the top contribution ask. Treat each one
as a claim to confirm locally before relying on it in a hearing.

**This is not legal advice.** Authority for zoning conditions, exactions,
payments, and utility commitments varies by state. Confirm every item with
counsel licensed in your jurisdiction.

Content: **CC BY 4.0**. Code: **MIT**, with the rest of this repository.
Contributions are accepted under the same terms; there is no CLA. Cite as
described in [CITATION.cff](../CITATION.cff).
