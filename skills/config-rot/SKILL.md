---
name: config-rot
description: Detect and repair configuration rot — the drift between how a project is configured and how its ecosystem currently works. Finds EOL runtimes, deprecated config formats, contradictory version declarations across .nvmrc/CI/Dockerfile/engines, dead tooling config, abandoned packages, and missed ecosystem migrations, then performs the migrations with verification. Use this whenever the user wants to modernize, refresh, revive, upgrade, or "reinvigorate" a project, asks why an old repo feels stale or is hard to build, mentions tech debt, outdated dependencies, EOL versions, legacy config, upgrading a framework or runtime, or asks to audit/health-check a codebase's setup — even if they don't use the words "configuration rot". Also use before a major version upgrade to find what will break first.
license: MIT
---

# Configuration Rot

Projects don't rot because their code goes wrong. They rot because the ground
underneath moves and the project doesn't move with it. A repo that was idiomatic
three years ago is now running an EOL runtime, pinning deprecated CI actions,
carrying an `.eslintrc.json` that ESLint 9 silently ignores, and declaring three
different Node versions in three different files. Nothing is red. Everything
works — until the upgrade that should have been six small steps is one
impossible one.

Your job is to find that drift with evidence, and close it without breaking
anything.

## The one rule that makes this work

**Deterministic scanners find evidence. You supply judgment.**

`scripts/scan.py` reads the repo and emits findings with file+line evidence. It
never guesses and never edits. You never report a finding it didn't
substantiate. This split is what makes the output trustworthy — when a user
reads "Node 18 is EOL" in your report, a tool proved it, you didn't recall it.

If you notice something real that the scanner missed, that's valuable — put it
under a clearly-labelled **Observations** heading, separate from the findings
table, and consider whether it should become a rule in `data/rules.json`.

## Workflow

### 1. Scan first, always

```bash
python3 skills/config-rot/scripts/scan.py --repo . --json .configrot/findings.json
```

Adjust the path to wherever the skill lives. Useful flags:

- `--online` — also check registries for how far behind dependencies are (DRIFT).
  Skip it when offline or when the user only wants the structural problems.
- `--categories DECAY,DIVERGENCE` — narrow the scan.
- `--format markdown` — human-readable straight to stdout.

Exit code encodes the worst severity found (0 clean, 1 low, 2 medium, 3 high,
4 critical) so it composes in CI.

Read the `skipped` array in the output before anything else. If `npm` wasn't on
PATH, the audit didn't run, and a report that quietly omits that is worse than
no report. Surface every skip in your final output.

### 2. Read the policy before proposing anything

If `CONFIGROT.md` exists at the repo root, read it in full. It carries the
owner's constraints — both structured (`never_touch`, `verify`, `auto_merge`)
and prose ("pinned to Node 20 until the Q3 migration; the vendor SDK isn't
certified above it"). The prose matters as much as the YAML; it usually explains
*why* something that looks like rot is a deliberate decision.

A finding that contradicts the policy still gets reported — but as
`suppressed-by-policy`, with the reason, not as an action item. Silently
dropping it means the constraint never gets revisited when it expires.

Also read `.configrot/state.json` if present. It records what previous runs
tried and what failed. **Do not re-attempt a migration that a prior run recorded
as failing for a reason that still holds.** Without this, a scheduled agent
retries the same dead end every week forever.

### 3. Triage into a sequence, not a list

Findings come back sorted by severity, but severity is not execution order.
Upgrades have a partial order, and getting it wrong is the most common way a
modernization attempt stalls halfway and gets reverted.

The order that works:

1. **Reconcile DIVERGENCE first.** If the repo declares three Node versions, you
   cannot correctly upgrade anything until you know which one is true. Pick the
   truth (usually: what CI actually runs, because that's what's tested), and make
   the other declarations agree. This is cheap, safe, and unblocks everything.
2. **Runtimes and package managers next.** Node/Python/Go version, then the
   package manager and lockfile. Everything downstream depends on these.
3. **Build and test tooling.** Bundler, transpiler, test runner, linter — the
   things that must work for you to verify anything else.
4. **Framework and library majors.** One at a time, verified between each.
5. **HAZARD cleanup** — abandoned packages, vulnerable deps.
6. **CRUFT last.** Deleting dead config is satisfying and low-risk, but doing it
   first means you delete something you then discover was load-bearing.

Within that order, prefer the changes that unblock the most other findings. Say
so explicitly in the report — "moving to Node 22 first resolves 4 of the 11
findings below" is the sentence that gets a modernization approved.

### 4. Establish the baseline before touching anything

```bash
# whatever the repo's own verify commands are — from CONFIGROT.md, or inferred
npm ci && npm run lint && npm test && npm run build
```

Record what passes and what already fails. This is not optional ceremony. If the
test suite is already red and you don't know it, you will spend an hour
attributing a pre-existing failure to your change — or worse, ship a "fix" for
it that masks a real bug.

If the baseline is red, say so in the report and either fix that first (if
trivial and clearly in scope) or scope your changes to things you can verify
another way.

### 5. Remediate in verified increments

**The ratchet: every run leaves the repo greener or unchanged, never redder.**

For each change:

- Change **one class of thing** per commit. Not "modernize the build" — "migrate
  ESLint to flat config", then separately "move Docker base to Node 22".
- Re-run verification after each.
- If it fails and you can't fix it within the finding's stated effort, **revert
  that change** and record why in `.configrot/state.json`. A failed attempt with
  a recorded reason is a genuinely useful output; a half-migrated repo is not.
- Never disable, skip, or loosen a test, a type check, or a lint rule to make a
  migration pass. That converts a visible problem into an invisible one, which
  is the exact disease you're treating.

For migrations you haven't done before, read the relevant reference file rather
than working from memory — ecosystem migration details are precisely the kind of
thing that changes faster than any model's training data.

### 6. Report

Write `ROT-REPORT.md` using `assets/report-template.md`. The structure is fixed
because people scan these, they don't read them.

Update `.configrot/state.json` with the run's date, rot index, what you changed,
and what you tried and abandoned (with reasons). The trend line is more useful
than any absolute score.

## References — read these on demand, not upfront

Load only what the scan surfaced. Reading all of them wastes context you'll want
for the actual migration.

| File | Read when |
|---|---|
| `references/taxonomy.md` | You need severity/effort/autofix definitions, or you're classifying a finding by hand |
| `references/report-format.md` | Writing the report; contains the full template and worked examples |
| `references/safe-remediation.md` | **Before your first edit.** Verification discipline, revert protocol, what never to touch |
| `references/ecosystem-node.md` | Node, npm/pnpm/yarn, TypeScript, ESLint, bundlers, test runners |
| `references/ecosystem-python.md` | Python, pip/poetry/uv, pyproject, ruff/black/mypy, packaging |
| `references/ecosystem-infra.md` | Dockerfiles, GitHub Actions, base images, CI runners |
| `references/ecosystem-other.md` | Go, Rust, Ruby, JVM, PHP, .NET |
| `references/modernization-recipes.md` | Step-by-step for the common big migrations (CRA→Vite, eslintrc→flat, CJS→ESM, requirements.txt→pyproject, Jest→Vitest) |
| `references/writing-rules.md` | Adding a detector rule — the `rules.json` format and how to contribute one |

## Scope discipline

The user asked you to address configuration rot. That is a specific and bounded
thing: the project's *configuration surface*, not its architecture, not its code
style, not its product decisions.

Signals you've drifted out of scope: you're refactoring application logic,
you're rewriting tests to be "better", you're introducing a new library the repo
didn't ask for, you're restructuring directories. A modernization PR that also
rearranges someone's code is a PR that doesn't get merged, and the rot stays.

The inverse failure is worth naming too: don't stop at the version bump. If
moving ESLint to 9 requires a flat-config migration, the migration *is* the task
— shipping the bump alone leaves the repo lint-less and worse off than before.

## When the user just wants to know

Plenty of people want the diagnosis, not the surgery. If they asked "what's
wrong with this repo" or "is this project stale", scan and report — don't start
editing. Offer the remediation sequence and let them pick. Ask before making
changes unless they clearly asked you to fix things.

## Working without the scanner

If Python 3 isn't available or the scripts can't run, degrade gracefully rather
than abandoning the task: read manifests, CI workflows, Dockerfiles, and version
pin files directly, and apply the same taxonomy and ordering by hand. Say
clearly in the report that findings were gathered manually and are therefore
lower-confidence. A manual pass that names the three EOL runtimes is still worth
far more than an apology.
