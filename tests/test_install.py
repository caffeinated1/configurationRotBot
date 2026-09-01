#!/usr/bin/env python3
"""Tests for install.sh.

The installer is piped into a shell from a URL, so its failure modes are
unusually unforgiving: a broken flag parse or a policy file the scanner cannot
read lands directly in someone's repository. These checks run offline — the
network paths are exercised by hand and by the release process, not here.

    python3 tests/test_install.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALL = os.path.join(ROOT, "install.sh")
sys.path.insert(0, os.path.join(ROOT, "skills", "config-rot", "scripts"))

import scan  # noqa: E402


def run(*args, cwd=None):
    return subprocess.run(["sh", INSTALL, *args], cwd=cwd, capture_output=True,
                          text=True, timeout=60, check=False)


class Syntax(unittest.TestCase):
    def test_parses_as_posix_sh(self):
        proc = subprocess.run(["sh", "-n", INSTALL], capture_output=True, text=True,
                              check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_is_executable_with_a_shebang(self):
        with open(INSTALL, encoding="utf-8") as fh:
            self.assertEqual(fh.readline().strip(), "#!/bin/sh")
        self.assertTrue(os.access(INSTALL, os.X_OK))

    def test_uses_no_bashisms_that_dash_would_reject(self):
        """The script advertises /bin/sh; on Debian that is dash, not bash."""
        with open(INSTALL, encoding="utf-8") as fh:
            body = fh.read()
        for pattern, name in [
            (r"\[\[", "[[ ]] test"),
            (r"^\s*declare\s", "declare"),
            (r"^\s*local\s", "local"),
            (r"\$\(\(.*\+\+", "++ arithmetic"),
            (r"\[[^]\n]*\s==\s", "== inside a [ ] test"),
            (r"\bfunction\s+\w+\s*\(", "function keyword"),
        ]:
            self.assertIsNone(
                re.search(pattern, body, re.MULTILINE),
                f"install.sh uses a bashism: {name}")


class Flags(unittest.TestCase):
    def test_help_exits_zero_and_documents_the_options(self):
        proc = run("--help")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for flag in ("--dir", "--ref", "--no-scan", "--uninstall"):
            self.assertIn(flag, proc.stdout)

    def test_help_prints_no_shell_source(self):
        """Regression guard: usage() once used a hardcoded line range.

        When the header grew, `set -eu` and the variable block were printed into
        the user's help output.
        """
        stdout = run("--help").stdout
        for leak in ("set -eu", "REPO=", 'REF="$', "die()", "case \"$1\""):
            self.assertNotIn(leak, stdout,
                             f"help output leaked shell source: {leak!r}")

    def test_unknown_option_fails_loudly(self):
        proc = run("--nonsense")
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("unknown option", proc.stderr)

    def test_option_needing_a_value_rejects_a_bare_flag(self):
        for flag in ("--dir", "--ref"):
            proc = run(flag)
            self.assertNotEqual(proc.returncode, 0, flag)

    def test_uninstall_on_a_clean_directory_is_a_successful_no_op(self):
        with tempfile.TemporaryDirectory() as tmp:
            proc = run("--uninstall", cwd=tmp)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("Nothing installed", proc.stdout)
            self.assertEqual(os.listdir(tmp), [])


class StarterPolicy(unittest.TestCase):
    """The policy the installer writes must be readable by the policy parser.

    These two live in different files and different languages, so nothing but a
    test keeps them in step. A starter policy the scanner cannot parse would
    silently grant more autonomy than the user thinks they granted.
    """

    @classmethod
    def setUpClass(cls):
        with open(INSTALL, encoding="utf-8") as fh:
            body = fh.read()
        match = re.search(r"<<'POLICYEOF'\n(.*?)\nPOLICYEOF", body, re.DOTALL)
        assert match, "could not find the starter policy heredoc in install.sh"
        cls.policy_text = match.group(1)

    def _parse(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "CONFIGROT.md"), "w", encoding="utf-8") as fh:
                fh.write(self.policy_text + "\n")
            return scan.load_policy(tmp)

    def test_parses_into_the_expected_shape(self):
        policy = self._parse()
        self.assertEqual(policy["mode"], "ondemand")
        for key in ("never_touch", "verify", "suppress"):
            self.assertEqual(policy[key], [], f"{key} should parse as an empty list")

    def test_defaults_to_the_least_autonomous_mode(self):
        """A file written without the user reading it must not grant autonomy."""
        self.assertEqual(self._parse()["mode"], "ondemand")

    def test_grants_no_auto_merge_and_suppresses_nothing(self):
        policy = self._parse()
        self.assertEqual(policy.get("auto_merge", []), [])
        self.assertEqual(policy["suppress"], [])

    def test_contains_no_fictional_constraints(self):
        """Regression guard: the installer once shipped the annotated template.

        Its worked examples ("pinned to Node 20 until the Q3 migration") read as
        binding fact to the agent, which would refuse real upgrades for reasons
        that were never true of the user's repo.
        """
        prose = self._parse().get("prose", "")
        for phrase in ("Pinned to Node", "vendor SDK is not\ncertified",
                       "Do not migrate away from Jest", "scheduled for deletion"):
            self.assertNotIn(phrase, prose,
                             "the starter policy must not assert constraints "
                             "the user never made")


if __name__ == "__main__":
    unittest.main(verbosity=2)
