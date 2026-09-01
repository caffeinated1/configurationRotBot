# Safe remediation

Read this before the first edit. Most failed modernization attempts fail the
same way: someone changes six things at once, something breaks, nobody can tell
which change caused it, and the whole branch gets abandoned. The repo is then
worse off than before, because the team now believes modernizing is dangerous.

## The ratchet

**Every run leaves the repo greener or unchanged, never redder.**

This is the whole discipline in one line. Everything below is mechanics for
keeping it true.

## 1. Baseline before you touch anything

Run the repo's own verification and record the result:

```bash
npm ci && npm run lint && npm test && npm run build     # or the repo's equivalent
```

Take `verify` from `CONFIGROT.md` if it exists. Otherwise infer from the CI
workflow — CI is the definition of "working" that the team actually agreed on,
better than anything in a README.

If the baseline is already red, say so explicitly and loudly. Do not start
fixing. A pre-existing failure that you don't know about will get attributed to
your change, and you will spend an hour chasing it — or worse, "fix" it in a way
that masks a real bug.

## 2. One class of change per commit

Not "modernize the build". Instead:

```
migrate ESLint to flat config
move Docker base image to Node 22
reconcile Node version declarations
```

Each commit should be independently revertable and independently explainable. A
reviewer who cannot hold the diff in their head will not review it, and an
unreviewed maintenance PR sits open until it conflicts and gets closed.

## 3. Verify after each one

Re-run the same commands. Compare against the baseline, not against "green" —
if three tests were failing before and three are failing after, and they are the
same three, you have not regressed.

## 4. Revert, don't wrestle

If a change fails verification and you cannot fix it within the effort the
finding claimed, **revert it**. Then record in `.configrot/state.json`:

```json
{
  "attempts": {
    "STAGNATION.create-react-app": {
      "date": "2026-09-01",
      "outcome": "abandoned",
      "reason": "Vite migration blocked: three internal packages import from
                 'react-scripts/config/env' directly. Needs owner decision.",
      "retry_after": "2027-01-01"
    }
  }
}
```

A failed attempt with a recorded reason is a genuinely useful output. A
half-migrated repo is not. And without the record, a scheduled agent retries the
same dead end every week forever.

## 5. Never buy green with coverage

Do not, to make a migration pass:

- skip, delete, or `.only` a test
- add `// @ts-ignore`, `# type: ignore`, or `eslint-disable` at file scope
- loosen a compiler or linter setting (`strict: false`, `ignoreErrors: true`)
- add `--force`, `--legacy-peer-deps`, or `continue-on-error: true`
- pin a transitive dependency to dodge a conflict rather than resolving it

Every one of these converts a visible problem into an invisible one. That is
precisely the disease being treated here — most of the rot you are looking at
started as somebody's temporary workaround.

If a migration genuinely requires one of these, it is not a `safe` or `assisted`
change any more. Stop, revert, and report it as `manual` with the reason.

## 6. Respect the policy

`never_touch` paths are a hard boundary. Do not edit files under them, do not
propose edits to them, and do not route around them by changing something
adjacent that has the same effect.

Prose constraints in `CONFIGROT.md` are equally binding. "We're staying on Node
20 until the vendor SDK is certified" means Node 20 findings get reported as
suppressed context, not acted on.

## 7. What "verified" means per change type

| Change | Minimum verification |
|---|---|
| Version pin file (`.nvmrc` etc.) | Install and build on the new version |
| Package manager / lockfile | Clean install from scratch, then full test suite |
| Linter config migration | Lint runs, reports a comparable rule count, and still catches a deliberate violation |
| Framework major | Full test suite plus a manual smoke of the primary user path |
| Dockerfile base image | Image builds and the container starts |
| CI workflow | The workflow actually runs — a YAML change that only "looks right" is unverified |
| Deleting config | Build, test, and lint all still pass; grep for the filename across the repo first |

That linter row deserves emphasis. A flat-config migration that produces zero
errors usually means the config is not matching any files, not that the code is
clean. Introduce a deliberate violation and confirm it is caught before
believing the migration worked.

## 8. Order of operations

Reconcile DIVERGENCE → runtimes → package manager → build/test tooling →
framework majors → HAZARD cleanup → CRUFT. The reasoning is in SKILL.md §3. The
short version: you cannot verify anything until the tools that do the verifying
work, and you should not delete anything until you know what still uses it.
