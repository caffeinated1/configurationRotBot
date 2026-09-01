#!/usr/bin/env python3
"""Assert the scanner imports nothing outside the standard library.

The zero-dependency guarantee is load-bearing: a tool that diagnoses dependency
rot cannot itself require `pip install`, and it is what makes `scan.py` runnable
from a README one-liner on any machine with Python. That guarantee is also easy
to break by accident, so it is checked rather than documented and hoped for.

    python3 tests/test_stdlib_only.py
"""

from __future__ import annotations

import ast
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "config-rot", "scripts")

# Modules that are part of this package rather than imports of anything external.
LOCAL = {"common", "detectors", "scan"}

# Python 3.9 is the declared floor, so sys.stdlib_module_names (3.10+) cannot be
# relied on. This is the stdlib surface the scanner is permitted to use.
ALLOWED = {
    "__future__", "argparse", "ast", "collections", "concurrent", "dataclasses",
    "datetime", "json", "math", "os", "pathlib", "re", "shutil", "subprocess",
    "sys", "tempfile", "time", "tomllib", "typing", "unittest", "urllib",
}


def python_files(directory: str):
    for dirpath, _, filenames in os.walk(directory):
        if "__pycache__" in dirpath:
            continue
        for name in filenames:
            if name.endswith(".py"):
                yield os.path.join(dirpath, name)


def top_level_imports(path: str) -> set[str]:
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read(), filename=path)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                names.add(node.module.split(".")[0])
    return names


class StdlibOnly(unittest.TestCase):
    def test_scanner_imports_only_stdlib_and_itself(self):
        offenders: dict[str, set[str]] = {}
        for path in python_files(SCRIPTS):
            extra = top_level_imports(path) - ALLOWED - LOCAL
            if extra:
                offenders[os.path.relpath(path, ROOT)] = extra
        self.assertFalse(
            offenders,
            "the scanner must import only the standard library:\n  "
            + "\n  ".join(f"{k}: {sorted(v)}" for k, v in offenders.items()))

    def test_sources_parse_on_the_declared_floor(self):
        """Catches syntax newer than the version matrix claims to support."""
        for path in python_files(SCRIPTS):
            with open(path, encoding="utf-8") as fh:
                try:
                    ast.parse(fh.read(), filename=path)
                except SyntaxError as exc:
                    self.fail(f"{os.path.relpath(path, ROOT)}: {exc}")

    def test_scripts_are_executable_and_have_shebangs(self):
        for name in ("scan.py", "refresh_data.py", "gh_outputs.py"):
            path = os.path.join(SCRIPTS, name)
            self.assertTrue(os.path.exists(path), f"{name} is missing")
            with open(path, encoding="utf-8") as fh:
                self.assertTrue(fh.readline().startswith("#!"),
                                f"{name} has no shebang")
            self.assertTrue(os.access(path, os.X_OK), f"{name} is not executable")


if __name__ == "__main__":
    unittest.main(verbosity=2)
