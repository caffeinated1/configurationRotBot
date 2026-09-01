"""HAZARD: known vulnerabilities, via the ecosystem's own auditing tool.

This detector deliberately bundles no vulnerability database. A stale CVE list
shipped inside a tool that diagnoses staleness would be self-refuting, and the
native tools are better at this than anything this project could maintain.

When a tool is not installed, that is reported as a skip rather than silently
producing a clean result. A scan that quietly checked nothing is worse than no
scan, because it manufactures confidence.
"""

from __future__ import annotations

import json
import shutil
import subprocess

from common import Evidence, Finding

DETECTOR = "audit"

TIMEOUT = 180


def _run(cmd: list[str], cwd: str) -> tuple[int, str]:
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                              timeout=TIMEOUT, check=False)
        return proc.returncode, proc.stdout
    except (subprocess.TimeoutExpired, OSError):
        return -1, ""


def run(inv, ctx) -> list[Finding]:
    if not ctx.online:
        ctx.skip(DETECTOR, "offline mode: advisory lookup needs network; pass --online")
        return []

    out: list[Finding] = []
    if "node" in inv.ecosystems:
        out += _npm(inv, ctx)
    if "python" in inv.ecosystems:
        out += _pip(inv, ctx)
    if "rust" in inv.ecosystems:
        out += _cargo(inv, ctx)
    if "go" in inv.ecosystems:
        out += _go(inv, ctx)
    return out


def _finding(tool: str, counts: dict, manifest: str, cmd: str) -> Finding:
    critical = counts.get("critical", 0)
    high = counts.get("high", 0)
    total = sum(counts.values())
    severity = "critical" if critical else "high" if high else "medium"
    summary = ", ".join(f"{v} {k}" for k, v in counts.items() if v)
    return Finding(
        id=f"HAZARD.advisories.{tool}",
        category="HAZARD",
        severity=severity,
        title=f"{tool} reports {total} known vulnerabilities ({summary})",
        evidence=[Evidence(manifest)],
        detail=(
            f"Reported by `{cmd}`. Counts include transitive dependencies, so the fix is "
            "often a single upgrade of a direct dependency rather than {total} separate "
            "changes. Check whether the advisories are reachable from your code before "
            "treating the count as the priority."
        ),
        recommendation=(
            f"Run `{cmd}` for the detail. Apply the non-breaking fixes first, then treat "
            "anything requiring a major upgrade as its own scoped change."
        ),
        effort="medium", autofix="assisted", blast_radius=["runtime", "security"],
        detector=DETECTOR,
    )


def _npm(inv, ctx) -> list[Finding]:
    if not shutil.which("npm"):
        ctx.skip(DETECTOR, "npm is not on PATH — JavaScript advisories were not checked")
        return []
    if not any(f.endswith("package-lock.json") for f in inv.lockfiles):
        ctx.skip(DETECTOR, "npm audit needs package-lock.json — advisories were not checked")
        return []
    code, stdout = _run(["npm", "audit", "--json", "--audit-level=low"], inv.root)
    if not stdout:
        ctx.skip(DETECTOR, "npm audit produced no output")
        return []
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        ctx.skip(DETECTOR, "npm audit output could not be parsed")
        return []
    counts = ((data.get("metadata") or {}).get("vulnerabilities") or {})
    counts = {k: v for k, v in counts.items() if k != "total" and isinstance(v, int) and v}
    if not counts:
        return []
    return [_finding("npm audit", counts, "package-lock.json", "npm audit")]


def _pip(inv, ctx) -> list[Finding]:
    if not shutil.which("pip-audit"):
        ctx.skip(DETECTOR, "pip-audit is not installed — Python advisories were not checked "
                           "(`pipx install pip-audit`)")
        return []
    code, stdout = _run(["pip-audit", "-f", "json", "--progress-spinner=off"], inv.root)
    if not stdout:
        ctx.skip(DETECTOR, "pip-audit produced no output")
        return []
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        ctx.skip(DETECTOR, "pip-audit output could not be parsed")
        return []
    deps = data.get("dependencies", data if isinstance(data, list) else [])
    vulnerable = [d for d in deps if d.get("vulns")]
    if not vulnerable:
        return []
    total = sum(len(d["vulns"]) for d in vulnerable)
    return [Finding(
        id="HAZARD.advisories.pip-audit",
        category="HAZARD", severity="high",
        title=f"pip-audit reports {total} advisories across {len(vulnerable)} packages",
        evidence=[Evidence("pyproject.toml" if inv.pyproject else "requirements.txt")],
        detail="; ".join(f"{d['name']} {d.get('version','')}" for d in vulnerable[:15]),
        recommendation="Run `pip-audit --fix` for the mechanical upgrades, then handle the rest.",
        effort="medium", autofix="assisted", blast_radius=["runtime", "security"],
        detector=DETECTOR,
    )]


def _cargo(inv, ctx) -> list[Finding]:
    if not shutil.which("cargo-audit") and not shutil.which("cargo"):
        ctx.skip(DETECTOR, "cargo-audit is not installed — Rust advisories were not checked")
        return []
    code, stdout = _run(["cargo", "audit", "--json"], inv.root)
    if not stdout:
        ctx.skip(DETECTOR, "cargo audit is unavailable (`cargo install cargo-audit`)")
        return []
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        return []
    count = len(((data.get("vulnerabilities") or {}).get("list")) or [])
    if not count:
        return []
    return [_finding("cargo audit", {"high": count}, "Cargo.lock", "cargo audit")]


def _go(inv, ctx) -> list[Finding]:
    if not shutil.which("govulncheck"):
        ctx.skip(DETECTOR, "govulncheck is not installed — Go advisories were not checked "
                           "(`go install golang.org/x/vuln/cmd/govulncheck@latest`)")
        return []
    code, stdout = _run(["govulncheck", "-json", "./..."], inv.root)
    if not stdout:
        return []
    ids = {line.split('"id":"')[1].split('"')[0]
           for line in stdout.splitlines() if '"id":"GO-' in line}
    if not ids:
        return []
    return [_finding("govulncheck", {"high": len(ids)}, "go.mod", "govulncheck ./...")]
