#!/usr/bin/env python3
"""Emit GitHub Actions `key=value` output lines from a findings.json.

Exists so the composite action does not have to embed a heredoc inside a YAML
block scalar, where the terminator cannot be indented and the whole thing
silently breaks.

    python3 gh_outputs.py findings.json >> "$GITHUB_OUTPUT"
"""

from __future__ import annotations

import json
import sys

RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: gh_outputs.py <findings.json>", file=sys.stderr)
        return 64
    try:
        with open(sys.argv[1], encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        print(f"gh_outputs.py: {exc}", file=sys.stderr)
        return 65

    findings = data.get("findings", [])
    worst = max((f["severity"] for f in findings), key=lambda s: RANK.get(s, 0),
                default="none")
    print(f"rot-index={data.get('rot_index', {}).get('overall', 0)}")
    print(f"finding-count={len(findings)}")
    print(f"worst-severity={worst}")
    print(f"skipped-count={len(data.get('skipped', []))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
