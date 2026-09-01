"""DIVERGENCE: places in the repo that disagree about the same underlying truth.

This is the detector no other tool runs, and the cheapest one to trust: it needs
no network, no registry, and no knowledge of what is currently modern. It only
needs to notice that a repo declares its Node version in seven places and that
three of them say different things.

Every divergence is either a latent bug waiting for an environment difference to
surface it, or a stale file nobody updated. Both are worth reporting, and the
report should not pretend to know which one it found.

Authority ordering matters: CI is the highest authority because it is the
version actually exercised, then the Dockerfile because it is what ships, then
local pins, then declared ranges.
"""

from __future__ import annotations

import re
from collections import defaultdict

from common import Evidence, Finding, is_pinned, major, read_text, vtuple

DETECTOR = "divergence"

_SOURCE_LABEL = {
    "ci-matrix": "CI (what is actually tested)",
    "dockerfile": "the Dockerfile (what actually ships)",
    "nvmrc": ".nvmrc (local development)",
    "node-version": ".node-version (local development)",
    "python-version": ".python-version (local development)",
    "asdf": ".tool-versions (local development)",
    "engines": "package.json engines (what consumers are told)",
    "volta": "Volta pin",
    "requires-python": "pyproject requires-python (what consumers are told)",
    "poetry-python": "Poetry python constraint",
    "go-directive": "the go directive in go.mod",
}


def run(inv, ctx) -> list[Finding]:
    out: list[Finding] = []
    out += _runtime_divergence(inv)
    out += _declared_floor_untested(inv)
    out += _python_tool_targets(inv)
    out += _package_manager(inv)
    return out


# ------------------------------------------------------------------ runtimes

def _runtime_divergence(inv) -> list[Finding]:
    by_runtime: dict[str, list] = defaultdict(list)
    for d in inv.versions:
        if d.runtime in ("rust-edition",):
            continue
        by_runtime[d.runtime].append(d)

    out: list[Finding] = []
    for runtime, decls in by_runtime.items():
        if len(decls) < 2:
            continue

        # A CI matrix testing several versions is intentional, not divergence.
        tested = {major(d.spec) for d in decls
                  if d.source == "ci-matrix" and major(d.spec) is not None}
        pins = [d for d in decls if is_pinned(d.spec) and d.source != "ci-matrix"]
        pin_majors = {major(d.spec) for d in pins if major(d.spec) is not None}

        conflicting = pin_majors | (tested if tested else set())
        conflicting.discard(None)

        if len(conflicting) > 1:
            ships = next((d for d in decls if d.source == "dockerfile"), None)
            severity = "high" if (ships and tested and major(ships.spec) not in tested) else "medium"
            out.append(Finding(
                id=f"DIVERGENCE.{runtime}-version",
                category="DIVERGENCE",
                severity=severity,
                title=(f"{runtime} version is declared as "
                       f"{', '.join(str(v) for v in sorted(conflicting))} in different places"),
                evidence=[Evidence(d.file, d.line, f"{d.source}: {d.spec}") for d in decls],
                detail=_describe(runtime, decls, tested),
                recommendation=(
                    f"Pick one {runtime} version and make every declaration agree. CI is "
                    "usually the right answer because it is the version actually exercised; "
                    "if the Dockerfile differs from CI, you are shipping an untested runtime."
                ),
                effort="trivial",
                autofix="assisted",
                blast_radius=["build", "ci", "runtime"],
                detector=DETECTOR,
            ))
    return out


def _describe(runtime: str, decls, tested: set) -> str:
    lines = [f"Declarations of the {runtime} version found in this repo:"]
    for d in sorted(decls, key=lambda x: -x.authority):
        label = _SOURCE_LABEL.get(d.source, d.source)
        lines.append(f"  - `{d.file}`: {d.spec}  — {label}")
    ships = next((d for d in decls if d.source == "dockerfile"), None)
    if ships and tested and major(ships.spec) not in tested:
        lines.append("")
        lines.append(
            f"The Dockerfile builds on {runtime} {ships.spec}, which is not in the set CI "
            f"tests ({', '.join(str(t) for t in sorted(tested))}). Production is running a "
            "runtime that nothing verifies."
        )
    return "\n".join(lines)


def _declared_floor_untested(inv) -> list[Finding]:
    """A public floor nobody tests is a promise the project cannot keep."""
    out: list[Finding] = []
    for runtime in {d.runtime for d in inv.versions}:
        decls = [d for d in inv.versions if d.runtime == runtime]
        declared = next((d for d in decls
                         if d.source in ("engines", "requires-python", "poetry-python")), None)
        tested = sorted({major(d.spec) for d in decls
                         if d.source in ("ci-matrix", "dockerfile") and major(d.spec)})
        if not declared or not tested or is_pinned(declared.spec):
            continue
        floor = major(declared.spec)
        if floor is None or floor >= min(tested):
            continue
        out.append(Finding(
            id=f"DIVERGENCE.{runtime}-floor-untested",
            category="DIVERGENCE",
            severity="medium",
            title=(f"`{declared.file}` claims support for {runtime} {declared.spec}, "
                   f"but nothing below {min(tested)} is ever tested"),
            evidence=[Evidence(declared.file, declared.line,
                               f"{declared.source}: {declared.spec}")],
            detail=(
                f"The declared floor is {runtime} {floor}; the lowest version exercised by CI "
                f"or the container build is {min(tested)}. Anyone who installs this on the "
                "version you advertise is running a configuration you have never run. This "
                "usually means the floor was set years ago and never revisited."
            ),
            recommendation=(
                f"Either raise the declared floor to {min(tested)}, or add {runtime} {floor} "
                "to the CI matrix so the promise is actually verified."
            ),
            effort="trivial", autofix="assisted", blast_radius=["compat"],
            detector=DETECTOR,
        ))
    return out


# ------------------------------------------------------------- python tools

_PY_TARGET = re.compile(r"py(\d)(\d+)")


def _python_tool_targets(inv) -> list[Finding]:
    """ruff/black/mypy each carry their own idea of the minimum Python."""
    if not inv.pyproject:
        return []
    raw = read_text(inv.root, "pyproject.toml") or ""
    tool = inv.pyproject.get("tool") or {}
    targets: list[tuple[str, tuple[int, int], str]] = []

    for name, key in (("ruff", "target-version"), ("black", "target-version"),
                      ("mypy", "python_version")):
        cfg = tool.get(name) or {}
        val = cfg.get(key)
        if isinstance(val, list):
            val = val[0] if val else None
        if not val:
            continue
        m = _PY_TARGET.search(str(val))
        if m:
            targets.append((name, (int(m.group(1)), int(m.group(2))), str(val)))
        else:
            t = vtuple(str(val))
            if t:
                targets.append((name, (t[0], t[1]), str(val)))

    declared = next((d for d in inv.versions
                     if d.runtime == "python"
                     and d.source in ("requires-python", "poetry-python")), None)
    if not declared or not targets:
        return []
    dt = vtuple(declared.spec)
    if not dt:
        return []
    floor = (dt[0], dt[1])

    mismatched = [t for t in targets if t[1] != floor]
    if not mismatched:
        return []

    return [Finding(
        id="DIVERGENCE.python-tool-target",
        category="DIVERGENCE",
        severity="low",
        title="Python tooling targets a different version than requires-python declares",
        evidence=[Evidence("pyproject.toml",
                           None if not raw else _find_line(raw, name),
                           f"[tool.{name}] → {shown}")
                  for name, _, shown in mismatched],
        detail=(
            f"`requires-python` declares {declared.spec}, but "
            + ", ".join(f"{n} targets {s}" for n, _, s in mismatched)
            + ". Linters and type checkers will apply rules for the wrong Python version — "
              "either flagging syntax that is fine on your real floor, or permitting syntax "
              "that breaks on it."
        ),
        recommendation="Align every tool's target with requires-python.",
        effort="trivial", autofix="safe", blast_radius=["lint", "types"],
        detector=DETECTOR,
    )]


def _find_line(raw: str, tool: str) -> int | None:
    for i, line in enumerate(raw.splitlines(), start=1):
        if f"[tool.{tool}]" in line:
            return i
    return None


# ---------------------------------------------------------- package manager

_PM_COMMANDS = {
    "npm": re.compile(r"\bnpm (ci|install|i)\b"),
    "yarn": re.compile(r"\byarn (install|--frozen-lockfile)|\byarn\b\s*$", re.MULTILINE),
    "pnpm": re.compile(r"\bpnpm (install|i)\b"),
    "bun": re.compile(r"\bbun install\b"),
}

_LOCK_TO_PM = {
    "package-lock.json": "npm", "npm-shrinkwrap.json": "npm",
    "yarn.lock": "yarn", "pnpm-lock.yaml": "pnpm", "bun.lockb": "bun",
}


def _package_manager(inv) -> list[Finding]:
    if "node" not in inv.ecosystems:
        return []

    declared = None
    if inv.package_json:
        pm = inv.package_json.get("packageManager")
        if isinstance(pm, str):
            declared = pm.split("@")[0]

    lock_pms = {_LOCK_TO_PM[f.split("/")[-1]] for f in inv.lockfiles
                if f.split("/")[-1] in _LOCK_TO_PM}

    ci_pms: set[str] = set()
    ci_evidence: list[Evidence] = []
    for wf in inv.workflows:
        text = read_text(inv.root, wf) or ""
        for pm, rx in _PM_COMMANDS.items():
            m = rx.search(text)
            if m:
                ci_pms.add(pm)
                line = text[:m.start()].count("\n") + 1
                ci_evidence.append(Evidence(wf, line, text.splitlines()[line - 1].strip()))

    truths = {k: v for k, v in (("declared", {declared} if declared else set()),
                                ("lockfile", lock_pms),
                                ("ci", ci_pms)) if v}
    all_pms: set[str] = set()
    for v in truths.values():
        all_pms |= v
    if len(all_pms) < 2:
        return []

    ev = ci_evidence + [Evidence(f) for f in inv.lockfiles]
    if declared and inv.package_json:
        ev.insert(0, Evidence("package.json", None, f'"packageManager": "{declared}"'))

    return [Finding(
        id="DIVERGENCE.package-manager",
        category="DIVERGENCE",
        severity="high" if (lock_pms and ci_pms and not (lock_pms & ci_pms)) else "medium",
        title=f"Package manager is ambiguous: {', '.join(sorted(all_pms))} are all indicated",
        evidence=ev,
        detail=(
            "Different surfaces point at different package managers — "
            + "; ".join(f"{k}: {', '.join(sorted(v))}" for k, v in truths.items())
            + ". When CI installs with a manager whose lockfile is not the committed one, "
              "the lockfile is not being honoured and CI is resolving fresh versions on every "
              "run. That silently undoes the reproducibility the lockfile exists to provide."
        ),
        recommendation=(
            "Choose one manager. Add a `packageManager` field to package.json so Corepack "
            "enforces it, keep only the matching lockfile, and make CI use the same command."
        ),
        effort="small", autofix="assisted", blast_radius=["build", "ci"],
        detector=DETECTOR,
    )]
