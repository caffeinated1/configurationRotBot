# configurationRotBot

**An open-source agent skill that finds and fixes configuration rot — the drift
between how your project is configured and how its ecosystem actually works
today.**

MIT licensed. Works in Claude Code, as a GitHub Action, or as a plain Python
script with no dependencies at all.

---

## The problem

Projects don't rot because their code goes wrong. They rot because the ground
underneath moves and the project doesn't move with it.

A repo that was idiomatic in 2022 is, today, running an end-of-life Node
runtime, pinning a GitHub Action that no longer exists, carrying an
`.eslintrc.json` that ESLint 9 silently ignores — so lint passes while checking
nothing — declaring `engines.node: ">=14"` while CI tests on 20 and the
Dockerfile builds on 18, and depending on four packages whose maintainers
archived them years ago.

None of this is a bug. Nothing is red. Everything works, right up until the
upgrade that should have been six small steps is one impossible one.

## Why another tool

Dependabot and Renovate already bump version numbers, and they do it well. What
they leave behind is **the config migration the bump requires**.

Renovate will happily raise ESLint 8 → 9 as a one-line diff. That diff breaks
your lint step, because ESLint 9 made flat config mandatory and ignores your
existing `.eslintrc` without an error. Nothing in the existing ecosystem does
the second half of that job — and the second half needs judgment, reads code,
and differs per repo, which is exactly the shape of work an agent is good at and
a rules engine is not.

So this project sits on top of the version bumpers rather than competing with
them. It will even tell you to install one if you haven't.

|  | Dependabot / Renovate | `npm audit` / Snyk | Linters | **configurationRotBot** |
|---|---|---|---|---|
| Bumps versions | ✅ | — | — | defers to them |
| Known CVEs | — | ✅ | — | delegates to native tools |
| **EOL runtimes and base images** | — | — | — | ✅ |
| **Deprecated config formats** | — | — | — | ✅ |
| **Contradictory version declarations** | — | — | — | ✅ |
| **Dead config nobody reads** | — | — | — | ✅ |
| **Performs the migration** | — | — | — | ✅ |

## The six rots

| | Category | What it means |
|---|---|---|
| 📉 | **DRIFT** | Behind current. Deliberately under-reported — Renovate owns this |
| 🪦 | **DECAY** | Past end-of-life, or deprecated upstream |
| 🧹 | **CRUFT** | Config and dependencies that no longer affect anything |
| ☣️ | **HAZARD** | Known vulnerabilities and archived packages |
| ⚔️ | **DIVERGENCE** | Two files in your repo disagreeing about the same truth |
| 🧊 | **STAGNATION** | The ecosystem adopted a standard you never picked up |

**DIVERGENCE and STAGNATION are the two no other tool reports.** DIVERGENCE is
nearly free to detect and almost always a real latent bug. STAGNATION is where
"reinvigorate my app" actually lives.

---

## Quick start

### As a Claude Code skill (no infrastructure)

```bash
curl -fsSL https://raw.githubusercontent.com/caffeinated1/configurationRotBot/main/install.sh | sh
```

Installs the skill into `.claude/skills/`, writes an empty starter
`CONFIGROT.md`, and runs a first scan. Needs Python 3.9+ and nothing else — no
sudo, no writes outside the target directory. Re-run it to update; it leaves an
edited policy alone. `--uninstall` reverses it.

Reading a script before piping it into a shell is a good habit, and
[`install.sh`](install.sh) is written to be read.

Prefer to do it by hand:

```bash
git clone --depth 1 https://github.com/caffeinated1/configurationRotBot /tmp/crb
mkdir -p .claude/skills && cp -r /tmp/crb/skills/config-rot .claude/skills/
```

Then ask Claude Code:

> Check this repo for configuration rot and tell me what to fix first.

It scans, prioritizes into a remediation *sequence* rather than a list, and —
if you ask it to — performs the migrations, verifying with your own build and
tests between each one.

### As a plain script (no Claude, no dependencies)

```bash
python3 skills/config-rot/scripts/scan.py --repo /path/to/your/project
```

Python 3.9+, standard library only, offline by default, and it never writes to
the repository it is scanning. Add `--online` to check registries and run your
ecosystem's native audit tool.

```
--format markdown|json|summary   output shape (default: markdown)
--json PATH                      also write machine-readable findings
--categories DECAY,DIVERGENCE    narrow the scan
--exclude '^vendor/'             skip vendored or example projects (repeatable)
--min-severity medium            raise the floor
--exit-zero                      always exit 0
```

Exit code encodes the worst severity found (0 none · 1 low · 2 medium · 3 high ·
4 critical) so it composes in a shell pipeline.

### As a GitHub Action (scan only)

```yaml
- uses: actions/checkout@v4
- uses: caffeinated1/configurationRotBot@main   # pin to a tag once one is cut
  with:
    online: true
    fail-on: never   # then ratchet: critical → high → medium
```

Posts the report to the job summary. Full template in
[`templates/config-rot-scan.yml`](templates/config-rot-scan.yml).

---

## Is it a live agent?

Yes — but "live agent" here means *a scheduled agent with memory and a budget*,
not a hosted service. There is nothing to sign up for and no server to trust
with standing access to your code.

Three tiers, each a superset of the last. **You can start at Tier 0 and stay
there forever.**

### Tier 0 — on demand
Drop the skill in `.claude/skills/` and ask. Zero infrastructure, works offline,
nothing is granted any autonomy.

### Tier 1 — scheduled *(recommended)*
A weekly GitHub Actions workflow runs the agent, which makes one verified change
and opens a pull request. GitHub is the scheduler, the compute, the audit log
and the review UI.

Copy [`templates/config-rot-agent.yml`](templates/config-rot-agent.yml), add
`ANTHROPIC_API_KEY` to your repository secrets, and write a `CONFIGROT.md`.

PRs are batched by category and blast radius — one PR that migrates ESLint
config, a separate one that moves the Docker base image. Mixed PRs are how
automated maintenance gets ignored: a reviewer who can't hold the whole diff in
their head clicks away.

### Tier 2 — continuous keeper
Tier 1 plus persistent memory of what was tried and what failed, a hard PR
budget, and optional auto-merge for the narrow class of changes that are
mechanically verifiable. Set `mode: keeper` in `CONFIGROT.md`.

---

## CONFIGROT.md — the safety mechanism

Autonomy is only tolerable if your repo can say *no* in advance, in a place the
agent will always read.

```yaml
---
mode: scheduled              # off | ondemand | scheduled | keeper
max_open_prs: 3
max_prs_per_week: 5
auto_merge: []               # [] requires human review on everything
never_touch: ["terraform/**", "charts/**"]
verify: ["npm ci", "npm run lint", "npm test", "npm run build"]
suppress: []
---

## Constraints

- Pinned to Node 20 until the Q3 platform migration; the vendor SDK is not
  certified above 20. Revisit after 2026-10-01.
- Do not migrate away from Jest. We know Vitest is faster; the team decided the
  churn isn't worth it this year.
```

The prose section is deliberate. Real constraints have *reasons*, reasons don't
fit in YAML, and an agent can act correctly on a reason in a way a rules engine
cannot. Start from
[`CONFIGROT.template.md`](skills/config-rot/assets/CONFIGROT.template.md).

Two fields carry most of the weight. `never_touch` is a hard boundary. `verify`
is what makes the guarantee below real.

## The ratchet

> **Every run leaves the repo greener or unchanged, never redder.**

Concretely: take a baseline with your own commands before touching anything;
change one class of thing per commit; re-verify after each; revert anything that
fails and record *why* in `.configrot/state.json` so the next run doesn't walk
into the same wall.

And never buy a green build with coverage — no skipped tests, no `@ts-ignore`,
no `--legacy-peer-deps`, no `continue-on-error`. Every one of those converts a
visible problem into an invisible one, which is the disease being treated. Most
of the rot you are looking at started as somebody's temporary workaround.

## The rot index

A 0–100 score where **lower is better** — it's debt, not a grade.

The absolute number means little across repos; a monorepo will always score
worse than a library. **The trend within one repo is the whole point.** History
lives in `.configrot/state.json`, so the report can say "58 → 41 since last
month", and so a CI gate can ratchet on regression rather than fail against an
arbitrary threshold. A threshold either blocks a team on day one or never fires.

---

## How it works

```
CONFIGROT.md ──▶ scan.py (deterministic, offline, read-only)
                       │
                       ▼  findings.json
                 SKILL.md (the agent: triage → sequence → migrate → verify)
                       │
        ┌──────────────┼──────────────┐
        ▼              ▼              ▼
  ROT-REPORT.md   verified edits   .configrot/state.json
```

**Deterministic scanners find evidence. The agent supplies judgment.**

`scan.py` reads the repo and emits findings with file-and-line evidence. It
never guesses and never edits. The agent never reports a finding the scanner
didn't substantiate. That split is what makes the output trustworthy: when the
report says "Node 18 is EOL", a tool proved it — the model didn't recall it.

Four properties the scanner holds to, all of them checked by the test suite:

- **No dependencies.** A tool that diagnoses dependency rot cannot require
  `pip install`.
- **Read-only.** Safe to run in CI, in a pre-commit hook, or on code you
  haven't read.
- **Offline by default.** Bundled EOL and rule data. `--online` is opt-in.
- **Loud about gaps.** If `npm` isn't on PATH, the advisory check didn't run and
  the report says so. A scan that silently checks nothing manufactures
  confidence, which is worse than no scan.

## Repository layout

```
SPEC.md                          design document — read this to understand the why
skills/config-rot/
  SKILL.md                       the agent skill
  references/                    nine docs, loaded on demand per ecosystem
  scripts/scan.py                the scanner
  scripts/detectors/             one file per detector
  data/eol.json                  EOL dates, refreshed from endoflife.date
  data/rules.json                declarative deprecation rules ← easiest contribution
  data/abandoned.json            archived-package catalogue
  assets/                        report and policy templates
templates/                       copy-paste workflows for Tier 0.5 and Tier 1
examples/rotten-repo/            deliberately rotten fixture
tests/                           62 tests, standard library only
install.sh                       one-command installer
action.yml                       the composite GitHub Action
```

## Contributing

The highest-leverage contribution is a **rule** — five lines of JSON in
`data/rules.json`, no Python required:

```jsonc
{
  "id": "STAGNATION.foo-config-rename",
  "category": "STAGNATION",
  "severity": "high",
  "when": {
    "dependency": {"name": "foo", "version_gte": "4.0.0"},
    "file_exists": ["foo.config.js"],
    "file_absent": ["foo.config.mjs"]
  },
  "title": "foo 4 ignores foo.config.js — your configuration is not being applied",
  "recommendation": "Rename to foo.config.mjs and convert to ESM export syntax.",
  "effort": "small", "autofix": "assisted", "covers": ["foo"],
  "references": ["https://foo.dev/migration/v4"]
}
```

Deprecation patterns move faster than any code release, which is why they are
data rather than code. See
[`references/writing-rules.md`](skills/config-rot/references/writing-rules.md)
for the condition grammar, and [`CONTRIBUTING.md`](CONTRIBUTING.md) for
everything else.

```bash
for t in tests/test_*.py; do python3 "$t" || break; done
```

## Status

**v1.0.0** — merged and CI-green. Node, Python, Go, Rust, Docker and GitHub
Actions coverage; Tiers 0 through 2.

Release tags are not yet pushed, so examples above reference `main`. Once `v1`
and `v1.0.0` exist, pin to them instead. See [CHANGELOG.md](CHANGELOG.md) for
what is in this release and, just as importantly, what is not.

Next up: JVM, Ruby and PHP detectors, per-workspace monorepo scoring, and
Terraform and Kubernetes. Roadmap and open design questions are in
[SPEC.md](SPEC.md#8-roadmap).

## Also in this repository: Community Goal

[`community-goal/`](community-goal/README.md) is a separate deliverable that
shares this repository's stdlib-only, no-dependency approach: an interactive
site and open JSON API built from a civic guide, *"A town's first data center:
what to require before saying yes."*

- **Site:** https://caffeinated1.github.io/configurationRotBot/
- **API:** `api/v1/` — 10 sections, 71 requirements, 18 checkable claims, all
  static JSON, no key and no rate limit.

It answers a different question than the scanner does — what a community should
require before approving a data center, and how much of that is actually
written down — but the shape is the same: data as the source of truth, a build
that fails on a broken reference, and no runtime to keep alive.

**It is open to contributors who are not developers**, which is most of the
people who know this subject: town and county staff, planning boards, state
agencies, consumer advocates, NGOs, law school clinics, engineers, and land use
counsel. The two highest-leverage contributions are citing a claim (18 of 18
carry no primary source, and coverage is published rather than hidden) and
adding a jurisdiction overlay that attaches your local statutes to the
requirements they govern. Issue forms cover both without touching JSON. See
[`community-goal/CONTRIBUTING.md`](community-goal/CONTRIBUTING.md) and
[`community-goal/GOVERNANCE.md`](community-goal/GOVERNANCE.md), which sets the
conflict-of-interest rule everyone works under.

## License

MIT. See [LICENSE](LICENSE).
