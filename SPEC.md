# ConfigurationRotBot — Specification

**Status:** v0.1 (draft, implemented)
**License:** MIT
**Repo:** https://github.com/caffeinated1/configurationRotBot

---

## 1. The problem

Software projects do not rot because their code is wrong. They rot because the
*ground underneath the code* moves and nobody moves with it.

A repo that was idiomatic in 2022 is, in 2026, quietly running an EOL Node
runtime, pinning a deprecated GitHub Action, carrying an `.eslintrc.json` that
ESLint 9 silently ignores, declaring `engines.node: ">=14"` while CI tests on 20
and the Dockerfile builds on 18, and depending on four packages whose
maintainers archived them. None of this is a bug. Nothing is red. Everything
still works — until the day it very suddenly doesn't, and the upgrade that
should have been six small steps is now one impossible one.

This is **configuration rot**: the accumulated drift between how a project is
configured and how its ecosystem currently works.

### 1.1 Why existing tools don't solve it

| Tool | What it does | What it leaves behind |
|---|---|---|
| Dependabot / Renovate | Bumps version numbers in manifests | The config migration the bump *requires*; anything not in a manifest |
| `npm audit`, `pip-audit`, Snyk | Finds known CVEs | Everything non-security: EOL runtimes, dead config, deprecated idioms |
| Linters | Enforce rules you already configured | Rules you never adopted because they didn't exist when you set it up |
| Renovate presets | Config-as-code for bumping | No opinion on whether your stack's *shape* is still current |

The unfilled niche is the **migration and modernization layer that sits on top of
the version bumper**. Bumping ESLint 8 → 9 is a one-line diff that Renovate does
happily; it breaks your lint step because flat config is now mandatory. Nothing
in the existing ecosystem does the second half. That second half needs judgment,
reads code, and adapts per repo — which is exactly the shape of work an agent is
good at and a rules engine is not.

### 1.2 Design thesis

> Deterministic scanners find *evidence*. An agent supplies *judgment*.
> Keep those two things in separate boxes and you get a tool that is both
> trustworthy and capable.

Everything in this spec follows from that split. The scanner never guesses and
never edits. The agent never invents findings the scanner didn't substantiate.

---

## 2. Taxonomy: the six rots

Every finding is classified into exactly one category. The taxonomy exists so
that severity, automation-safety, and remediation strategy can be reasoned about
per-class rather than per-finding.

| Code | Category | Definition | Example |
|---|---|---|---|
| **DRIFT** | Behind current | A dependency or tool is N versions/releases behind current | `react@17` when 19 is current |
| **DECAY** | Deprecated or EOL | Something is past end-of-life or formally deprecated upstream | Node 16 base image; `actions/checkout@v2` |
| **CRUFT** | Dead weight | Config or dependency that no longer affects anything | `.babelrc` in a repo with no Babel; unused deps |
| **HAZARD** | Actively unsafe | Known vulnerability, abandoned/unmaintained package, or supply-chain risk | `request@2` (archived); a CVE'd transitive |
| **DIVERGENCE** | Self-contradiction | Two config surfaces in the same repo declare different truths | `.nvmrc` says 18, CI matrix says 20, `engines` says >=14 |
| **STAGNATION** | Ecosystem moved on | The ecosystem adopted a new standard the repo never picked up | Still on `.eslintrc` under ESLint 9; CJS-only in an ESM world |

**DIVERGENCE and STAGNATION are the two categories no existing tool reports.**
They are the reason this project exists. DIVERGENCE is cheap to detect
mechanically and almost always indicates a real latent bug. STAGNATION is where
"reinvigorate my app" actually lives.

### 2.1 Severity

Severity is computed, not assigned by vibes:

```
severity = f(blast_radius, time_pressure, exploitability)
```

- **critical** — Known-exploitable vulnerability, or the thing is *already*
  broken/EOL and unsupported today.
- **high** — EOL within 90 days; build/deploy will break on the next upstream
  release; DIVERGENCE that can produce different behavior across environments.
- **medium** — Meaningfully behind; deprecated with a working shim; STAGNATION
  with a clear migration path.
- **low** — Cosmetic drift, CRUFT, nice-to-have modernization.

### 2.2 Effort and automation safety

Every finding also carries two orthogonal fields that gate what the live agent
is allowed to do unattended:

- `effort`: `trivial` | `small` | `medium` | `large` | `epic`
- `autofix`: `safe` (mechanical + verifiable) | `assisted` (agent can do it, human
  should review) | `manual` (needs a human decision first)

A `safe` + `trivial` finding is the only kind eligible for auto-merge, and only
when the repo's policy opts in. See §6.

---

## 3. Architecture

```
                    ┌────────────────────────────┐
                    │  CONFIGROT.md  (policy)    │  ← repo owner's constraints
                    └────────────┬───────────────┘
                                 │
   repo files ──▶ ┌──────────────▼──────────────┐
                  │  scan.py  (deterministic)   │  no LLM, no network by default
                  │  ├─ inventory               │  stdlib only, exit code = worst sev
                  │  ├─ detectors/*             │
                  │  └─ score                   │
                  └──────────────┬──────────────┘
                                 │  findings.json  (stable schema)
                                 ▼
                  ┌─────────────────────────────┐
                  │  SKILL.md  (the agent)      │  triage → plan → migrate → verify
                  │  + references/*  loaded     │
                  │    on demand per ecosystem  │
                  └──────────────┬──────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              ▼                  ▼                  ▼
      ROT-REPORT.md      code/config edits    .configrot/state.json
      (human-readable)   (verified by the      (trend + suppressions
                          repo's own tests)     + what was tried)
```

### 3.1 Hard boundaries

1. **`scan.py` never writes to the repo.** It reads and emits JSON. This makes it
   safe to run in CI, in a pre-commit hook, on someone else's repo, or from a
   README one-liner.
2. **`scan.py` has zero dependencies.** Python 3.9+ stdlib only. The moment a
   rot-detector needs `pip install` it has become part of the problem.
3. **`scan.py` is offline by default.** Bundled EOL and rules data means a useful
   scan with no network. `--online` enriches with live registry data.
4. **The agent may not report a finding the scanner did not produce**, except in
   a clearly-labelled `Observations` section. This is the anti-hallucination
   guardrail: if a claim is in the findings table, a deterministic tool
   substantiated it.
5. **No remediation ships without verification.** The agent runs the repo's own
   build/test/lint commands before and after. Red-before is recorded; red-after
   is reverted.

### 3.2 The ratchet

Every run must leave the repo **greener or unchanged, never redder.** This single
invariant is what makes autonomous operation tolerable. Practically it means:

- Establish the baseline first (does the build pass *before* I touch anything?).
- Change one class of thing per commit, verify, then proceed.
- If verification fails and can't be fixed within the finding's stated effort,
  revert that change and downgrade the finding to `manual` with notes on what
  went wrong — recorded in `.configrot/state.json` so the next run doesn't
  retry the same dead end.

That last clause matters more than it looks. Without memory, a scheduled agent
re-attempts the same impossible upgrade every week forever.

---

## 4. Finding schema

`findings.json` is the contract between scanner and agent. It is versioned.

```jsonc
{
  "schema_version": "1.0",
  "generated_at": "2026-09-01T12:00:00Z",
  "repo": { "root": ".", "ecosystems": ["node", "github-actions", "docker"] },
  "rot_index": { "overall": 62, "by_category": { "DECAY": 40, "DRIFT": 71 } },
  "findings": [
    {
      "id": "DECAY.node-eol.dockerfile",     // stable across runs → dedupe/suppress
      "category": "DECAY",
      "severity": "high",
      "title": "Dockerfile builds on Node 18, which reached end-of-life 2025-04-30",
      "evidence": [
        { "file": "Dockerfile", "line": 1, "text": "FROM node:18-alpine" }
      ],
      "detail": "Node 18 no longer receives security patches...",
      "recommendation": "Move to node:22-alpine (Active LTS until 2027-04).",
      "effort": "small",
      "autofix": "assisted",
      "blast_radius": ["build", "runtime"],
      "references": ["https://endoflife.date/nodejs"],
      "detector": "eol",
      "confidence": "high"
    }
  ],
  "skipped": [ { "detector": "audit", "reason": "npm not on PATH" } ]
}
```

**Design notes.**

- `id` is deterministic and content-addressed by *what* is wrong and *where* —
  not by version numbers — so a finding survives partial remediation and can be
  suppressed durably in policy.
- `evidence` is mandatory and must be file+line. A finding without evidence is a
  bug in the detector.
- `skipped` is as important as `findings`. Silent partial scans are how people
  come to trust a tool that isn't actually looking. If `npm` isn't installed, say
  so, loudly, in the report.
- `confidence` lets heuristic detectors (unused-dependency scanning is
  necessarily heuristic) participate without polluting the high-trust set.

### 4.1 Rot Index

A 0–100 score where **lower is better** (it's debt, not a grade). Per category:

```
category_score = min(100, Σ severity_weight(f) for f in category_findings)
severity_weight = {critical: 40, high: 15, medium: 5, low: 1}
overall = weighted mean, HAZARD and DECAY double-weighted
```

The absolute number is nearly meaningless across repos. **The trend within one
repo is the whole point** — `.configrot/state.json` retains history so the report
can say "58 → 41 since last month" and so a CI gate can fail on regression
rather than on an arbitrary threshold. Ratchets beat thresholds: a threshold
either blocks a team on day one or never fires.

---

## 5. Detectors

All detectors live in `skills/config-rot/scripts/detectors/` and share one
interface: given an inventory, return findings. Adding an ecosystem means adding
one file — this is the primary contribution path for the community.

| Detector | Category emphasis | Network | Notes |
|---|---|---|---|
| `inventory` | — | no | Discovers manifests, lockfiles, CI, containers, version pins |
| `eol` | DECAY | no | Bundled `data/eol.json` (endoflife.date-derived); `--online` refreshes |
| `rules` | DECAY, STAGNATION | no | Declarative `data/rules.json` pattern rules; the community-extensible surface |
| `divergence` | DIVERGENCE | no | Cross-file version-truth reconciliation. Highest signal-to-noise detector |
| `cruft` | CRUFT | no | Orphan configs, unused deps (heuristic), multiple lockfiles, dead scripts |
| `abandoned` | HAZARD | no | Bundled list of archived/deprecated-upstream packages + replacements |
| `drift` | DRIFT | **yes** | Registry latest-version comparison (npm, PyPI, crates.io, Go proxy) |
| `audit` | HAZARD | **yes** | Shells out to native tooling if present; never bundles its own CVE DB |

### 5.1 Why `rules.json` is declarative

Deprecation patterns are the fastest-moving and most community-shaped part of
this problem. Making them data rather than code means a contributor who knows
that Vite 6 dropped some option can open a five-line PR without reading any
Python. The rule format:

```jsonc
{
  "id": "STAGNATION.eslint-flat-config",
  "category": "STAGNATION",
  "severity": "medium",
  "when": {
    "dependency": { "name": "eslint", "version_gte": "9.0.0" },
    "file_exists": [".eslintrc", ".eslintrc.js", ".eslintrc.json"]
  },
  "title": "ESLint 9 ignores .eslintrc — your lint rules are not running",
  "recommendation": "Migrate to eslint.config.js flat config.",
  "effort": "medium", "autofix": "assisted",
  "references": ["https://eslint.org/docs/latest/use/configure/migration-guide"]
}
```

### 5.2 Divergence detection

The detector reconciles every declaration of the same underlying truth:

**Node version truth** is declared in up to seven places — `engines.node`,
`.nvmrc`, `.node-version`, `.tool-versions`, CI `node-version` matrices,
`FROM node:` in Dockerfiles, and `volta.node`. **Python version truth** in
`requires-python`, `.python-version`, `.tool-versions`, CI matrices,
`FROM python:`, `[tool.ruff] target-version`, `[tool.black] target-version`,
`[tool.mypy] python_version`. Package-manager truth in `packageManager`, which
lockfiles exist, and what CI actually invokes.

When these disagree, something is wrong — either a bug waiting for an
environment difference to surface it, or a stale file nobody updated. Both are
worth a finding. This check requires no network, no registry, and no
version-currency knowledge, which makes it the most durable detector in the set.

---

## 6. Deployment tiers — "is it a live agent?"

Yes, but "live agent" should mean *a scheduled agent with memory and a budget*,
not a hosted service. Three tiers, each a superset of the last. **A repo should
be able to start at Tier 0 and never be forced upward.**

### Tier 0 — On-demand skill

Drop `skills/config-rot/` into `.claude/skills/`, then ask Claude Code to check
for configuration rot. Zero infrastructure, zero trust required, works offline.
This is the adoption on-ramp and must stay genuinely useful alone.

### Tier 1 — Scheduled agent (the recommended "live" mode)

A GitHub Actions workflow on a weekly cron runs Claude Code headless with the
skill and opens a PR per remediation batch. "Live" without hosting anything:
GitHub is the scheduler, the compute, the audit log, and the review UI.

Batching is by *category and blast radius*, not by package — one PR that
migrates ESLint config, a separate PR that moves the Docker base image. Mixed
PRs are how automated maintenance gets ignored: a reviewer who can't hold the
whole diff in their head clicks away.

### Tier 2 — Continuous keeper

Tier 1 plus:
- **Policy** (`CONFIGROT.md`) — the repo owner's constraints in the repo itself.
- **Budget** — max open PRs and max PRs/week, so the bot cannot flood a repo.
- **Memory** (`.configrot/state.json`) — what was tried, what failed and why,
  what's suppressed until when.
- **Graduated autonomy** — auto-merge `safe`+`trivial` when CI is green *and*
  the policy opts in; everything else waits for a human.

### 6.1 The policy file is the safety mechanism

Autonomy is only tolerable if the repo can say *no* in advance, in a place the
agent will always read. `CONFIGROT.md` is prose plus front-matter, deliberately —
constraints like "we're pinned to Node 20 until the Q3 platform migration
because the vendor SDK hasn't been certified" cannot be expressed as YAML, and
an agent can act correctly on the prose.

```yaml
---
mode: scheduled            # off | ondemand | scheduled | keeper
max_open_prs: 3
max_prs_per_week: 5
auto_merge: [safe]         # [] to require human review on everything
never_touch: ["terraform/**", "charts/**"]
verify: ["npm ci", "npm run lint", "npm test", "npm run build"]
---

## Constraints
- Pinned to Node 20 until the Q3 platform migration; the vendor SDK is not
  certified above 20. Revisit after 2026-10-01.
- Do not migrate away from Jest. We know Vitest is faster; the team decided the
  churn isn't worth it this year.
```

`never_touch` and `verify` are the two fields that matter most in practice. The
first is a hard boundary; the second is what makes the ratchet real.

### 6.2 What this deliberately is *not*

- **Not a hosted SaaS.** No server to trust with repo access, no account, no
  pricing page. The value is the skill and the detector data; anything requiring
  a backend would fragment the community into users and customers.
- **Not a version bumper.** It defers to Renovate/Dependabot for DRIFT and says
  so in the report. Competing with them on their own ground is a losing,
  redundant fight; sitting on top of them is a moat.
- **Not a linter.** Findings are about the project's *configuration surface*, not
  its source code style.

---

## 7. Output contract

Two artifacts, for two audiences:

- **`findings.json`** — machine-readable, stable schema, for CI gates and other
  tools. Exit code encodes worst severity so it composes in a shell pipeline.
- **`ROT-REPORT.md`** — for the human. Executive summary, rot index with trend,
  findings grouped by category and sorted by severity, a proposed remediation
  sequence in dependency order, and an explicit "what I could not check and why"
  section.

The remediation sequence is the part people actually use. Upgrades have a
partial order — you move the runtime before the framework that requires it,
and the package manager before the lockfile — and getting that order wrong is
the most common way a modernization attempt stalls halfway and gets reverted.

---

## 8. Roadmap

**v0.1 (this release)** — Skill, deterministic scanner, six detectors, Node /
Python / Go / Rust / Docker / GitHub Actions coverage, Tier 0 + Tier 1, policy
file, report format.

**v0.2** — Tier 2 keeper with budget enforcement and suppression expiry;
JVM (Maven/Gradle), Ruby, PHP, .NET detectors; `--online` drift enrichment for
all registries; pre-commit hook mode.

**v0.3** — Terraform / Kubernetes / Helm; monorepo awareness (per-workspace
scoring); `rot-index` badge; GitLab CI and a generic-cron adapter so the
project isn't GitHub-shaped forever.

**Ongoing** — `data/rules.json` and `data/eol.json` are the living surface. The
project's long-term health is measured by whether outside contributors are
adding rules, because that is the part that decays fastest.

---

## 9. Open questions

1. **Suppression expiry default.** Permanent suppressions become the new rot.
   Proposal: suppressions expire after 180 days and must be re-affirmed.
2. **Monorepo scoring.** One index for the repo, or per-workspace? Probably per-
   workspace with a roll-up, but it complicates the trend line.
3. **Registry rate limits.** `--online` across a large dependency tree will get
   throttled. Needs a cache in `.configrot/` with a TTL.
4. **How opinionated should STAGNATION be?** "You should move off Jest" is
   useful to some teams and obnoxious to others. Current answer: emit it at
   `low`/`medium` with an easy policy opt-out, and never auto-fix it.
