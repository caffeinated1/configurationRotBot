"""DECAY: runtimes, base images and actions that are past or nearing end of life.

This is the highest-value offline detector. Knowing that Node 18 stopped
receiving security patches requires no network call and no registry lookup —
only a date — yet it is the single fact most likely to be out of date in a repo
nobody has touched in two years.
"""

from __future__ import annotations

import datetime as _dt
import re

from common import Evidence, Finding, is_pinned, load_data, vtuple

DETECTOR = "eol"

# How the cycle key is formed per runtime, because vendors version differently:
# Node ships one cycle per major, Python one per minor.
_GRANULARITY = {
    "node": 1, "java": 1, "rust": 1,
    "python": 2, "go": 2, "ruby": 2, "php": 2, "dotnet": 2,
    "alpine": 2, "ubuntu": 2,
}


def _cycle_keys(runtime: str, spec: str) -> list[str]:
    """Candidate keys to look up, most specific first."""
    spec = str(spec).strip().lstrip("v=^~>< ")
    keys: list[str] = []
    # Debian releases are commonly referenced by codename.
    word = re.match(r"^([a-z]+)", spec)
    if word:
        keys.append(word.group(1))
    t = vtuple(spec)
    if t:
        gran = _GRANULARITY.get(runtime, 2)
        if gran == 2:
            # Preserve a written ".04"-style minor rather than the parsed int.
            m = re.match(r"^(\d+)\.(\d+)", spec)
            keys.append(m.group(0) if m else f"{t[0]}.{t[1]}")
        keys.append(str(t[0]))
    return keys


def _parse_date(s: str) -> _dt.date | None:
    try:
        return _dt.date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _severity_for(days: int | None) -> str | None:
    """days < 0 means already past EOL."""
    if days is None:
        return None
    if days < -365:
        return "critical"
    if days < 0:
        return "high"
    if days <= 90:
        return "high"
    if days <= 180:
        return "medium"
    return None


def run(inv, ctx) -> list[Finding]:
    data = load_data("eol.json")
    if not data:
        ctx.skip(DETECTOR, "data/eol.json missing or unreadable")
        return []

    today = ctx.today
    findings: list[Finding] = []
    seen: set[str] = set()

    cycles = data.get("cycles", {})
    for decl in inv.versions:
        cycle = cycles.get(decl.runtime)
        if not cycle:
            continue
        eol_map = cycle.get("eol", {})
        hit_key = hit_date = None
        for key in _cycle_keys(decl.runtime, decl.spec):
            if key in eol_map:
                hit_key, hit_date = key, _parse_date(eol_map[key])
                break
        if not hit_date:
            continue

        days = (hit_date - today).days
        sev = _severity_for(days)
        if not sev:
            continue

        fid = f"DECAY.{decl.runtime}-eol.{decl.source}"
        if fid in seen:
            # One finding per declaration site, not per matched key.
            fid = f"{fid}.{decl.file.replace('/', '_')}"
        if fid in seen:
            continue
        seen.add(fid)

        past = days < 0
        when = f"reached end of life on {hit_date.isoformat()}" if past \
            else f"reaches end of life on {hit_date.isoformat()} ({days} days)"
        newest = _newest_supported(eol_map, today)

        findings.append(Finding(
            id=fid,
            category="DECAY",
            severity=sev,
            title=f"{decl.runtime} {hit_key} ({decl.source}) {when}",
            evidence=[Evidence(decl.file, decl.line, f"{decl.runtime} {decl.spec}")],
            detail=_detail(decl, hit_key, past),
            recommendation=(
                f"Move to {decl.runtime} {newest} if nothing pins you lower."
                if newest else f"Move to a currently supported {decl.runtime} release."
            ),
            effort="small" if decl.source in ("nvmrc", "node-version", "python-version",
                                              "asdf", "ci-matrix") else "medium",
            autofix="assisted",
            blast_radius=["build", "runtime", "ci"],
            references=[cycle["url"]] if cycle.get("url") else [],
            detector=DETECTOR,
        ))

    findings += _runners(inv, data, ctx)
    findings += _actions(inv, data, ctx)
    return findings


def _detail(decl, hit_key: str, past: bool) -> str:
    """Phrase the finding honestly for ranges as well as pins.

    `engines.node: ">=14"` does not mean the project runs Node 14 — it means it
    advertises support for it. Saying "you are on an unpatched runtime" would be
    wrong; the real problem is that the promise covers a version nobody should
    still be using.
    """
    where = f"`{decl.file}` declares {decl.runtime} {decl.spec} via {decl.source}."
    if not is_pinned(decl.spec):
        return (f"{where} The declared floor is {decl.runtime} {hit_key}, which "
                + ("is past end of life. Anyone taking that promise literally runs an "
                   "unpatched runtime, and the range keeps compatibility shims alive "
                   "across the whole codebase."
                   if past else
                   "loses support soon. Raise the floor before it does."))
    if past:
        return (f"{where} This version no longer receives security patches, so any "
                "vulnerability found in it stays unpatched in your build.")
    return f"{where} Plan the upgrade before support ends rather than during an incident."


def _newest_supported(eol_map: dict, today: _dt.date) -> str | None:
    """The highest cycle whose EOL is furthest in the future."""
    best, best_date = None, None
    for key, val in eol_map.items():
        d = _parse_date(val)
        if not d or d <= today:
            continue
        if best_date is None or d > best_date or (d == best_date and _kf(key) > _kf(best)):
            best, best_date = key, d
    return best


def _kf(key: str | None) -> tuple:
    return vtuple(key) or (0, 0, 0)


def _runners(inv, data, ctx) -> list[Finding]:
    runners = data.get("github_runners", {})
    out, seen = [], set()
    for wf, facts in inv.workflows.items():
        for line, kind, value in facts:
            if kind != "runs-on":
                continue
            label = value.strip().strip("[]").split(",")[0].strip()
            info = runners.get(label)
            if not info or (wf, label) in seen:
                continue
            seen.add((wf, label))
            removed = info.get("status") == "removed"
            out.append(Finding(
                id=f"DECAY.gh-runner.{label}",
                category="DECAY",
                severity="critical" if removed else "high",
                title=f"Workflow targets the {'removed' if removed else 'deprecated'} runner label `{label}`",
                evidence=[Evidence(wf, line, f"runs-on: {label}")],
                detail=("GitHub removed this runner image. Jobs requesting it fail to "
                        "schedule." if removed else
                        f"GitHub has scheduled this runner for removal ({info.get('date')})."),
                recommendation=f"Switch to `{info.get('replacement', 'ubuntu-latest')}`.",
                effort="trivial", autofix="safe", blast_radius=["ci"],
                detector=DETECTOR,
            ))
    return out


_USES_RE = re.compile(r"^([\w.-]+/[\w.-]+)@v?(\d+)")


def _actions(inv, data, ctx) -> list[Finding]:
    mins = data.get("github_actions", {})
    out, seen = [], set()
    for wf, facts in inv.workflows.items():
        for line, kind, value in facts:
            if kind != "uses":
                continue
            m = _USES_RE.match(value)
            if not m:
                continue
            action, ver = m.group(1), int(m.group(2))
            info = mins.get(action)
            if not info or ver >= info["min_major"]:
                continue
            key = (action, ver)
            if key in seen:
                continue
            seen.add(key)
            out.append(Finding(
                id=f"DECAY.gh-action.{action.replace('/', '-')}",
                category="DECAY",
                severity="high",
                title=f"`{action}@v{ver}` is below the supported major (v{info['min_major']})",
                evidence=[Evidence(wf, line, f"uses: {value}")],
                detail=info.get("reason", ""),
                recommendation=f"Pin to `{action}@v{info['min_major']}`.",
                effort="trivial", autofix="safe", blast_radius=["ci"],
                detector=DETECTOR,
            ))
    return out
