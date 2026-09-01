"""Repository inventory — the shared substrate every other detector reads.

The inventory answers three questions: what config surfaces exist, what does
this project depend on, and how many different places declare a runtime
version. Only that last one takes real care, because the answer is routinely
"seven, and they disagree".
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

from common import (
    line_of,
    parse_toml,
    read_json,
    read_text,
    scan_yaml_lines,
    walk,
)


@dataclass
class Dep:
    name: str
    spec: str
    manifest: str
    ecosystem: str
    dev: bool = False
    line: int | None = None


@dataclass
class VersionDecl:
    """One place in the repo that claims to know a runtime's version."""
    runtime: str          # node | python | go | java | ruby
    spec: str
    file: str
    line: int | None
    source: str           # engines | nvmrc | ci-matrix | dockerfile | tool-config ...
    authority: int = 1    # higher = more likely to be the operative truth


@dataclass
class Inventory:
    root: str
    files: set[str] = field(default_factory=set)
    ecosystems: set[str] = field(default_factory=set)
    deps: list[Dep] = field(default_factory=list)
    versions: list[VersionDecl] = field(default_factory=list)
    lockfiles: list[str] = field(default_factory=list)
    workflows: dict[str, list[tuple[int, str, str]]] = field(default_factory=dict)
    dockerfiles: dict[str, str] = field(default_factory=dict)
    manifests: list[str] = field(default_factory=list)
    package_json: dict[str, Any] | None = None
    pyproject: dict[str, Any] | None = None
    notes: list[str] = field(default_factory=list)

    def has(self, *names: str) -> bool:
        return any(n in self.files for n in names)

    def dep(self, name: str) -> Dep | None:
        for d in self.deps:
            if d.name == name:
                return d
        return None

    def glob(self, pattern: str) -> list[str]:
        rx = re.compile(pattern)
        return [f for f in sorted(self.files) if rx.search(f)]


LOCKFILES = {
    "package-lock.json": "npm",
    "npm-shrinkwrap.json": "npm",
    "yarn.lock": "yarn",
    "pnpm-lock.yaml": "pnpm",
    "bun.lockb": "bun",
    "poetry.lock": "poetry",
    "uv.lock": "uv",
    "Pipfile.lock": "pipenv",
    "Cargo.lock": "cargo",
    "go.sum": "go",
    "Gemfile.lock": "bundler",
    "composer.lock": "composer",
}

ECOSYSTEM_MARKERS = {
    "package.json": "node",
    "pyproject.toml": "python",
    "requirements.txt": "python",
    "setup.py": "python",
    "setup.cfg": "python",
    "Pipfile": "python",
    "go.mod": "go",
    "Cargo.toml": "rust",
    "Gemfile": "ruby",
    "pom.xml": "jvm",
    "build.gradle": "jvm",
    "build.gradle.kts": "jvm",
    "composer.json": "php",
}


def build(root: str, exclude: list[str] | None = None) -> Inventory:
    inv = Inventory(root=root)
    inv.files = set(walk(root))
    if exclude:
        rx = [re.compile(p) for p in exclude]
        inv.files = {f for f in inv.files if not any(r.search(f) for r in rx)}

    for f in sorted(inv.files):
        base = os.path.basename(f)
        if base in ECOSYSTEM_MARKERS:
            inv.ecosystems.add(ECOSYSTEM_MARKERS[base])
            inv.manifests.append(f)
        if base in LOCKFILES:
            inv.lockfiles.append(f)
        if base == "Dockerfile" or base.startswith("Dockerfile."):
            inv.ecosystems.add("docker")
            txt = read_text(root, f)
            if txt:
                inv.dockerfiles[f] = txt
        if f.startswith(".github/workflows/") and f.endswith((".yml", ".yaml")):
            inv.ecosystems.add("github-actions")
            txt = read_text(root, f)
            if txt:
                inv.workflows[f] = scan_yaml_lines(txt)
        if base.endswith((".tf", ".tfvars")):
            inv.ecosystems.add("terraform")

    _node(inv)
    _python(inv)
    _go(inv)
    _rust(inv)
    _pin_files(inv)
    _ci_versions(inv)
    _docker_versions(inv)
    return inv


# ---------------------------------------------------------------- node

def _node(inv: Inventory) -> None:
    if "package.json" not in inv.files:
        return
    pkg = read_json(inv.root, "package.json")
    if not isinstance(pkg, dict):
        inv.notes.append("package.json is present but could not be parsed as JSON")
        return
    inv.package_json = pkg
    raw = read_text(inv.root, "package.json") or ""

    for key, dev in (("dependencies", False), ("devDependencies", True),
                     ("optionalDependencies", True), ("peerDependencies", True)):
        for name, spec in (pkg.get(key) or {}).items():
            inv.deps.append(Dep(
                name=name, spec=str(spec), manifest="package.json",
                ecosystem="node", dev=dev,
                line=line_of(raw, f'"{name}"'),
            ))

    engines = (pkg.get("engines") or {})
    if isinstance(engines, dict) and engines.get("node"):
        inv.versions.append(VersionDecl(
            "node", str(engines["node"]), "package.json",
            line_of(raw, '"node"'), "engines", authority=2))

    volta = pkg.get("volta")
    if isinstance(volta, dict) and volta.get("node"):
        inv.versions.append(VersionDecl(
            "node", str(volta["node"]), "package.json",
            line_of(raw, '"volta"'), "volta", authority=3))


# ---------------------------------------------------------------- python

_REQ_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*([<>=!~^].*)?$")


def _python(inv: Inventory) -> None:
    if "pyproject.toml" in inv.files:
        raw = read_text(inv.root, "pyproject.toml") or ""
        data = parse_toml(raw)
        inv.pyproject = data
        project = data.get("project") or {}
        rp = project.get("requires-python")
        if rp:
            inv.versions.append(VersionDecl(
                "python", str(rp), "pyproject.toml",
                line_of(raw, "requires-python"), "requires-python", authority=2))
        for spec in project.get("dependencies") or []:
            if isinstance(spec, str):
                _add_req(inv, spec, "pyproject.toml", raw)
        extras = project.get("optional-dependencies") or {}
        if isinstance(extras, dict):
            for group in extras.values():
                for spec in group if isinstance(group, list) else []:
                    if isinstance(spec, str):
                        _add_req(inv, spec, "pyproject.toml", raw, dev=True)
        poetry = ((data.get("tool") or {}).get("poetry") or {})
        for name, spec in (poetry.get("dependencies") or {}).items():
            if name.lower() == "python":
                inv.versions.append(VersionDecl(
                    "python", str(spec), "pyproject.toml",
                    line_of(raw, "python ="), "poetry-python", authority=2))
                continue
            inv.deps.append(Dep(name, str(spec), "pyproject.toml", "python",
                                line=line_of(raw, name)))

    for req in inv.glob(r"(^|/)requirements[^/]*\.txt$"):
        raw = read_text(inv.root, req) or ""
        for i, line in enumerate(raw.splitlines(), start=1):
            line = line.split("#")[0].strip()
            if not line or line.startswith("-"):
                continue
            m = _REQ_RE.match(line)
            if m:
                inv.deps.append(Dep(m.group(1), (m.group(2) or "").strip(),
                                    req, "python", line=i))


def _add_req(inv: Inventory, spec: str, manifest: str, raw: str, dev: bool = False) -> None:
    m = _REQ_RE.match(spec.split(";")[0].strip())
    if m:
        inv.deps.append(Dep(m.group(1), (m.group(2) or "").strip(), manifest,
                            "python", dev=dev, line=line_of(raw, m.group(1))))


# ---------------------------------------------------------------- go / rust

def _go(inv: Inventory) -> None:
    if "go.mod" not in inv.files:
        return
    raw = read_text(inv.root, "go.mod") or ""
    for i, line in enumerate(raw.splitlines(), start=1):
        s = line.strip()
        if s.startswith("go "):
            inv.versions.append(VersionDecl("go", s[3:].strip(), "go.mod", i,
                                            "go-directive", authority=3))
        m = re.match(r"^\s*([\w./-]+)\s+(v[\d][^\s/]*)", line)
        if m and not s.startswith(("module", "go ", "//")):
            inv.deps.append(Dep(m.group(1), m.group(2), "go.mod", "go", line=i))


def _rust(inv: Inventory) -> None:
    if "Cargo.toml" not in inv.files:
        return
    raw = read_text(inv.root, "Cargo.toml") or ""
    data = parse_toml(raw)
    pkg = data.get("package") or {}
    if pkg.get("rust-version"):
        inv.versions.append(VersionDecl("rust", str(pkg["rust-version"]), "Cargo.toml",
                                        line_of(raw, "rust-version"), "rust-version", 2))
    if pkg.get("edition"):
        inv.versions.append(VersionDecl("rust-edition", str(pkg["edition"]), "Cargo.toml",
                                        line_of(raw, "edition"), "edition", 2))
    for section, dev in (("dependencies", False), ("dev-dependencies", True)):
        for name, spec in (data.get(section) or {}).items():
            v = spec.get("version") if isinstance(spec, dict) else spec
            inv.deps.append(Dep(name, str(v), "Cargo.toml", "rust", dev=dev,
                                line=line_of(raw, name)))


# ---------------------------------------------------------------- pin files

PIN_FILES = {
    ".nvmrc": ("node", "nvmrc", 2),
    ".node-version": ("node", "node-version", 2),
    ".python-version": ("python", "python-version", 2),
    ".ruby-version": ("ruby", "ruby-version", 2),
    ".go-version": ("go", "go-version", 2),
}


def _pin_files(inv: Inventory) -> None:
    for fname, (runtime, source, auth) in PIN_FILES.items():
        if fname in inv.files:
            txt = (read_text(inv.root, fname) or "").strip()
            if txt:
                inv.versions.append(VersionDecl(runtime, txt.splitlines()[0].strip(),
                                                fname, 1, source, auth))

    if ".tool-versions" in inv.files:
        raw = read_text(inv.root, ".tool-versions") or ""
        for i, line in enumerate(raw.splitlines(), start=1):
            parts = line.split()
            if len(parts) >= 2 and not line.strip().startswith("#"):
                inv.versions.append(VersionDecl(parts[0].lower(), parts[1],
                                                ".tool-versions", i, "asdf", 2))


# ---------------------------------------------------------------- ci + docker

CI_VERSION_KEYS = {
    "node-version": "node",
    "python-version": "python",
    "go-version": "go",
    "java-version": "java",
    "ruby-version": "ruby",
}


def _ci_versions(inv: Inventory) -> None:
    """CI carries the highest authority: it is the version actually exercised."""
    for wf, facts in inv.workflows.items():
        for line, kind, value in facts:
            runtime = CI_VERSION_KEYS.get(kind)
            if runtime and not value.startswith("$"):
                for v in re.findall(r"[\d]+(?:\.[\dxX*]+)*", value):
                    inv.versions.append(VersionDecl(runtime, v, wf, line,
                                                    "ci-matrix", authority=4))


_FROM_RE = re.compile(r"^\s*FROM\s+(?:--platform=\S+\s+)?([^\s]+)", re.IGNORECASE)
_IMAGE_RUNTIMES = ("node", "python", "golang", "ruby", "openjdk", "eclipse-temurin", "rust", "php")


def _docker_versions(inv: Inventory) -> None:
    for path, text in inv.dockerfiles.items():
        for i, line in enumerate(text.splitlines(), start=1):
            m = _FROM_RE.match(line)
            if not m:
                continue
            image = m.group(1)
            name, _, tag = image.partition(":")
            name = name.split("/")[-1]
            if name in _IMAGE_RUNTIMES and tag and not tag.startswith("$"):
                runtime = {"golang": "go", "openjdk": "java",
                           "eclipse-temurin": "java"}.get(name, name)
                inv.versions.append(VersionDecl(runtime, tag, path, i,
                                                "dockerfile", authority=3))
