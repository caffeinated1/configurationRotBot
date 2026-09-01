# Changelog

Notable changes to configurationRotBot. This project follows
[semantic versioning](https://semver.org/); the `v1` tag tracks the latest v1.x
release so `uses: caffeinated1/configurationRotBot@v1` stays current.

## v1.0.0 — 2026-09-01

First release. Merged to `main`; the `v1.0.0` and `v1` tags are not yet pushed,
so installs and Action references use `main` until they are.

### What it does

Finds and fixes **configuration rot**: the drift between how a project is
configured and how its ecosystem currently works. Six categories — DRIFT,
DECAY, CRUFT, HAZARD, DIVERGENCE, STAGNATION — of which the last two are not
reported by any existing tool.

It is deliberately complementary to Dependabot and Renovate rather than
competing with them. They bump version numbers; this handles the config
migration the bump requires, and will raise a finding telling you to install one
if you haven't.

### Added

**The skill.** `skills/config-rot/SKILL.md` plus nine reference documents loaded
on demand — per-ecosystem guidance, migration recipes, remediation discipline,
and the report format.

**The scanner.** `scripts/scan.py` with seven detectors. Python 3.9+, standard
library only, offline by default, and it never writes to the repository it
scans. Exit code encodes the worst severity found.

**Datasets.** `data/eol.json` (EOL dates, refreshable from endoflife.date),
`data/rules.json` (35 declarative deprecation rules), `data/abandoned.json`
(45 archived packages). These are the community-extensible surface: a new
deprecation is five lines of JSON, no Python.

**Ecosystems.** Node/JavaScript/TypeScript, Python, Go, Rust, Docker, GitHub
Actions. JVM, Ruby, PHP and .NET have manifest and version-declaration support
but no dedicated detectors yet.

**Three deployment tiers.**
- Tier 0 — the skill, on demand, no infrastructure.
- Tier 0.5 — `action.yml`, a read-only GitHub Action needing no API key.
- Tier 1 — `templates/config-rot-agent.yml`, a scheduled agent that makes one
  verified change and opens a PR, with budget enforcement.
- Tier 2 — the above with `mode: keeper` in `CONFIGROT.md`.

**`CONFIGROT.md`.** Policy as YAML front matter plus prose, because real
constraints have reasons and reasons don't fit in YAML.

**`install.sh`.** One-command install; POSIX sh, no sudo, no writes outside the
target directory. Re-run to update, `--uninstall` to reverse.

**Tests.** 62 tests across four files, standard library only. CI runs them on
Python 3.9, 3.11 and 3.13, self-scans this repository, installs from the commit
under test, and asserts the fixture still exercises every detector.

### Known limitations

- **Workflow YAML is read line-wise, not parsed.** There is no YAML parser in
  the standard library, and taking a dependency would break the guarantee that
  matters more. Facts extracted this way (action versions, runner labels,
  language matrices) are reliable; structural reasoning about workflows is not
  attempted.
- **Unused-dependency detection is a text search.** It is reported at `low`
  confidence and misses dynamic imports and config-referenced plugins. Verify
  with `depcheck` or `knip` before removing anything.
- **The bundled EOL dataset is a snapshot.** A weekly workflow refreshes it from
  endoflife.date and opens a PR; `scripts/refresh_data.py --check` reports drift.
- **Monorepos are scored as one repository.** Per-workspace scoring is v0.3.
- **No Terraform or Kubernetes detectors yet**, though both are recognised.

### Design notes

The rot index is compressive rather than linear: a single critical finding lands
near 30, and a thoroughly rotten repository near 90 without ever pegging at 100.
The number measures accumulated debt, not urgency — the severity counts beside
it carry urgency — and a metric stuck at its ceiling cannot show progress, which
is the only thing it is genuinely good for.

Open design questions (suppression expiry, monorepo scoring, how opinionated
STAGNATION rules should be) are tracked in [SPEC.md §9](SPEC.md).
