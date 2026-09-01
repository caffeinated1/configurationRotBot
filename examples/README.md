# Fixtures

Deliberately rotten repositories used to exercise the detectors.

**Do not fix them.** Every problem in here is intentional, and CI asserts that
the fixtures still trigger every offline category. If a fixture stops firing a
detector, the detector is broken, not the fixture.

The root `CONFIGROT.md` excludes `^examples/` so this directory's rot does not
get merged into a scan of this repository itself.

| Fixture | Exercises |
|---|---|
| `rotten-repo/` | All six offline categories: EOL Node in four places, removed runner label, `::set-output`, ESLint 9 with `.eslintrc`, CRA, `node-sass`, two lockfiles, dead npm scripts |

## Adding one

Add a directory, make it minimal, and add an assertion in `tests/test_scan.py`
naming the finding ids it should produce. A fixture nothing asserts against is
decoration.
