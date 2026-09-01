"""HAZARD / STAGNATION: dependencies whose upstream has stopped.

An archived package is not merely old. It is a component that will never receive
another security fix, which means every future advisory against it is permanent.
That is a different kind of problem from being a few versions behind, and it is
why these are HAZARD rather than DRIFT.
"""

from __future__ import annotations

from common import Evidence, Finding, load_data

DETECTOR = "abandoned"

_STATUS = {
    "deprecated": ("HAZARD", "high",
                   "The maintainers have formally deprecated this package. It will not "
                   "receive security fixes."),
    "archived": ("HAZARD", "high",
                 "The upstream repository is archived. No fix will ever ship."),
    "dormant": ("STAGNATION", "low",
                "Still installable and not formally deprecated, but development has "
                "effectively stopped and the ecosystem has moved to alternatives."),
}


def run(inv, ctx) -> list[Finding]:
    data = load_data("abandoned.json")
    if not data:
        ctx.skip(DETECTOR, "data/abandoned.json missing or unreadable")
        return []

    catalogue = data.get("packages", {})
    out: list[Finding] = []
    seen: set[str] = set()

    for dep in inv.deps:
        entry = (catalogue.get(dep.ecosystem) or {}).get(dep.name)
        if not entry or entry.get("status") == "active":
            continue
        if dep.name in seen or dep.name in ctx.claimed_packages:
            # A dedicated rule already explains this one, with better
            # advice than the generic catalogue entry can give.
            continue
        seen.add(dep.name)

        category, severity, blurb = _STATUS.get(
            entry["status"], ("STAGNATION", "low", ""))
        since = f" (since {entry['since']})" if entry.get("since") else ""
        replacement = entry.get("replacement")

        out.append(Finding(
            id=f"{category}.abandoned.{dep.name}",
            category=category,
            severity=severity,
            title=f"`{dep.name}` is {entry['status']}{since}",
            evidence=[Evidence(dep.manifest, dep.line, f"{dep.name} {dep.spec}")],
            detail=blurb,
            recommendation=(f"Replace with {replacement}." if replacement
                            else "Find a maintained alternative or vendor the functionality."),
            effort="medium" if severity == "high" else "large",
            autofix="assisted" if severity == "high" else "manual",
            blast_radius=["runtime"],
            detector=DETECTOR,
            confidence="high",
        ))
    return out
