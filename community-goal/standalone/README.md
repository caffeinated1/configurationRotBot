# Files for the standalone repository

Community Goal is built inside `configurationRotBot` but is meant to live in its
own repository, where a town planner or an NGO can find it without navigating a
developer tool. [`../extract.py`](../extract.py) performs that move.

These are the files that only make sense once it is standalone — a CI workflow
that no longer shares a matrix with the scanner's tests, and the licence pair
that here is inherited from the parent repository. `extract.py` copies them to
the new repository root.

Everything else the new repository needs is generated from what is already in
`community-goal/`, so this directory stays small on purpose. If you change a
path, a URL, or a document name in `community-goal/`, `extract.py` will carry it
across — that is what its tests check.
