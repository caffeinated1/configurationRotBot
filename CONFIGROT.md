---
mode: ondemand

# examples/ holds deliberately rotten fixture projects used to exercise the
# detectors. Their rot is the point, and it is not this repository's rot.
exclude:
  - "^examples/"

verify:
  - "python3 tests/test_scan.py"
  - "python3 tests/test_rules.py"

auto_merge: []
suppress: []
---

## Constraints

- `skills/config-rot/scripts/` must stay standard-library only and Python 3.9+
  compatible. A tool that diagnoses dependency rot cannot acquire dependencies.
- `scan.py` must never write to the repository under scan. The read-only
  guarantee is what makes it safe to run in CI and against untrusted code.
- Finding ids in `data/rules.json` are a public interface — users suppress by id.
  Add a new id rather than renaming an existing one.
