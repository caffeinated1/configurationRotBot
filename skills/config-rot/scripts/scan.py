#!/usr/bin/env python3
"""Configuration rot scanner.

Reads a repository and emits evidence-backed findings. It never writes to the
repository under scan, has no dependencies beyond the standard library, and
works offline. Those three properties are what make it safe to run in CI, in a
pre-commit hook, or against code you have not read.

    python3 scan.py --repo . --format markdown
    python3 scan.py --repo . --json findings.json --online

Exit code encodes the worst severity found (0 none, 1 low, 2 medium, 3 high,
4 critical) so it composes in a shell pipeline. Use --exit-zero in contexts
where a nonzero exit would be treated as a crash.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import (  # noqa: E402
    CATEGORIES, CATEGORY_WEIGHT, SCHEMA_VERSION, SEVERITY_RANK, SEVERITY_WEIGHT,
    Finding, read_text,
)
from detectors import abandoned, audit, cruft, divergence, eol, inventory, rules  # noqa: E402

# Order matters: `rules` runs before `abandoned` so that a rule can claim a
# package and suppress the generic catalogue entry for it.
DETECTORS = {
    "eol": eol,
    "rules": rules,
    "divergence": divergence,
    "cruft": cruft,
    "abandoned": abandoned,
    "drift": None,     # imported lazily; only meaningful with --online
    "audit": audit,
}


class Context:
    """Carries run-wide options and collects the things that did not happen.

    `skipped` is as important as the findings themselves. A scan that quietly
    omits the advisory check because npm was missing manufactures confidence,
    which is worse than reporting nothing at all.
    """

    def __init__(self, online: bool, today: _dt.date):
        self.online = online
        self.today = today
        self.skipped: list[dict[str, str]] = []
        # Packages already fully explained by a fired rule. The flat
        # abandoned-package catalogue defers to these so one dependency
        # produces one finding rather than two overlapping ones.
        self.claimed_packages: set[str] = set()

    def skip(self, detector: str, reason: str) -> None:
        self.skipped.append({"detector": detector, "reason": reason})


# --------------------------------------------------------------------------
# Policy
# --------------------------------------------------------------------------

_FRONTMATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def load_policy(root: str) -> dict:
    """Parse CONFIGROT.md front matter.

    Deliberately a small hand-rolled subset rather than a YAML dependency: the
    documented schema is flat scalars and flat lists, and the prose below the
    front matter is meant for the agent to read, not for this parser.
    """
    text = read_text(root, "CONFIGROT.md")
    if not text:
        return {}
    m = _FRONTMATTER.match(text)
    if not m:
        return {"prose": text}

    policy: dict = {"prose": text[m.end():]}
    current_list: str | None = None
    for line in m.group(1).splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if line.strip().startswith("-") and current_list:
            policy[current_list].append(line.strip()[1:].strip().strip("'\""))
            continue
        if ":" not in line:
            continue
        key, _, raw = line.partition(":")
        key, raw = key.strip(), raw.strip()
        if not raw:
            policy[key] = []
            current_list = key
            continue
        current_list = None
        if raw.startswith("[") and raw.endswith("]"):
            inner = raw[1:-1].strip()
            policy[key] = [p.strip().strip("'\"") for p in inner.split(",") if p.strip()]
        elif raw.lower() in ("true", "false"):
            policy[key] = raw.lower() == "true"
        elif raw.isdigit():
            policy[key] = int(raw)
        else:
            policy[key] = raw.strip("'\"")
    return policy


def apply_policy(findings: list[Finding], policy: dict) -> tuple[list, list]:
    """Split findings into actionable and policy-suppressed.

    Suppressed findings are returned, not dropped. A constraint that disappears
    from the report never gets revisited when it expires, which is how a
    temporary exception becomes permanent rot.
    """
    suppress = set(policy.get("suppress", []) or [])
    never = [p.rstrip("/*") for p in (policy.get("never_touch", []) or [])]

    active, muted = [], []
    for f in findings:
        reason = None
        if f.id in suppress:
            reason = "listed in CONFIGROT.md `suppress`"
        elif never and f.evidence and all(
                any(e.file.startswith(p) for p in never) for e in f.evidence):
            reason = "all evidence falls under CONFIGROT.md `never_touch`"
        if reason:
            d = f.to_dict()
            d["suppressed_by_policy"] = reason
            muted.append(d)
        else:
            active.append(f)
    return active, muted


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------

def rot_index(findings: list[Finding]) -> dict:
    """0-100, lower is better. It is debt, not a grade.

    Two properties matter more than the exact number.

    *Category weighting must survive.* An earlier version took a weighted mean
    across categories, which cancels the weights whenever one category dominates
    — three HAZARD findings scored identically to three CRUFT ones. Weight is
    applied per finding instead, so a critical vulnerability always outranks a
    stale config file.

    *The scale must not saturate.* A badly rotten repo can easily accumulate
    enough raw weight to peg a linear score at 100, and a metric stuck at its
    maximum cannot show progress — which destroys the only thing this number is
    genuinely good for. The compressive curve below keeps every improvement
    visible: fixing something always moves the index down, even from 97.

    The absolute value means little across repos; a monorepo will always score
    worse than a library. The trend within one repo is the entire point.
    """
    raw = sum(SEVERITY_WEIGHT.get(f.severity, 0) * CATEGORY_WEIGHT.get(f.category, 1.0)
              for f in findings)
    by_cat = {
        cat: _compress(sum(SEVERITY_WEIGHT.get(f.severity, 0)
                           for f in findings if f.category == cat))
        for cat in CATEGORIES
    }
    return {"overall": _compress(raw), "by_category": by_cat}


# Calibrated against examples/rotten-repo, which is about as bad as a real
# repository gets: it should land in the high 80s, leaving headroom above so
# the number never pegs and every fix still moves it. A single critical
# finding lands near 30 — the index measures accumulated debt, not urgency;
# the severity counts alongside it carry urgency.
_INDEX_SCALE = 250.0


def _compress(raw: float) -> int:
    if raw <= 0:
        return 0
    return max(1, min(100, int(round(100 * (1 - math.exp(-raw / _INDEX_SCALE))))))


def worst_severity(findings: list[Finding]) -> str:
    return max((f.severity for f in findings),
               key=lambda s: SEVERITY_RANK.get(s, 0), default="info")


# --------------------------------------------------------------------------
# State
# --------------------------------------------------------------------------

def update_state(root: str, index: dict, findings: list[Finding]) -> dict:
    path = os.path.join(root, ".configrot", "state.json")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        state = {"schema_version": SCHEMA_VERSION, "history": [], "attempts": {}}

    state.setdefault("history", [])
    state["history"].append({
        "date": _dt.date.today().isoformat(),
        "rot_index": index["overall"],
        "finding_count": len(findings),
        "by_severity": {s: sum(1 for f in findings if f.severity == s)
                        for s in ("critical", "high", "medium", "low")},
    })
    state["history"] = state["history"][-52:]  # a year of weekly runs
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
    except OSError:
        pass
    return state


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------

_SEV_ORDER = ["critical", "high", "medium", "low", "info"]
_ICON = {"critical": "!!", "high": "!", "medium": "~", "low": ".", "info": " "}


def render_markdown(payload: dict) -> str:
    idx = payload["rot_index"]
    findings = payload["findings"]
    out: list[str] = []
    out.append("# Configuration Rot Report")
    out.append("")
    out.append(f"**Rot index: {idx['overall']}/100** (lower is better) · "
               f"{len(findings)} findings · "
               f"ecosystems: {', '.join(payload['repo']['ecosystems']) or 'none detected'}")
    if payload.get("trend"):
        out.append("")
        out.append(f"**Trend:** {payload['trend']}")
    out.append("")

    counts = {s: sum(1 for f in findings if f["severity"] == s) for s in _SEV_ORDER}
    if any(counts.values()):
        out.append("| Severity | Count |")
        out.append("|---|---|")
        for s in _SEV_ORDER:
            if counts[s]:
                out.append(f"| {s} | {counts[s]} |")
        out.append("")

    for cat in CATEGORIES:
        rows = [f for f in findings if f["category"] == cat]
        if not rows:
            continue
        rows.sort(key=lambda f: -SEVERITY_RANK.get(f["severity"], 0))
        out.append(f"## {cat} ({len(rows)}) — index {idx['by_category'].get(cat, 0)}")
        out.append("")
        for f in rows:
            out.append(f"### {_ICON.get(f['severity'], '')} {f['title']}")
            out.append("")
            meta = (f"`{f['id']}` · **{f['severity']}** · effort: {f['effort']} · "
                    f"autofix: {f['autofix']}")
            if f.get("confidence") != "high":
                meta += f" · confidence: {f['confidence']}"
            out.append(meta)
            out.append("")
            for e in f["evidence"][:8]:
                loc = f"{e['file']}:{e['line']}" if e.get("line") else e["file"]
                out.append(f"- `{loc}`" + (f" — `{e['text']}`" if e.get("text") else ""))
            if f["evidence"]:
                out.append("")
            if f.get("detail"):
                out.append(f["detail"])
                out.append("")
            if f.get("recommendation"):
                out.append(f"**Fix:** {f['recommendation']}")
                out.append("")
            for ref in f.get("references", []):
                out.append(f"- {ref}")
            if f.get("references"):
                out.append("")

    if payload.get("suppressed"):
        out.append("## Suppressed by policy")
        out.append("")
        for f in payload["suppressed"]:
            out.append(f"- `{f['id']}` — {f['title']} ({f['suppressed_by_policy']})")
        out.append("")

    out.append("## What was not checked")
    out.append("")
    if payload.get("skipped"):
        for s in payload["skipped"]:
            out.append(f"- **{s['detector']}**: {s['reason']}")
    else:
        out.append("- Nothing. Every detector ran.")
    out.append("")
    out.append("---")
    out.append(f"_Generated by configurationRotBot · schema {payload['schema_version']} · "
               f"{payload['generated_at']}_")
    return "\n".join(out)


def render_summary(payload: dict) -> str:
    idx = payload["rot_index"]["overall"]
    counts: dict[str, int] = {}
    for f in payload["findings"]:
        counts[f["severity"]] = counts.get(f["severity"], 0) + 1
    parts = [f"{counts[s]} {s}" for s in _SEV_ORDER if counts.get(s)]
    line = f"rot index {idx}/100 · " + (", ".join(parts) if parts else "no findings")
    if payload.get("skipped"):
        line += f" · {len(payload['skipped'])} check(s) skipped"
    return line


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="scan.py", description="Detect configuration rot in a repository.")
    ap.add_argument("--repo", default=".", help="repository root (default: .)")
    ap.add_argument("--json", metavar="PATH", help="write findings.json here")
    ap.add_argument("--format", choices=["json", "markdown", "summary"], default="markdown",
                    help="stdout format (default: markdown)")
    ap.add_argument("--online", action="store_true",
                    help="allow network: registry version checks and native audit tools")
    ap.add_argument("--categories", help="comma-separated subset of " + ",".join(CATEGORIES))
    ap.add_argument("--detectors", help="comma-separated subset of " + ",".join(DETECTORS))
    ap.add_argument("--exclude", action="append", metavar="REGEX", default=[],
                    help="skip paths matching this regex (repeatable); also read from\n"
                         "CONFIGROT.md `exclude`. Use for vendored example or fixture\n"
                         "projects, whose rot is not this repo's rot")
    ap.add_argument("--min-severity", choices=_SEV_ORDER, default="low")
    ap.add_argument("--no-state", action="store_true",
                    help="do not read or write .configrot/state.json")
    ap.add_argument("--exit-zero", action="store_true",
                    help="always exit 0 (default exit code encodes worst severity)")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.repo)
    if not os.path.isdir(root):
        print(f"scan.py: not a directory: {root}", file=sys.stderr)
        return 64

    ctx = Context(online=args.online, today=_dt.date.today())
    policy = load_policy(root)
    exclude = list(args.exclude) + list(policy.get("exclude", []) or [])
    inv = inventory.build(root, exclude=exclude)

    selected = set(args.detectors.split(",")) if args.detectors else set(DETECTORS)
    findings: list[Finding] = []
    for name in DETECTORS:
        if name not in selected:
            continue
        module = DETECTORS[name]
        if name == "drift":
            from detectors import drift as module  # noqa: PLC0415
        try:
            findings += module.run(inv, ctx)
        except Exception as exc:  # a broken detector must not lose the other results
            ctx.skip(name, f"detector raised {type(exc).__name__}: {exc}")

    if args.categories:
        keep = {c.strip().upper() for c in args.categories.split(",")}
        findings = [f for f in findings if f.category in keep]

    floor = SEVERITY_RANK[args.min_severity]
    findings = [f for f in findings if SEVERITY_RANK.get(f.severity, 0) >= floor]

    findings, suppressed = apply_policy(findings, policy)
    findings.sort(key=lambda f: (-SEVERITY_RANK.get(f.severity, 0), f.category, f.id))

    index = rot_index(findings)
    trend = None
    if not args.no_state:
        state = update_state(root, index, findings)
        hist = state.get("history", [])
        if len(hist) >= 2:
            prev = hist[-2]
            delta = index["overall"] - prev["rot_index"]
            arrow = "improved" if delta < 0 else "worsened" if delta > 0 else "unchanged"
            trend = (f"{prev['rot_index']} → {index['overall']} "
                     f"({arrow} by {abs(delta)}) since {prev['date']}")

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "repo": {"root": os.path.relpath(root), "ecosystems": sorted(inv.ecosystems)},
        "rot_index": index,
        "trend": trend,
        "findings": [f.to_dict() for f in findings],
        "suppressed": suppressed,
        "skipped": ctx.skipped,
        "notes": inv.notes,
        "policy_present": bool(policy),
        "excluded": exclude,
    }

    if args.json:
        os.makedirs(os.path.dirname(os.path.abspath(args.json)) or ".", exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)

    if args.format == "json":
        print(json.dumps(payload, indent=2))
    elif args.format == "summary":
        print(render_summary(payload))
    else:
        print(render_markdown(payload))

    if args.exit_zero:
        return 0
    return SEVERITY_RANK.get(worst_severity(findings), 0)


if __name__ == "__main__":
    raise SystemExit(main())
