# Python

## Where the Python version is declared

| Source | File | Notes |
|---|---|---|
| CI matrix | `.github/workflows/*.yml` | What is actually tested |
| Container | `Dockerfile` `FROM python:` | What ships |
| `requires-python` | `pyproject.toml` | A promise to consumers; pip enforces it |
| `python_requires` | `setup.py`/`setup.cfg` | Legacy equivalent |
| `.python-version` | pyenv | Local only |
| `.tool-versions` | asdf/mise | Local only |
| Tool targets | `[tool.ruff] target-version`, `[tool.black] target-version`, `[tool.mypy] python_version` | Frequently stale |

The tool targets are the ones nobody updates. A repo that moved to 3.12 but left
`target-version = "py38"` gets linted against 3.8 rules — so `ruff` will not
suggest the modern syntax the codebase can now use, and may flag syntax that is
perfectly valid.

## Packaging

PEP 621 `pyproject.toml` is the standard. `setup.py` still works but is
increasingly second-class: `uv`, isolated builds, and much of the modern
toolchain expect `pyproject.toml`.

Order of modernity, roughly:

```
setup.py only  →  setup.py + setup.cfg  →  pyproject.toml [project]  →  + uv/poetry lock
```

`requirements.txt` with unpinned versions and no lockfile means every install
resolves differently. `pip-compile` (pip-tools) or `uv lock` fixes this without
a full packaging migration — a good small step for a repo not ready for one.

## Hard breakages by version

| Version | What broke |
|---|---|
| 3.12 | `distutils` **removed**. Any `import distutils` is an ImportError. `setuptools` vendors a shim only if installed and imported first |
| 3.12 | Invalid escape sequences in strings became SyntaxWarning (SyntaxError in 3.14) |
| 3.11 | `inspect.getargspec`, `@asyncio.coroutine` removed |
| 3.10 | `collections.Mapping` style aliases removed (use `collections.abc`) |
| 3.10 | `nose` no longer imports |
| 3.9 | `zoneinfo` added — `pytz` is no longer necessary |

`distutils` is the one that most often blocks a Python upgrade outright, and it
is frequently pulled in by an old `setup.py` rather than by application code.

## Linters and formatters

`ruff` now covers flake8, isort, pyupgrade, pydocstyle, bandit and more, at
roughly 10–100× the speed. A repo running three or more of those separately is
carrying three configs, three CI steps, and three things to keep current.

That said: consolidating is a `medium`-effort STAGNATION finding, not a defect.
Flag it, explain the win, and let the team decide. A repo happily running flake8
is not broken.

Real cruft, on the other hand: a `.flake8` or `[flake8]` section left behind
after the move to ruff. Nobody reads it, but contributors edit it expecting an
effect.

## Dependency tooling

| Tool | State |
|---|---|
| `uv` | Current; fastest, handles resolution, locking, and Python installs |
| `poetry` | Actively maintained, widely used |
| `pip-tools` | Maintained, minimal, good for a requirements.txt project |
| `pipenv` | Effectively dormant; migrate when convenient |
| bare `pip install -r` | Works, but no lockfile means no reproducibility |

## Verification commands

```bash
python -m pip install -e ".[dev]"     # or: uv sync / poetry install
python -m pytest
python -m ruff check .                # or flake8
python -m mypy .
python -c "import <yourpackage>"      # catches import-time breakage fastest
```

That last one is worth running first after any dependency change. Most Python
upgrade failures are import errors, and finding them takes a second rather than
a full test run.
