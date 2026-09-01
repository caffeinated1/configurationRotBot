# Writing a rule

Rules live in `data/rules.json` and are pure data — no Python needed. This is
the main way to contribute to the project, because deprecation patterns move far
faster than any code release.

## When a rule is the right tool

A rule fits when the finding is: **"if this configuration exists, that is a
problem"**. If you need to compare two things against each other, compute
something, or reach the network, write a detector instead.

## Format

```jsonc
{
  "id": "STAGNATION.eslint-flat-config",   // CATEGORY.short-slug, stable forever
  "category": "STAGNATION",
  "severity": "high",
  "when": { /* conditions, ANDed */ },
  "title": "One line stating the problem, not the fix",
  "detail": "Why it matters. What actually goes wrong.",
  "recommendation": "The fix, concretely. Name the command if there is one.",
  "effort": "medium",
  "autofix": "assisted",
  "blast_radius": ["lint", "ci"],
  "confidence": "high",                    // omit for high
  "covers": ["eslint"],                    // optional: packages this fully explains
  "references": ["https://..."]
}
```

`id` is a permanent identifier. Users suppress findings by id in
`CONFIGROT.md`, so renaming one silently un-suppresses it in every repo that
had opted out. Add a new id instead.

`covers` stops `data/abandoned.json` from reporting the same package a second
time with worse advice. Add it whenever your rule is about a specific package.

## Condition grammar

All top-level keys AND together.

| Key | Meaning |
|---|---|
| `ecosystem` | `"node"` — project uses this ecosystem |
| `dependency` | `{name, present\|version_gte\|version_lt}` |
| `dependency_absent` | `["a","b"]` — none of these are dependencies |
| `dependency_any` + `count_gte` | at least N of these present |
| `file_exists` | `["a","b"]` — **any** of these paths exists |
| `file_exists_all` | all of these exist |
| `file_absent` | all of these are absent |
| `file_absent_glob` | no path matches any of these regexes |
| `file_contains` | `[{glob, pattern}]` — some file matching `glob` matches `pattern` |
| `not_file_contains` | no file matching `glob` matches `pattern` |
| `lockfile_count_gte` | N or more lockfiles committed |
| `any` | `[{...},{...}]` — OR over sub-conditions |

`glob` is a **regex matched against the repo-relative path**, not a shell glob.
`Dockerfile` matches any path containing "Dockerfile"; use `^Dockerfile$` to
match only the root one.

## Worked example

Suppose a tool renames `foo.config.js` to `foo.config.mjs` in v4 and silently
ignores the old name:

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
  "detail": "foo 4 only reads foo.config.mjs. The old file is ignored with no warning, so the tool runs on defaults while appearing configured.",
  "recommendation": "Rename to foo.config.mjs and convert to ESM export syntax.",
  "effort": "small", "autofix": "assisted", "blast_radius": ["build"],
  "covers": ["foo"],
  "references": ["https://foo.dev/migration/v4"]
}
```

Note the shape of the title: it states what is wrong and its consequence. "Use
foo.config.mjs" would be a fix masquerading as a finding.

## Writing good severities

The most common contribution mistake is rating a new rule `high` because the
contributor was recently bitten by it. Ask: what breaks, and when?

- Silently not working (config ignored, lint not running) → `high`. These are
  worse than loud failures because nobody notices.
- Loud failure → `high` or `critical`; it is already blocking someone.
- Works but deprecated with a shim → `medium`.
- Works fine, just not how people do it now → `low`.

## Testing

```bash
python3 tests/test_rules.py                  # schema and id-uniqueness checks
python3 skills/config-rot/scripts/scan.py --repo examples/rotten-repo --detectors rules
```

Add a fixture to `examples/` if your rule needs one to fire. A rule that no
fixture exercises will silently stop working and nobody will notice.

## Checklist

- [ ] `id` is `CATEGORY.slug` and unique
- [ ] Title states the problem and its consequence
- [ ] `detail` explains what actually goes wrong, not just that it is old
- [ ] `recommendation` is actionable — a command, or a named migration path
- [ ] `covers` set if the rule is about a specific package
- [ ] At least one authoritative `references` link
- [ ] `confidence: "medium"` if there is a plausible false positive
- [ ] Fires on a fixture; does not fire on a healthy repo
