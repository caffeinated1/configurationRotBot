## What this changes

<!-- One or two sentences. -->

## Why

<!-- The failure mode, or the deprecation that prompted it. -->

## Checks

- [ ] `for t in tests/test_*.py; do python3 "$t" || break; done` passes
- [ ] No third-party imports in `skills/config-rot/scripts/`
- [ ] No finding id was renamed or reused (users suppress by id)
- [ ] Any new rule carries a title, detail, recommendation, and references
