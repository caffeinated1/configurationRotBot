# Contributing to Community Goal

You do not need to write code, and you do not need to be a developer. The most
valuable contributions here are **citations, local statutes, and corrections** —
all of them small JSON edits or a filled-in issue form.

Who this is for: residents who have been through a proposal, town and county
staff, planning and zoning boards, state agencies, utility consumer advocates,
NGOs, law school clinics, acoustical and hydrological engineers, and land use
counsel.

## Ways to help, roughly by leverage

| # | Contribution | Who it suits | Effort |
|---|---|---|---|
| 1 | **Cite a claim.** 18 of 18 claims carry no primary source | Anyone with a library card | Minutes |
| 2 | **Add a jurisdiction overlay.** Attach your notice statute, drought stages, tariff docket, and security authority to the requirements they govern | Agencies, counties, clinics, NGOs | An afternoon |
| 3 | **Correct something.** A wrong figure, a legal statement that does not hold in your state, a requirement filed under the wrong instrument | Anyone who spots it | Minutes |
| 4 | **Propose a requirement.** Something the guide misses, or a protection that failed in practice | Planners, counsel, engineers, residents who lived it | An hour |
| 5 | **Report from experience.** What you required, what happened, what you would write differently | Anyone who has been through it | Varies |
| 6 | **Translate.** The data is separate from the presentation, so a translation is a data file, not a fork | Bilingual contributors | Varies |

Not sure which? **[ROADMAP.md](ROADMAP.md) lists specific claimable work** — every
uncited claim with a note on where its primary document probably lives, the
jurisdictions worth overlaying first, and the gaps we already know about. Or open
an issue describing what you have and someone will help you file it.

## Setup

There isn't one. Python 3.9+ and a clone — no dependencies, no build tools, no
package manager.

```bash
git clone https://github.com/caffeinated1/configurationRotBot
cd configurationRotBot

python3 community-goal/build.py --check   # validate the data, write nothing
python3 community-goal/build.py           # generate community-goal/dist/
python3 community-goal/serve.py           # build and open http://localhost:8000
python3 tests/test_community_goal.py      # the full check suite
```

`build.py --check` is the fast loop. It fails with the file and field to fix, so
you do not need to read the Python to correct your JSON.

## 1. Citing a claim

Every figure in `data/evidence.json` came from a source document that names no
citations. Rather than invent references, each claim ships with a `verify` field
saying how a community would check it locally — and an empty `sources` array
waiting for someone to close the gap.

Find the claim's `id` (the Evidence view on the site links each one), then:

```jsonc
{
  "id": "ev-incentive-returns",
  "headline": "States lose 52 to 70 cents per dollar of data center sales tax exemption",
  "sources": [
    {
      "title": "Exact title of the document",
      "publisher": "The body that published it — a legislative auditor, a court, a commission, a university",
      "url": "https://…",                  // must be https, and must resolve
      "date": "2024-06",                   // as specific as the document allows
      "note": "Where in it — table 4, page 19, paragraph 32"  // optional but kind
    }
  ]
}
```

What counts as a source, in descending order of usefulness:

1. A primary public document — a statute, a court opinion, a commission order, a
   legislative audit, an agency dataset.
2. A published study, if its method is stated and its data is available.
3. Reporting that quotes and links to one of the above.

What does not count: a press release, an advocacy summary of a document nobody
links, a paywalled item with no public equivalent, or another guide citing this
one. **If a claim turns out to be wrong, say so** — a correction that removes a
figure is worth more than a citation that props one up.

## 2. Adding a jurisdiction overlay

The requirements are meant to be portable. Statutes are not. An overlay attaches
local law to shared requirements without changing them for anyone else, so the
guide stays comparable across places.

```bash
cp community-goal/data/jurisdictions/template.json \
   community-goal/data/jurisdictions/vermont.json
```

Then edit: set `id` (lowercase, hyphenated), `name`, `level`
(`national`, `state`, `province`, `county`, `municipality`), `status`, at least
one maintainer with a public contact, and one note per requirement you can speak
to. Keys under `notes` are requirement ids; the build rejects one that does not
exist.

```jsonc
"notes": {
  "s1-r5": {
    "note": "What the rule actually is here, in plain language.",
    "citation": "The statute or docket, with its section number."
  }
}
```

Three rules for overlays:

- **Add context, never override.** An overlay cannot change, weaken, or delete a
  requirement. If a requirement is wrong everywhere, that is a correction, not an
  overlay.
- **Name a maintainer.** An overlay nobody maintains goes stale silently, and
  stale law is worse than no law. The build rejects one with no maintainer.
- **Be honest about `status`.** `draft` until someone qualified has checked it;
  `reviewed` only when they have. The site labels anything that is not reviewed
  and tells readers to confirm with counsel. Nobody will think less of a draft.

You do not have to cover all 71 requirements. Six good notes beat seventy
placeholders.

## 3. Proposing a requirement

Add an object to the right section's `requirements` array in
`data/sections.json`:

```jsonc
{
  "id": "s4-r9",                    // next free number in that section; never reuse one
  "title": "The imperative, in one line",
  "detail": "What to require and why. Two or three sentences.",
  "type": "commitment",             // commitment = scored against the four pillars; action = done or not
  "weight": 3,                      // 3 critical, 2 important, 1 supporting
  "instruments": ["permit", "utility"],   // which documents can actually carry it
  "tags": ["water", "drought"],
  "evidence": ["ev-…"],             // optional, must resolve
  "pitfall": "What went wrong somewhere this was missing."   // optional, and the most useful field in the file
}
```

A proposal is far stronger with a failure mode attached. "Require X" invites
debate; "here is what happened to a town that did not require X" ends it.

Before proposing, check that it is not already covered — `api/v1/search.json`
and the site's search cover all 71.

## 4. Corrections

File them. They outrank everything else on this list, including your own earlier
contributions. If a figure is wrong, a legal statement does not hold in your
state, or a requirement is filed under an instrument that cannot carry it, say
so with whatever evidence you have — even if that evidence is only "I am the
zoning administrator and this is not how it works here."

## What gets merged

- **Portable.** Anything true only in one jurisdiction belongs in an overlay.
- **Sourced, or honestly unsourced.** A claim with no source ships with a way to
  verify it and is counted publicly in `api/v1/coverage.json`. Do not quietly add
  an uncited figure.
- **Not legal advice.** The guide says what to require and why. It does not tell
  a town what the law is where they are.
- **Ids are permanent.** People cite `s9-r2` in staff reports and council packets.
  Renaming one breaks their citation. Add a new id instead; retire an old one by
  marking it, never by reusing the number.
- **Stdlib only.** No runtime dependencies in `build.py`, no frameworks or
  third-party requests in `site/`. A civic tool that needs `npm install` to
  rebuild is a civic tool that stops being rebuilt.
- **Declare an interest.** See [GOVERNANCE.md](GOVERNANCE.md) — disclosed
  interest is welcome, undisclosed interest gets the contribution reverted.

Tests enforce most of this. If `python3 tests/test_community_goal.py` passes,
your change is structurally sound; the rest is review.

## Licensing of contributions

By contributing you agree that your content is published under
**CC BY 4.0** and your code under **MIT**, and that you have the right to submit
it. If you are contributing on behalf of an employer, make sure you are
authorised to. There is no CLA.

Public-sector contributors: work that is a public record or otherwise not
copyrightable in your jurisdiction is welcome as-is — note that in the pull
request and we will mark it.

## Conduct

Be straightforward and assume good faith. People on every side of these
proposals — including operators and their advisers — are welcome to contribute
under the disclosure rule. Attacks on people, rather than on claims, are not.
See [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md).
