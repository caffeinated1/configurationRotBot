#!/usr/bin/env python3
"""Tests for the configuration-rot scanner. Standard library only.

    python3 tests/test_scan.py
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "config-rot", "scripts")
sys.path.insert(0, SCRIPTS)

import common  # noqa: E402
import scan  # noqa: E402
from detectors import inventory  # noqa: E402

FIXTURE = os.path.join(ROOT, "examples", "rotten-repo")


def write(root: str, rel: str, content: str) -> None:
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)


def run_scan(root: str, *extra: str) -> dict:
    """Run the scanner and return the payload, without touching the repo."""
    with tempfile.TemporaryDirectory() as out:
        target = os.path.join(out, "findings.json")
        scan.main(["--repo", root, "--json", target, "--format", "summary",
                   "--no-state", "--exit-zero", *extra])
        with open(target, encoding="utf-8") as fh:
            return json.load(fh)


class VersionHelpers(unittest.TestCase):
    def test_vtuple_handles_real_world_specs(self):
        for spec, expected in [
            ("18.2.0", (18, 2, 0)), ("^18.2", (18, 2, 0)), ("v20.11.1", (20, 11, 1)),
            (">=3.9", (3, 9, 0)), ("3.11-slim", (3, 11, 0)), ("22", (22, 0, 0)),
        ]:
            self.assertEqual(common.vtuple(spec), expected, spec)

    def test_vtuple_returns_none_for_unparseable(self):
        for spec in (None, "", "latest", "*"):
            self.assertIsNone(common.vtuple(spec))

    def test_is_pinned_distinguishes_ranges(self):
        self.assertTrue(common.is_pinned("18.2.0"))
        self.assertTrue(common.is_pinned("3.11"))
        for spec in ("^18.2.0", "~1.2", ">=14", "1.x", "1 - 2"):
            self.assertFalse(common.is_pinned(spec), spec)

    def test_toml_fallback_parses_pyproject_shapes(self):
        parsed = common._fallback_toml(
            '[project]\nname = "x"\nrequires-python = ">=3.11"\n'
            'dependencies = ["a>=1", "b"]\n\n[tool.ruff]\ntarget-version = "py311"\n')
        self.assertEqual(parsed["project"]["requires-python"], ">=3.11")
        self.assertEqual(parsed["project"]["dependencies"], ["a>=1", "b"])
        self.assertEqual(parsed["tool"]["ruff"]["target-version"], "py311")


class Inventory(unittest.TestCase):
    def test_collects_every_node_version_declaration(self):
        inv = inventory.build(FIXTURE)
        sources = {d.source for d in inv.versions if d.runtime == "node"}
        self.assertEqual(sources, {"engines", "nvmrc", "ci-matrix", "dockerfile"})

    def test_evidence_carries_line_numbers(self):
        inv = inventory.build(FIXTURE)
        for decl in inv.versions:
            self.assertIsNotNone(decl.line, f"{decl.file} {decl.source} has no line")

    def test_skips_vendored_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "package.json", '{"name":"x"}')
            write(tmp, "node_modules/dep/package.json", '{"name":"dep"}')
            inv = inventory.build(tmp)
            self.assertNotIn("node_modules/dep/package.json", inv.files)


class Detectors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.payload = run_scan(FIXTURE)
        cls.ids = {f["id"] for f in cls.payload["findings"]}

    def test_every_category_is_exercised_by_the_fixture(self):
        found = {f["category"] for f in self.payload["findings"]}
        self.assertEqual(found, set(common.CATEGORIES) - {"DRIFT"},
                         "fixture should exercise every offline category")

    def test_finds_eol_runtime_and_removed_runner(self):
        self.assertIn("DECAY.node-eol.dockerfile", self.ids)
        self.assertIn("DECAY.gh-runner.ubuntu-20.04", self.ids)
        self.assertIn("DECAY.gh-set-output", self.ids)

    def test_finds_version_divergence(self):
        self.assertIn("DIVERGENCE.node-version", self.ids)
        f = next(x for x in self.payload["findings"] if x["id"] == "DIVERGENCE.node-version")
        files = {e["file"] for e in f["evidence"]}
        self.assertGreaterEqual(len(files), 3, "divergence must cite every conflicting file")

    def test_finds_eslint_flat_config_stagnation(self):
        self.assertIn("STAGNATION.eslint-flat-config", self.ids)

    def test_every_finding_has_evidence_and_a_recommendation(self):
        for f in self.payload["findings"]:
            self.assertTrue(f["evidence"], f"{f['id']} has no evidence")
            self.assertTrue(f["recommendation"], f"{f['id']} has no recommendation")
            for e in f["evidence"]:
                self.assertTrue(e.get("file"), f"{f['id']} evidence lacks a file")

    def test_no_duplicate_finding_ids(self):
        ids = [f["id"] for f in self.payload["findings"]]
        self.assertEqual(len(ids), len(set(ids)), "finding ids must be unique per run")

    def test_a_rule_claiming_a_package_suppresses_the_catalogue_entry(self):
        # `request` has a dedicated rule; the flat catalogue must defer to it.
        self.assertIn("HAZARD.request-abandoned", self.ids)
        self.assertNotIn("HAZARD.abandoned.request", self.ids)

    def test_offline_scan_reports_what_it_skipped(self):
        skipped = {s["detector"] for s in self.payload["skipped"]}
        self.assertIn("drift", skipped)
        self.assertIn("audit", skipped)

    def test_findings_are_severity_sorted(self):
        ranks = [common.SEVERITY_RANK[f["severity"]] for f in self.payload["findings"]]
        self.assertEqual(ranks, sorted(ranks, reverse=True))


class HealthyRepo(unittest.TestCase):
    """A current repo should be quiet. False positives are what get a tool muted."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = self.tmp.name
        write(root, "package.json", json.dumps({
            "name": "healthy", "version": "1.0.0", "packageManager": "npm@10.8.0",
            "engines": {"node": ">=22"},
            "scripts": {"test": "node --test"},
            "dependencies": {"express": "^5.0.0"},
        }))
        write(root, "package-lock.json", '{"lockfileVersion": 3}')
        write(root, "src/index.js", "import express from 'express';\nexpress();\n")
        write(root, ".github/workflows/ci.yml",
              "name: CI\non: [push]\njobs:\n  t:\n    runs-on: ubuntu-latest\n"
              "    strategy:\n      matrix:\n        node-version: [22]\n"
              "    steps:\n      - uses: actions/checkout@v4\n"
              "      - uses: actions/setup-node@v4\n      - run: npm ci\n")
        write(root, ".github/dependabot.yml",
              'version: 2\nupdates:\n  - package-ecosystem: "npm"\n')
        write(root, ".nvmrc", "22\n")
        self.payload = run_scan(root)

    def tearDown(self):
        self.tmp.cleanup()

    def test_no_high_or_critical_findings(self):
        loud = [f["id"] for f in self.payload["findings"]
                if f["severity"] in ("high", "critical")]
        self.assertEqual(loud, [], f"false positives on a healthy repo: {loud}")

    def test_rot_index_is_low(self):
        self.assertLessEqual(self.payload["rot_index"]["overall"], 10,
                             "a current repo should score near zero")


class Policy(unittest.TestCase):
    def test_frontmatter_parses_scalars_and_lists(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "CONFIGROT.md",
                  "---\nmode: keeper\nmax_open_prs: 3\nauto_merge: [safe]\n"
                  "never_touch:\n  - \"vendor/**\"\n  - charts/\n---\n\n## Constraints\nStay on Node 20.\n")
            policy = scan.load_policy(tmp)
        self.assertEqual(policy["mode"], "keeper")
        self.assertEqual(policy["max_open_prs"], 3)
        self.assertEqual(policy["auto_merge"], ["safe"])
        self.assertEqual(policy["never_touch"], ["vendor/**", "charts/"])
        self.assertIn("Stay on Node 20", policy["prose"])

    def test_never_touch_suppresses_rather_than_drops(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "package.json", '{"name":"x","dependencies":{"request":"^2.88.0"}}')
            write(tmp, "CONFIGROT.md", '---\nnever_touch: ["package.json"]\n---\n')
            payload = run_scan(tmp)
        ids = {f["id"] for f in payload["findings"]}
        suppressed = {f["id"] for f in payload["suppressed"]}
        self.assertNotIn("HAZARD.request-abandoned", ids)
        self.assertIn("HAZARD.request-abandoned", suppressed)
        self.assertTrue(all(f.get("suppressed_by_policy") for f in payload["suppressed"]))

    def test_suppress_by_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "package.json", '{"name":"x","dependencies":{"request":"^2.88.0"}}')
            write(tmp, "CONFIGROT.md", '---\nsuppress: ["HAZARD.request-abandoned"]\n---\n')
            payload = run_scan(tmp)
        self.assertNotIn("HAZARD.request-abandoned", {f["id"] for f in payload["findings"]})


class Scoring(unittest.TestCase):
    def _f(self, category: str, severity: str):
        return common.Finding(id=f"{category}.x", category=category,
                              severity=severity, title="t")

    def test_clean_repo_scores_zero(self):
        self.assertEqual(scan.rot_index([])["overall"], 0)

    def test_index_is_capped_and_ordered(self):
        low = scan.rot_index([self._f("CRUFT", "low")])["overall"]
        high = scan.rot_index([self._f("HAZARD", "critical")])["overall"]
        self.assertLess(low, high)
        self.assertLessEqual(high, 100)

    def test_hazard_outweighs_cruft_at_equal_severity(self):
        hazard = scan.rot_index([self._f("HAZARD", "high")] * 3)
        cruft = scan.rot_index([self._f("CRUFT", "high")] * 3)
        self.assertGreater(hazard["overall"], cruft["overall"])


class Safety(unittest.TestCase):
    def test_scanner_does_not_write_to_the_repo(self):
        """The scanner is safe to run on untrusted code because it is read-only."""
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "package.json", '{"name":"x","dependencies":{"request":"^2.0.0"}}')
            before = {p: os.path.getmtime(os.path.join(tmp, p))
                      for p in os.listdir(tmp)}
            run_scan(tmp)
            after = {p: os.path.getmtime(os.path.join(tmp, p))
                     for p in os.listdir(tmp)}
            self.assertEqual(before, after, "scan.py must not modify the repository")

    def test_online_mode_also_writes_nothing_to_the_repo(self):
        """The registry cache belongs in a user cache dir, not the scanned repo.

        Regression guard: the cache was originally written to
        `<repo>/.configrot/`, which silently broke the read-only guarantee for
        anyone passing --online.
        """
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "package.json",
                  '{"name":"x","dependencies":{"left-pad":"^1.0.0"}}')
            before = sorted(os.listdir(tmp))
            # No network is needed to prove this: the cache write happens on the
            # same path whether or not the lookups succeed.
            run_scan(tmp, "--online", "--detectors", "drift")
            self.assertEqual(before, sorted(os.listdir(tmp)),
                             "--online must not create files in the scanned repo")

    def test_survives_a_malformed_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "package.json", "{ this is not json")
            payload = run_scan(tmp)
            self.assertIsInstance(payload["findings"], list)
            self.assertTrue(payload["notes"], "a broken manifest should be noted")

    def test_empty_directory_produces_a_valid_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = run_scan(tmp)
        self.assertEqual(payload["schema_version"], common.SCHEMA_VERSION)
        self.assertEqual(payload["rot_index"]["overall"], 0)


class ExitCodes(unittest.TestCase):
    def test_exit_code_encodes_worst_severity(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = scan.main(["--repo", tmp, "--format", "summary", "--no-state"])
        self.assertEqual(code, 0)
        code = scan.main(["--repo", FIXTURE, "--format", "summary", "--no-state"])
        self.assertEqual(code, common.SEVERITY_RANK["critical"])

    def test_exit_zero_overrides(self):
        code = scan.main(["--repo", FIXTURE, "--format", "summary",
                          "--no-state", "--exit-zero"])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
