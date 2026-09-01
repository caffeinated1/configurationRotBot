#!/usr/bin/env python3
"""Refresh data/eol.json from endoflife.date.

The bundled dataset is a snapshot so that scans work offline. It goes stale by
definition — a tool that diagnoses staleness should not be smug about its own —
so this script replaces the `cycles` block with live upstream data.

    python3 refresh_data.py            # rewrite data/eol.json
    python3 refresh_data.py --check    # report drift, change nothing (exit 1 if stale)

Only `cycles` is refreshed. The `github_runners` and `github_actions` blocks are
hand-maintained because GitHub publishes no equivalent machine-readable feed.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
import urllib.error
import urllib.request

API = "https://endoflife.date/api/{product}.json"

# Local runtime name -> endoflife.date product slug.
PRODUCTS = {
    "node": "nodejs", "python": "python", "go": "go", "ruby": "ruby",
    "php": "php", "java": "oracle-jdk", "dotnet": "dotnet",
    "alpine": "alpine", "debian": "debian", "ubuntu": "ubuntu",
    "django": "django", "rails": "rails",
}


def fetch(product: str) -> list | None:
    req = urllib.request.Request(
        API.format(product=product),
        headers={"User-Agent": "configurationRotBot/0.1", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError) as exc:
        print(f"  ! {product}: {exc}", file=sys.stderr)
        return None


def normalise(entries: list) -> dict[str, str]:
    """endoflife.date returns eol as an ISO date, or a bool for rolling releases."""
    out: dict[str, str] = {}
    for entry in entries:
        cycle, eol = entry.get("cycle"), entry.get("eol")
        if not cycle or not isinstance(eol, str):
            continue
        out[str(cycle)] = eol
        if entry.get("codename"):
            out[str(entry["codename"]).lower()] = eol
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="report drift without writing; exit 1 if the snapshot is stale")
    args = ap.parse_args()

    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "eol.json")
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    drift, failures = [], []
    for runtime, product in PRODUCTS.items():
        print(f"  fetching {product}...", file=sys.stderr)
        entries = fetch(product)
        if not entries:
            failures.append(runtime)
            continue
        fresh = normalise(entries)
        if not fresh:
            failures.append(runtime)
            continue
        cycle = data["cycles"].setdefault(runtime, {"url": f"https://endoflife.date/{product}"})
        current = cycle.get("eol", {})
        for key, val in fresh.items():
            if current.get(key) != val:
                drift.append(f"{runtime} {key}: {current.get(key, '—')} → {val}")
        if not args.check:
            cycle["eol"] = {**current, **fresh}

    if failures:
        print(f"\ncould not refresh: {', '.join(failures)}", file=sys.stderr)

    if args.check:
        if drift:
            print(f"\n{len(drift)} cycle(s) differ from upstream:")
            for d in drift[:40]:
                print(f"  {d}")
            return 1
        print("\neol.json matches upstream.")
        return 0

    data["_updated"] = _dt.date.today().isoformat()
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")
    print(f"\nupdated {len(drift)} cycle(s) in data/eol.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
