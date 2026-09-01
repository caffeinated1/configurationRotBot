"""DRIFT: how far behind current the declared dependencies are. Requires network.

DRIFT is the one category of rot that existing tooling already solves well, so
this detector deliberately under-reports: it raises individual findings only for
dependencies two or more majors behind (where the gap implies migration work,
which is this project's actual job) and folds everything else into a single
summary. Reproducing Renovate's per-package PR firehose here would add noise
without adding information.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from common import Evidence, Finding, major, vtuple

DETECTOR = "drift"

USER_AGENT = "configurationRotBot/0.1 (+https://github.com/caffeinated1/configurationRotBot)"
TIMEOUT = 8
CACHE_TTL = 6 * 3600
MAX_LOOKUPS = 300


def _fetch(url: str) -> dict | None:
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, TimeoutError, OSError):
        return None


def _latest_npm(name: str) -> str | None:
    d = _fetch(f"https://registry.npmjs.org/{urllib.parse.quote(name, safe='@')}/latest")
    return d.get("version") if d else None


def _latest_pypi(name: str) -> str | None:
    d = _fetch(f"https://pypi.org/pypi/{urllib.parse.quote(name)}/json")
    return (d.get("info") or {}).get("version") if d else None


def _latest_crates(name: str) -> str | None:
    d = _fetch(f"https://crates.io/api/v1/crates/{urllib.parse.quote(name)}")
    return (d.get("crate") or {}).get("max_stable_version") if d else None


def _latest_go(name: str) -> str | None:
    d = _fetch(f"https://proxy.golang.org/{name.lower()}/@latest")
    return d.get("Version") if d else None


RESOLVERS = {"node": _latest_npm, "python": _latest_pypi,
             "rust": _latest_crates, "go": _latest_go}


def _cache_path(root: str) -> str:
    """A user-level cache directory, never inside the repository under scan.

    The read-only guarantee is what makes scan.py safe to point at CI
    workspaces and at code you have not read, and a cache file is still a
    write. Keying by repo path keeps unrelated projects from colliding.
    """
    base = os.environ.get("XDG_CACHE_HOME") or os.path.join(
        os.path.expanduser("~"), ".cache")
    key = str(abs(hash(os.path.abspath(root))) % (10 ** 12))
    return os.path.join(base, "configrotbot", f"registry-{key}.json")


def _load_cache(root: str) -> dict:
    try:
        with open(_cache_path(root), "r", encoding="utf-8") as fh:
            cache = json.load(fh)
        now = time.time()
        return {k: v for k, v in cache.items()
                if isinstance(v, list) and len(v) == 2 and now - v[1] < CACHE_TTL}
    except (OSError, ValueError):
        return {}


def _save_cache(root: str, cache: dict) -> None:
    try:
        os.makedirs(os.path.dirname(_cache_path(root)), exist_ok=True)
        with open(_cache_path(root), "w", encoding="utf-8") as fh:
            json.dump(cache, fh)
    except OSError:
        pass  # a missing cache costs time, not correctness


def run(inv, ctx) -> list[Finding]:
    if not ctx.online:
        ctx.skip(DETECTOR, "offline mode: pass --online to check versions against registries")
        return []

    targets = [d for d in inv.deps
               if d.ecosystem in RESOLVERS and vtuple(d.spec)
               and not d.name.startswith(("file:", "link:", "workspace:"))]
    # Deduplicate: the same package often appears in several manifests.
    unique: dict[tuple[str, str], object] = {}
    for d in targets:
        unique.setdefault((d.ecosystem, d.name), d)
    targets = list(unique.values())

    if len(targets) > MAX_LOOKUPS:
        ctx.skip(DETECTOR,
                 f"checked the first {MAX_LOOKUPS} of {len(targets)} dependencies "
                 "(registry rate limits)")
        targets = targets[:MAX_LOOKUPS]

    cache = _load_cache(inv.root)
    to_fetch = [d for d in targets if f"{d.ecosystem}:{d.name}" not in cache]

    def resolve(dep):
        return f"{dep.ecosystem}:{dep.name}", RESOLVERS[dep.ecosystem](dep.name)

    if to_fetch:
        with ThreadPoolExecutor(max_workers=8) as pool:
            for key, latest in pool.map(resolve, to_fetch):
                if latest:
                    cache[key] = [latest, time.time()]
        _save_cache(inv.root, cache)

    behind: list[tuple[object, str, int]] = []
    unresolved = 0
    for d in targets:
        entry = cache.get(f"{d.ecosystem}:{d.name}")
        if not entry:
            unresolved += 1
            continue
        latest = entry[0]
        cur, new = major(d.spec), major(latest)
        if cur is None or new is None:
            continue
        gap = new - cur
        if gap > 0:
            behind.append((d, latest, gap))

    if unresolved:
        ctx.skip(DETECTOR, f"{unresolved} package(s) could not be resolved against their registry")
    if not behind:
        return []

    behind.sort(key=lambda x: -x[2])
    out: list[Finding] = []

    for d, latest, gap in behind:
        if gap < 2:
            continue
        out.append(Finding(
            id=f"DRIFT.major.{d.ecosystem}.{d.name}",
            category="DRIFT",
            severity="high" if gap >= 3 else "medium",
            title=f"`{d.name}` is {gap} major versions behind ({d.spec} → {latest})",
            evidence=[Evidence(d.manifest, d.line, f"{d.name} {d.spec}")],
            detail=(
                f"A gap of {gap} majors means the upgrade crosses {gap} sets of breaking "
                "changes. These do not get cheaper with time — each release the project "
                "skips adds another migration to the eventual jump."
            ),
            recommendation=(
                f"Upgrade one major at a time ({' → '.join(str(major(d.spec) + i) for i in range(1, gap + 1))}), "
                "running the test suite between each. Read the changelog for each major."
            ),
            effort="large" if gap >= 3 else "medium",
            autofix="assisted", blast_radius=["build", "runtime"],
            detector=DETECTOR,
        ))

    minor_gap = [b for b in behind if b[2] == 1]
    if minor_gap:
        out.append(Finding(
            id="DRIFT.one-major-behind",
            category="DRIFT",
            severity="low",
            title=f"{len(minor_gap)} dependencies are one major version behind",
            evidence=[Evidence(d.manifest, d.line, f"{d.name} {d.spec} → {latest}")
                      for d, latest, _ in minor_gap[:25]],
            detail=("; ".join(f"{d.name} {d.spec}→{latest}" for d, latest, _ in minor_gap)),
            recommendation=(
                "This is exactly what Dependabot or Renovate exists to do. Configure one "
                "rather than upgrading these by hand — this tool is more useful on the "
                "migrations those upgrades require than on the version numbers themselves."
            ),
            effort="small", autofix="assisted", blast_radius=["build"],
            detector=DETECTOR,
        ))
    return out
