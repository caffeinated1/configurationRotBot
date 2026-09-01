"""CRUFT: config and dependencies that no longer affect anything.

Cruft is low-severity by nature but high-value to report, because it is what
makes a repo feel unmaintained to a new contributor. Somebody opening a project
and finding four config files for tools that are not installed learns not to
trust any of the configuration.

Everything here is heuristic, and says so via `confidence`. Deleting config is
irreversible in the sense that nobody will ever remember why it was there, so
these findings recommend verification rather than deletion outright.
"""

from __future__ import annotations

import re

from common import Evidence, Finding, read_text

DETECTOR = "cruft"

# Config file -> the packages that give it meaning. If none of them are
# dependencies, nothing reads the file.
ORPHAN_CONFIGS = {
    "jest.config.js": ["jest", "ts-jest", "@jest/globals"],
    "jest.config.ts": ["jest", "ts-jest"],
    "jest.config.mjs": ["jest"],
    "vitest.config.ts": ["vitest"],
    "vitest.config.js": ["vitest"],
    "webpack.config.js": ["webpack", "webpack-cli", "next"],
    "rollup.config.js": ["rollup"],
    "vite.config.ts": ["vite"],
    "vite.config.js": ["vite"],
    "karma.conf.js": ["karma"],
    "protractor.conf.js": ["protractor"],
    "cypress.config.js": ["cypress"],
    "cypress.json": ["cypress"],
    "playwright.config.ts": ["@playwright/test", "playwright"],
    ".prettierrc": ["prettier"],
    ".prettierrc.json": ["prettier"],
    "prettier.config.js": ["prettier"],
    "tailwind.config.js": ["tailwindcss"],
    "postcss.config.js": ["postcss", "tailwindcss", "autoprefixer", "next", "vite"],
    "nodemon.json": ["nodemon"],
    "commitlint.config.js": ["@commitlint/cli", "@commitlint/config-conventional"],
    "lint-staged.config.js": ["lint-staged"],
    ".stylelintrc": ["stylelint"],
    ".stylelintrc.json": ["stylelint"],
    "tsconfig.json": ["typescript"],
    ".flake8": ["flake8"],
    "mypy.ini": ["mypy"],
    ".isort.cfg": ["isort"],
    "pytest.ini": ["pytest"],
    "tox.ini": ["tox"],
    ".pylintrc": ["pylint"],
}


def run(inv, ctx) -> list[Finding]:
    out: list[Finding] = []
    out += _orphan_configs(inv)
    out += _dead_scripts(inv)
    out += _unused_node_deps(inv, ctx)
    return out


def _orphan_configs(inv) -> list[Finding]:
    out = []
    for path in sorted(inv.files):
        base = path.split("/")[-1]
        owners = ORPHAN_CONFIGS.get(base)
        if not owners:
            continue
        if any(inv.dep(o) for o in owners):
            continue
        # A monorepo may declare the tool in a workspace manifest rather than at
        # the root, so this stays medium-confidence rather than asserting.
        out.append(Finding(
            id=f"CRUFT.orphan-config.{base}",
            category="CRUFT",
            severity="low",
            title=f"`{path}` configures {owners[0]}, which is not a declared dependency",
            evidence=[Evidence(path)],
            detail=(
                f"No manifest in this repo declares {' or '.join(owners)}, so nothing reads "
                f"`{path}`. Contributors will still edit it and expect an effect."
            ),
            recommendation=(
                "Confirm nothing consumes it (check workspace manifests and any global "
                "tooling), then delete it. If the tool is meant to be used, add it as a "
                "dependency instead."
            ),
            effort="trivial", autofix="assisted", blast_radius=[],
            detector=DETECTOR, confidence="medium",
        ))
    return out


_SCRIPT_FILE_RE = re.compile(r"(?:node|ts-node|tsx|python3?|bash|sh)\s+([\w./-]+\.\w+)")


def _dead_scripts(inv) -> list[Finding]:
    """npm scripts pointing at files that no longer exist."""
    if not inv.package_json:
        return []
    raw = read_text(inv.root, "package.json") or ""
    out = []
    for name, cmd in (inv.package_json.get("scripts") or {}).items():
        if not isinstance(cmd, str):
            continue
        for m in _SCRIPT_FILE_RE.finditer(cmd):
            target = m.group(1).lstrip("./")
            if target in inv.files or any(f.endswith("/" + target) for f in inv.files):
                continue
            line = next((i for i, l in enumerate(raw.splitlines(), 1)
                         if f'"{name}"' in l), None)
            out.append(Finding(
                id=f"CRUFT.dead-script.{name}",
                category="CRUFT",
                severity="low",
                title=f'npm script "{name}" runs `{target}`, which does not exist',
                evidence=[Evidence("package.json", line, f'"{name}": "{cmd}"')],
                detail="The script fails immediately if anyone runs it.",
                recommendation="Fix the path or remove the script.",
                effort="trivial", autofix="assisted", blast_radius=[],
                detector=DETECTOR, confidence="medium",
            ))
            break
    return out


_IMPORT_RE_TPL = r"""(?:from\s+['"]{name}(?:/[^'"]*)?['"]|require\(\s*['"]{name}(?:/[^'"]*)?['"]|import\s+['"]{name}(?:/[^'"]*)?['"])"""

# Packages that are legitimately never imported: they are invoked as binaries,
# loaded by config, or act as peer/plugin registrations.
_NEVER_IMPORTED_OK = re.compile(
    r"^(@types/|eslint|prettier|typescript|husky|lint-staged|nodemon|concurrently|"
    r"rimraf|cross-env|npm-run-all|tailwindcss|autoprefixer|postcss|sass|less|"
    r"@babel/|babel-|webpack|rollup|vite|esbuild|jest|vitest|mocha|nyc|c8|"
    r"ts-node|tsx|tsup|turbo|nx|patch-package|only-allow|corepack|semantic-release|"
    r"react-scripts|next|gatsby|expo|parcel|snowpack|gulp|grunt|"
    r"@commitlint/|stylelint|serve|wait-on|start-server-and-test)"
)


def _unused_node_deps(inv, ctx) -> list[Finding]:
    """Runtime dependencies that appear nowhere in the source.

    Heuristic and confined to non-dev dependencies, because devDependencies are
    usually binaries rather than imports and would generate mostly noise.
    """
    if "node" not in inv.ecosystems:
        return []

    sources = [f for f in inv.files
               if f.endswith((".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".vue", ".svelte",
                              ".astro", ".json", ".html"))
               and not f.endswith("package-lock.json")]
    if len(sources) > 4000:
        ctx.skip(DETECTOR, "unused-dependency scan skipped: more than 4000 source files")
        return []

    blob = "\n".join(filter(None, (read_text(inv.root, f) for f in sources[:4000])))
    if not blob:
        return []

    unused = []
    for d in inv.deps:
        if d.ecosystem != "node" or d.dev or _NEVER_IMPORTED_OK.match(d.name):
            continue
        rx = re.compile(_IMPORT_RE_TPL.format(name=re.escape(d.name)))
        if not rx.search(blob):
            unused.append(d)

    if not unused:
        return []

    return [Finding(
        id="CRUFT.unused-dependencies",
        category="CRUFT",
        severity="low",
        title=f"{len(unused)} runtime dependencies are never imported in the source",
        evidence=[Evidence(d.manifest, d.line, f'"{d.name}": "{d.spec}"') for d in unused[:20]],
        detail=(
            "Candidates: " + ", ".join(d.name for d in unused) + ".\n\n"
            "This is a text search, so it misses dynamic imports, packages referenced only "
            "from config files, and plugins loaded by name. Verify before removing — but each "
            "one that is genuinely unused is install time, attack surface, and an advisory "
            "you will otherwise have to triage."
        ),
        recommendation=(
            "Check each candidate (`depcheck` or `knip` cross-check these well), remove the "
            "confirmed ones, and re-run the build."
        ),
        effort="small", autofix="manual", blast_radius=["build"],
        detector=DETECTOR, confidence="low",
    )]
