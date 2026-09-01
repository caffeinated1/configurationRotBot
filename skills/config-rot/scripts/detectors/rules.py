"""Declarative rule engine over data/rules.json.

Deprecation patterns are the fastest-moving part of this problem, so they are
data rather than code. The condition grammar is deliberately small: it covers
"is this dependency present at this version", "does this file exist", and "does
this file contain this pattern", which between them express nearly every real
deprecation. Anything genuinely more complex belongs in its own detector.

Grammar (all top-level keys AND together):

    ecosystem          "node"                     project uses this ecosystem
    has_any_ecosystem  true                       any ecosystem was detected at all
                                                  (guard for "you are missing X" rules)
    dependency         {name, present|version_gte|version_lt}
    dependency_absent  ["a", "b"]                 none of these are dependencies
    dependency_any     ["a", "b"] + count_gte: N  at least N of these present
    file_exists        ["a", "b"]                 ANY of these paths exists
    file_exists_all    ["a", "b"]                 ALL of these paths exist
    file_absent        ["a", "b"]                 ALL of these are absent
    file_absent_glob   ["regex"]                  no path matches any regex
    file_contains      [{glob, pattern}]          some matching file matches pattern
    not_file_contains  [{glob, pattern}]          no matching file matches pattern
    lockfile_count_gte N
    any                [ {...}, {...} ]           OR over sub-conditions

A rule may also carry `covers: ["pkg"]`, marking packages it fully explains so
the abandoned-package catalogue does not report them a second time.
"""

from __future__ import annotations

import os
import re

from common import Evidence, Finding, line_matching, load_data, read_text, vcmp

DETECTOR = "rules"


def run(inv, ctx) -> list[Finding]:
    data = load_data("rules.json")
    if not data:
        ctx.skip(DETECTOR, "data/rules.json missing or unreadable")
        return []

    out: list[Finding] = []
    for rule in data.get("rules", []):
        try:
            ok, evidence = _match(rule.get("when", {}), inv)
        except re.error as exc:
            ctx.skip(DETECTOR, f"rule {rule.get('id')} has an invalid pattern: {exc}")
            continue
        if not ok:
            continue
        ctx.claimed_packages.update(rule.get("covers", []))
        if not evidence and inv.manifests:
            # An absence rule has no offending line to point at. The honest
            # evidence is the manifest establishing that this is a project
            # the rule applies to at all.
            evidence = [Evidence(inv.manifests[0])]
        out.append(Finding(
            id=rule["id"],
            category=rule.get("category", "STAGNATION"),
            severity=rule.get("severity", "medium"),
            title=rule.get("title", rule["id"]),
            evidence=evidence,
            detail=rule.get("detail", ""),
            recommendation=rule.get("recommendation", ""),
            effort=rule.get("effort", "small"),
            autofix=rule.get("autofix", "assisted"),
            blast_radius=rule.get("blast_radius", []),
            references=rule.get("references", []),
            detector=DETECTOR,
            confidence=rule.get("confidence", "high"),
        ))
    return out


def _exists(inv, path: str) -> bool:
    """True for tracked files and for directories, which `walk` does not list."""
    return path in inv.files or os.path.exists(os.path.join(inv.root, path))


def _match(when: dict, inv) -> tuple[bool, list[Evidence]]:
    evidence: list[Evidence] = []

    if "any" in when:
        for sub in when["any"]:
            ok, ev = _match(sub, inv)
            if ok:
                evidence += ev
                break
        else:
            return False, []

    eco = when.get("ecosystem")
    if eco and eco not in inv.ecosystems:
        return False, []

    # "You are missing X" only means something once we know this directory is
    # a project. Without this guard, absence rules fire on an empty folder.
    if when.get("has_any_ecosystem") and not inv.ecosystems:
        return False, []

    dep_cond = when.get("dependency")
    if dep_cond:
        d = inv.dep(dep_cond["name"])
        if d is None:
            return False, []
        if "version_gte" in dep_cond and vcmp(d.spec, dep_cond["version_gte"]) < 0:
            return False, []
        if "version_lt" in dep_cond and vcmp(d.spec, dep_cond["version_lt"]) >= 0:
            return False, []
        evidence.append(Evidence(d.manifest, d.line, f'"{d.name}": "{d.spec}"'))

    for name in when.get("dependency_absent", []):
        if inv.dep(name) is not None:
            return False, []

    if "dependency_any" in when:
        hits = [inv.dep(n) for n in when["dependency_any"]]
        hits = [h for h in hits if h is not None]
        if len(hits) < when.get("count_gte", 1):
            return False, []
        evidence += [Evidence(h.manifest, h.line, h.name) for h in hits]

    if "file_exists" in when:
        hit = next((p for p in when["file_exists"] if _exists(inv, p)), None)
        if hit is None:
            return False, []
        evidence.append(Evidence(hit))

    for path in when.get("file_exists_all", []):
        if not _exists(inv, path):
            return False, []

    for path in when.get("file_absent", []):
        if _exists(inv, path):
            return False, []

    for pattern in when.get("file_absent_glob", []):
        if inv.glob(pattern):
            return False, []

    for spec in when.get("file_contains", []):
        found = False
        for path in inv.glob(spec["glob"]):
            line, text = line_matching(read_text(inv.root, path), spec["pattern"])
            if line:
                evidence.append(Evidence(path, line, text))
                found = True
                break
        if not found:
            return False, []

    for spec in when.get("not_file_contains", []):
        for path in inv.glob(spec["glob"]):
            line, _ = line_matching(read_text(inv.root, path), spec["pattern"])
            if line:
                return False, []

    if "lockfile_count_gte" in when:
        if len(inv.lockfiles) < when["lockfile_count_gte"]:
            return False, []
        evidence += [Evidence(p) for p in inv.lockfiles]

    return True, evidence
