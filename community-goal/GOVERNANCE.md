# Governance

This project publishes requirements that communities use to negotiate against
well-resourced counterparties. That makes it a target for capture in both
directions — by developers who want a requirement softened, and by campaigners
who want a claim overstated. Neither is acceptable, and the defence is procedural
rather than personal.

## Scope

**In scope:** what a local government should require before approving a data
center, why, which instrument can carry it, and what the evidence is. Local law
that governs those requirements, as jurisdiction overlays.

**Out of scope:** telling a town what to decide. The guide is deliberately
usable by a community that approves a project and by one that refuses. It takes
a position on *process and enforceability*, not on outcome.

**Never in scope:** legal advice, a claim that a specific named project is good
or bad, or content about identifiable private individuals.

## Roles

| Role | What it means | How you get it |
|---|---|---|
| **Contributor** | Anyone who files an issue or opens a pull request | Do it |
| **Reviewer** | Reviews changes in a domain — noise, water, utility regulation, land use law, a jurisdiction | Sustained, accurate contributions in that domain; ask |
| **Maintainer** | Merges, cuts versions, enforces this document | Invited by existing maintainers |
| **Overlay maintainer** | Owns one jurisdiction file and its accuracy | Named in the overlay you contribute |

The project is currently maintained by its originating author. That is a fact
about its age, not a design goal. Reviewers and overlay maintainers are the
positions worth filling first, and domain expertise counts for more than commit
history.

## Conflict of interest

**Disclose any material interest in the pull request or issue, before review.**

Material interest means you are employed by, advise, own a stake in, are funded
by, or are in litigation with: a data center developer, operator, or tenant; a
utility or interconnection provider; an equipment vendor; a landowner in a
pending application; or an organisation campaigning for or against data center
development.

Disclosed interest is welcome and disqualifies nobody. An operator's counsel
explaining why a drafting position is unenforceable is exactly the kind of
correction that makes this guide worth using. **Undisclosed interest, once
discovered, gets the contribution reverted** and is the one thing that will get
someone barred from the project.

Maintainers disclose the same way and recuse themselves from merging changes
where they hold an interest.

## How a change lands

1. **Issue or pull request**, using a form where one fits.
2. **Structural check** — CI runs the build and the test suite. A dangling
   evidence id or a note keyed to a requirement that does not exist fails here,
   automatically, before a human looks at it.
3. **Review**, against the criteria in
   [CONTRIBUTING.md](CONTRIBUTING.md#what-gets-merged): portable, sourced or
   honestly unsourced, not legal advice, permanent ids, no dependencies.
4. **Domain review** where the change is technical — a noise threshold, a water
   accounting method, an exactions argument — by someone who works in it.
   Maintainers do not merge a technical change they cannot evaluate; they find
   someone who can, or they say so in the thread and leave it open.
5. **Merge.** Content changes ship on the next deploy to Pages.

Corrections move fast. New requirements move slowly, because 71 well-chosen
requirements are more useful than 200 that nobody finishes reading.

## Disputed claims

Some questions here are genuinely unsettled — ratepayer impact is the clearest
example, where the published evidence points both ways. The project's position
is that **a contested claim is documented as contested, not resolved by
vote.**

When two sourced accounts conflict:

- Both go in the evidence file, each with its source.
- The requirement that depends on them is written so it holds either way. This
  is why the guide argues risk allocation rather than proven harm — the
  protection survives the argument being lost.
- If no requirement survives that treatment, the claim does not carry a
  requirement.

Maintainers do not settle empirical disputes by picking the more useful answer.

## Overlays

Overlay maintainers own their file. A maintainer will not silently edit an
overlay's substance; they may fix formatting, mark an overlay `draft` if its
maintainer is unreachable, or retire one that has gone stale — with a note in
the file saying so and when.

An overlay never overrides a shared requirement. If a jurisdiction's law makes a
requirement impossible, that is worth saying in a note, and worth an issue
against the requirement itself.

## Versioning and citation

Content is versioned in `data/guide.json` (`meta.version`) using semantic
versioning applied to meaning:

- **Major** — a requirement is removed, or its meaning changes such that an
  existing assessment would be wrong.
- **Minor** — requirements or evidence added, an overlay added.
- **Patch** — wording, sources, corrections that do not change what is required.

Requirement ids are permanent across all of it. If you cite `s9-r2` in a staff
report, it will mean the same thing next year.

See [CITATION.cff](../CITATION.cff) for how to cite the guide, and
`api/v1/index.json` for the version a given deployment is serving.

## Forking

The licence permits it and there is no hard feeling in it. If a fork serves a
region, a language, or a different theory of what to require, that is a
reasonable outcome — the data files are the interface, and an overlay or an
export can flow between forks. Say what you changed, keep the attribution, and
do not present a fork as this project.

## Changing this document

By pull request, like everything else, with a maintainer merge and a week for
comment on anything touching conflict of interest or disputed claims.
