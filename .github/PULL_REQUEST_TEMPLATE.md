## What this changes

<!-- One or two sentences. If it touches community-goal/, say which requirement,
     evidence item, or jurisdiction. -->

## Why

<!-- The failure mode, the source, or the local statute that prompted it. -->

## Material interest

<!-- Required for community-goal/ changes, per community-goal/GOVERNANCE.md.
     Are you employed by, advising, funded by, or in litigation with a data
     center developer, operator, tenant, utility, equipment vendor, landowner in
     a pending application, or an organisation campaigning on either side?

     Disclosed interest disqualifies nobody. Write "none" if none. -->

none

## Checks

- [ ] `python3 tests/test_community_goal.py` passes (content changes), or
      `for t in tests/test_*.py; do python3 "$t" || break; done` (scanner changes)
- [ ] Any new claim carries a source, or a `verify` note saying how to check it
- [ ] Anything true in only one jurisdiction went into an overlay, not a shared requirement
- [ ] No requirement id was renamed or reused
- [ ] No new runtime dependencies
