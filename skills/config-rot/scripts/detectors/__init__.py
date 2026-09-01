"""Configuration-rot detectors.

Every detector exposes ``run(inv, ctx) -> list[Finding]`` and is registered in
``scan.py``. Adding an ecosystem means adding one file here — this is the
primary contribution path for the project.

Detectors must never write to the repository. ``scan.py`` is safe to run
against untrusted code, in CI, or from a README one-liner precisely because
nothing in this package has side effects.
"""
