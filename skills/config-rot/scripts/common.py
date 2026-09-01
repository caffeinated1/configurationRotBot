"""Shared types and helpers for configuration-rot detectors.

Python 3.9+, standard library only. A tool that diagnoses dependency rot must
not itself acquire dependencies.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Iterable

SCHEMA_VERSION = "1.0"

CATEGORIES = ("DRIFT", "DECAY", "CRUFT", "HAZARD", "DIVERGENCE", "STAGNATION")

SEVERITIES = ("critical", "high", "medium", "low", "info")

SEVERITY_WEIGHT = {"critical": 40, "high": 15, "medium": 5, "low": 1, "info": 0}
SEVERITY_RANK = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}

# HAZARD and DECAY are double-weighted in the overall index: something that is
# already unsupported or exploitable is qualitatively worse than something that
# is merely behind.
CATEGORY_WEIGHT = {
    "HAZARD": 2.0,
    "DECAY": 2.0,
    "DIVERGENCE": 1.5,
    "STAGNATION": 1.0,
    "DRIFT": 1.0,
    "CRUFT": 0.5,
}


@dataclass
class Evidence:
    file: str
    line: int | None = None
    text: str | None = None


@dataclass
class Finding:
    id: str
    category: str
    severity: str
    title: str
    evidence: list[Evidence] = field(default_factory=list)
    detail: str = ""
    recommendation: str = ""
    effort: str = "small"          # trivial | small | medium | large | epic
    autofix: str = "assisted"      # safe | assisted | manual
    blast_radius: list[str] = field(default_factory=list)
    references: list[str] = field(default_factory=list)
    detector: str = ""
    confidence: str = "high"       # high | medium | low

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["evidence"] = [
            {k: v for k, v in asdict(e).items() if v is not None} for e in self.evidence
        ]
        return d


# --------------------------------------------------------------------------
# Version handling
#
# Deliberately permissive rather than strictly semver: this code reads
# real-world manifests where "18", "^3.2", ">=1.0,<2", "v20.11.1", and
# "3.11-slim" all appear and all need to become something comparable.
# --------------------------------------------------------------------------

_VERSION_RE = re.compile(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?")


def vtuple(spec: str | None) -> tuple[int, int, int] | None:
    """Extract the first (major, minor, patch) found in a version-ish string."""
    if not spec:
        return None
    m = _VERSION_RE.search(str(spec))
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2) or 0), int(m.group(3) or 0))


def major(spec: str | None) -> int | None:
    t = vtuple(spec)
    return t[0] if t else None


def vcmp(a: str | None, b: str | None) -> int:
    """-1 if a<b, 0 if equal-ish, 1 if a>b. Unparseable sorts as equal."""
    ta, tb = vtuple(a), vtuple(b)
    if ta is None or tb is None:
        return 0
    return (ta > tb) - (ta < tb)


def is_pinned(spec: str | None) -> bool:
    """True when the spec allows exactly one version (no range operators)."""
    if not spec:
        return False
    return not re.search(r"[\^~><*|xX]|\s-\s", str(spec))


# --------------------------------------------------------------------------
# File helpers
# --------------------------------------------------------------------------

SKIP_DIRS = {
    ".git", "node_modules", "vendor", "dist", "build", "target", "__pycache__",
    ".venv", "venv", ".tox", ".mypy_cache", ".pytest_cache", ".next", ".nuxt",
    "coverage", ".gradle", ".idea", ".terraform", "site-packages", ".cache",
}

MAX_READ_BYTES = 512 * 1024


def walk(root: str, max_depth: int = 6) -> Iterable[str]:
    """Yield repo-relative paths, skipping vendored and generated trees."""
    root = os.path.abspath(root)
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        depth = 0 if rel_dir == "." else rel_dir.count(os.sep) + 1
        if depth >= max_depth:
            dirnames[:] = []
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".venv")]
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            yield rel.replace(os.sep, "/")


def read_text(root: str, rel: str) -> str | None:
    path = os.path.join(root, rel)
    try:
        if os.path.getsize(path) > MAX_READ_BYTES:
            return None
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except (OSError, ValueError):
        return None


def read_json(root: str, rel: str) -> Any | None:
    txt = read_text(root, rel)
    if txt is None:
        return None
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        return None


def line_of(text: str | None, needle: str, start: int = 0) -> int | None:
    """1-indexed line number of the first line containing `needle`.

    Evidence without a line number is nearly useless to a reader, so detectors
    should always try to resolve one rather than emitting a bare filename.
    """
    if not text or not needle:
        return None
    for i, line in enumerate(text.splitlines()[start:], start=start + 1):
        if needle in line:
            return i
    return None


def line_matching(text: str | None, pattern: str) -> tuple[int | None, str | None]:
    """1-indexed line number and content of the first line matching a regex."""
    if not text:
        return None, None
    rx = re.compile(pattern)
    for i, line in enumerate(text.splitlines(), start=1):
        if rx.search(line):
            return i, line.strip()
    return None, None


# --------------------------------------------------------------------------
# Minimal TOML reading
#
# tomllib landed in 3.11. Rather than force a floor of 3.11 or take a
# dependency, fall back to a small reader that handles the flat key/value and
# simple-array shapes that appear in pyproject.toml and Cargo.toml. It is not a
# general TOML parser and does not pretend to be.
# --------------------------------------------------------------------------

try:  # pragma: no cover - trivially environment-dependent
    import tomllib  # type: ignore

    def parse_toml(text: str) -> dict[str, Any]:
        try:
            return tomllib.loads(text)
        except Exception:
            return _fallback_toml(text)

except ImportError:  # pragma: no cover

    def parse_toml(text: str) -> dict[str, Any]:
        return _fallback_toml(text)


_TOML_TABLE = re.compile(r"^\s*\[\[?([^\]]+)\]\]?\s*$")
_TOML_KV = re.compile(r'^\s*([A-Za-z0-9_.\-"]+)\s*=\s*(.+?)\s*$')


def _toml_value(raw: str) -> Any:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        inner = raw[1:-1].strip()
        if not inner:
            return []
        return [_toml_value(p) for p in _split_top(inner)]
    if raw.startswith("{") and raw.endswith("}"):
        out: dict[str, Any] = {}
        for part in _split_top(raw[1:-1]):
            if "=" in part:
                k, v = part.split("=", 1)
                out[k.strip().strip('"\'')] = _toml_value(v)
        return out
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        return raw[1:-1]
    if raw in ("true", "false"):
        return raw == "true"
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _split_top(s: str) -> list[str]:
    """Split on commas that are not nested inside brackets, braces, or quotes."""
    parts, buf, depth, quote = [], [], 0, None
    for ch in s:
        if quote:
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch in "[{":
            depth += 1
        elif ch in "]}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append("".join(buf).strip())
            buf = []
            continue
        buf.append(ch)
    if "".join(buf).strip():
        parts.append("".join(buf).strip())
    return parts


def _fallback_toml(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    cursor = root
    for raw_line in text.splitlines():
        line = raw_line.split("#")[0].rstrip() if not raw_line.strip().startswith("#") else ""
        if not line.strip():
            continue
        tm = _TOML_TABLE.match(line)
        if tm:
            cursor = root
            for part in tm.group(1).split("."):
                part = part.strip().strip('"\'')
                cursor = cursor.setdefault(part, {})
                if not isinstance(cursor, dict):  # array-of-tables; good enough
                    cursor = {}
            continue
        kv = _TOML_KV.match(line)
        if kv:
            key = kv.group(1).strip().strip('"\'')
            cursor[key] = _toml_value(kv.group(2))
    return root


# --------------------------------------------------------------------------
# Minimal YAML reading for CI workflows
#
# GitHub Actions workflows are YAML, and there is no YAML parser in the stdlib.
# Detectors here need only a handful of scalar facts (which actions are used at
# which version, which runners, which language versions), all of which survive a
# line-oriented scan. Findings from this path are marked accordingly rather than
# pretending to a structural understanding the reader does not have.
# --------------------------------------------------------------------------

USES_RE = re.compile(r"^\s*-?\s*uses:\s*['\"]?([^'\"\s#]+)['\"]?")
RUNSON_RE = re.compile(r"^\s*runs-on:\s*['\"]?([^'\"\n#\[]+)['\"]?")
KEYVAL_RE = re.compile(r"^\s*([a-zA-Z0-9_-]+):\s*['\"]?([^'\"#\n]*?)['\"]?\s*$")


def scan_yaml_lines(text: str) -> list[tuple[int, str, str]]:
    """Yield (line_no, kind, value) for the workflow facts detectors need."""
    out: list[tuple[int, str, str]] = []
    for i, line in enumerate(text.splitlines(), start=1):
        m = USES_RE.match(line)
        if m:
            out.append((i, "uses", m.group(1)))
            continue
        m = RUNSON_RE.match(line)
        if m:
            out.append((i, "runs-on", m.group(1).strip()))
            continue
        m = KEYVAL_RE.match(line)
        if m and m.group(2).strip():
            key = m.group(1)
            if key in ("node-version", "python-version", "go-version", "java-version",
                       "ruby-version", "dotnet-version", "image", "container"):
                out.append((i, key, m.group(2).strip()))
    return out


def load_data(name: str) -> Any:
    """Load a bundled dataset from ../data/<name>."""
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, "..", "data", name)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
