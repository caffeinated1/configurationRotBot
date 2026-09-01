# Contributing

The most valuable contributions to this project are **rules and data**, not
code. Deprecation patterns are the fastest-moving part of the problem and the
part most likely to be out of date — which is why they live in JSON that anyone
can edit without reading a line of Python.

## Ways to help, roughly by leverage

1. **Add a rule** to `data/rules.json` — five lines of JSON for a deprecation
   you got bitten by.
2. **Add an abandoned package** to `data/abandoned.json` — one line.
3. **Fix stale EOL data** — usually `python3 skills/config-rot/scripts/refresh_data.py`.
4. **Improve a reference doc** — `references/` is what the agent reads when it
   performs a migration; a wrong step there produces a wrong migration.
5. **Add an ecosystem detector** — one new file in `scripts/detectors/`.
6. **Report a false positive.** These matter more than missing findings. A tool
   that cries wolf gets muted, and a muted tool is worse than no tool because
   everyone assumes it is covering the problem.

## Setup

There isn't one. Python 3.9+ and a clone.

```bash
git clone https://github.com/caffeinated1/configurationRotBot
cd configurationRotBot
for t in tests/test_*.py; do python3 "$t" || break; done
```

## The invariants

These are enforced by tests, and a PR that breaks one will not be merged
regardless of what else it does. They are what make the tool trustworthy enough
to run unattended.

| Invariant | Why |
|---|---|
| **No third-party imports** in `skills/config-rot/scripts/` | A tool that diagnoses dependency rot cannot itself require `pip install`. It also has to run from a README one-liner on any machine |
| **`scan.py` never writes to the repo under scan** | This is what makes it safe in CI, in a hook, and on code you haven't read |
| **Offline by default** | A scan that needs the network is a scan that doesn't happen |
| **Python 3.9+** | Below 3.11 there is a TOML fallback path; the CI matrix exercises it |
| **Every finding carries file+line evidence** | A finding without evidence is a claim, and claims are what the agent is not allowed to make |
| **Every finding carries a recommendation** | A finding without a fix is just criticism |
| **Finding ids are permanent** | Users suppress by id in `CONFIGROT.md`. Renaming one silently un-suppresses it in every repo that had opted out — add a new id instead |

## Adding a rule

Read [`references/writing-rules.md`](skills/config-rot/references/writing-rules.md)
for the condition grammar. The short version:

```jsonc
{
  "id": "CATEGORY.short-slug",
  "category": "STAGNATION",
  "severity": "medium",
  "when": { /* conditions, ANDed together */ },
  "title": "What is wrong, and its consequence",
  "detail": "Why it matters. What actually goes wrong.",
  "recommendation": "The fix, concretely. Name the command if there is one.",
  "effort": "small", "autofix": "assisted",
  "covers": ["the-package"],
  "references": ["https://..."]
}
```

Then add a fixture to `examples/` that makes it fire, and check it does not fire
on the healthy repo in `tests/test_scan.py`. **A rule that no fixture exercises
will silently stop working and nobody will notice.**

### Severity, honestly

The most common contribution mistake is rating a new rule `high` because you
were recently bitten by it. Ask what breaks and when:

- Silently not working (config ignored, lint not actually running) → `high`.
  These are worse than loud failures because nobody notices them.
- Already failing → `high` or `critical`.
- Works but deprecated, with a shim → `medium`.
- Works fine, just not how people do it now → `low`.

If the honest answer is "nothing breaks, it's just old", it is `low`.

### Opinions

STAGNATION rules are where this project can most easily become obnoxious.
"You should move off Jest" is useful to some teams and insulting to others.

The bar: a STAGNATION rule must describe something the ecosystem has *actually*
converged on, not something you personally prefer. Keep it at `low` or `medium`,
never mark it `autofix: safe`, and make the `recommendation` acknowledge that
staying put is a legitimate choice.

## Adding a detector

One file in `scripts/detectors/`, exposing `run(inv, ctx) -> list[Finding]`,
registered in the `DETECTORS` map in `scan.py`. Order in that map is execution
order, which matters when one detector claims work from another.

- Use `ctx.skip(name, reason)` whenever you cannot check something. Silence is
  the failure mode this project cares most about avoiding.
- Set `confidence: "medium"` or `"low"` for heuristics, and phrase the title
  accordingly — "5 dependencies appear unused" is honest; "5 unused
  dependencies" is not.
- Never shell out without checking `shutil.which` first, and never assume
  network access unless `ctx.online` is set.

Write it a rule instead if the finding is simply "if this config exists, that is
a problem". Detectors are for things that need to compare, compute, or reach
out.

## Pull requests

- One concern per PR. The project's own advice about reviewable diffs applies to
  the project.
- Run the test suite before pushing.
- New behaviour needs a test. New rules need a fixture.
- Say what you verified, not just what you changed.

## Code of conduct

Be decent to each other. Assume the person filing the awkward bug report is
trying to help. Maintainers may remove comments and contributors that make this
a worse place to work.

## License

Contributions are made under the MIT license, the same as the project.
