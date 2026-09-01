#!/usr/bin/env python3
"""Schema checks for the bundled datasets.

data/rules.json is the primary contribution surface, so it needs a guardrail
that catches the mistakes a first-time contributor actually makes: a duplicate
or renamed id, an invalid regex, a severity that does not exist, a missing
recommendation. Those are cheap to check and expensive to discover in
production.

    python3 tests/test_rules.py
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "skills", "config-rot", "scripts"))

import common  # noqa: E402

DATA = os.path.join(ROOT, "skills", "config-rot", "data")


def entries(mapping: dict) -> dict:
    """Datasets use a leading underscore for metadata keys."""
    return {k: v for k, v in mapping.items() if not k.startswith("_")}


def load(name: str):
    with open(os.path.join(DATA, name), encoding="utf-8") as fh:
        return json.load(fh)


VALID_EFFORT = {"trivial", "small", "medium", "large", "epic"}
VALID_AUTOFIX = {"safe", "assisted", "manual"}
VALID_CONFIDENCE = {"high", "medium", "low"}

KNOWN_CONDITIONS = {
    "ecosystem", "has_any_ecosystem", "dependency", "dependency_absent",
    "dependency_any", "count_gte", "file_exists", "file_exists_all",
    "file_absent", "file_absent_glob", "file_contains", "not_file_contains",
    "lockfile_count_gte", "any",
}


class Rules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = load("rules.json")["rules"]

    def test_ids_are_unique(self):
        ids = [r["id"] for r in self.rules]
        dupes = {i for i in ids if ids.count(i) > 1}
        self.assertFalse(dupes, f"duplicate rule ids: {dupes}")

    def test_ids_are_namespaced_by_category(self):
        for r in self.rules:
            self.assertTrue(r["id"].startswith(r["category"] + "."),
                            f"{r['id']} should start with {r['category']}.")

    def test_enumerated_fields_are_valid(self):
        for r in self.rules:
            self.assertIn(r["category"], common.CATEGORIES, r["id"])
            self.assertIn(r["severity"], common.SEVERITIES, r["id"])
            self.assertIn(r.get("effort", "small"), VALID_EFFORT, r["id"])
            self.assertIn(r.get("autofix", "assisted"), VALID_AUTOFIX, r["id"])
            self.assertIn(r.get("confidence", "high"), VALID_CONFIDENCE, r["id"])

    def test_every_rule_states_a_problem_and_a_fix(self):
        for r in self.rules:
            self.assertTrue(r.get("title"), f"{r['id']} has no title")
            self.assertTrue(r.get("recommendation"),
                            f"{r['id']} has no recommendation — a finding "
                            "without a fix is just criticism")

    def test_conditions_use_known_keys(self):
        def check(when, rid):
            for key in when:
                self.assertIn(key, KNOWN_CONDITIONS, f"{rid}: unknown condition `{key}`")
            for sub in when.get("any", []):
                check(sub, rid)
        for r in self.rules:
            self.assertTrue(r.get("when"), f"{r['id']} has no conditions")
            check(r["when"], r["id"])

    def test_patterns_compile(self):
        def check(when, rid):
            for spec in when.get("file_contains", []) + when.get("not_file_contains", []):
                for key in ("glob", "pattern"):
                    try:
                        re.compile(spec[key])
                    except re.error as exc:
                        self.fail(f"{rid}: invalid {key} regex — {exc}")
            for pattern in when.get("file_absent_glob", []):
                try:
                    re.compile(pattern)
                except re.error as exc:
                    self.fail(f"{rid}: invalid file_absent_glob regex — {exc}")
            for sub in when.get("any", []):
                check(sub, rid)
        for r in self.rules:
            check(r["when"], r["id"])

    def test_dependency_any_declares_a_threshold(self):
        for r in self.rules:
            if "dependency_any" in r["when"]:
                self.assertIn("count_gte", r["when"],
                              f"{r['id']}: dependency_any needs count_gte")

    def test_references_are_https(self):
        for r in self.rules:
            for ref in r.get("references", []):
                self.assertTrue(ref.startswith("https://"), f"{r['id']}: {ref}")

    def test_manual_rules_are_never_marked_safe(self):
        """`safe` means mechanically verifiable. A judgment call never is."""
        for r in self.rules:
            if r.get("effort") in ("large", "epic"):
                self.assertNotEqual(r.get("autofix"), "safe",
                                    f"{r['id']}: a {r['effort']} change cannot be `safe`")


class Abandoned(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = entries(load("abandoned.json")["packages"])
        cls.covered = {pkg for r in load("rules.json")["rules"]
                       for pkg in r.get("covers", [])}

    def test_statuses_are_known(self):
        for eco, packages in self.data.items():
            for name, entry in packages.items():
                self.assertIn(entry["status"],
                              {"deprecated", "archived", "dormant", "active"},
                              f"{eco}/{name}")

    def test_non_active_entries_name_a_replacement(self):
        for eco, packages in self.data.items():
            for name, entry in packages.items():
                if entry["status"] != "active":
                    self.assertTrue(entry.get("replacement"),
                                    f"{eco}/{name} is {entry['status']} with no replacement")

    def test_no_overlap_with_rules_that_claim_the_package(self):
        """A rule with `covers` gives better advice; the catalogue must defer.

        Overlap is not a crash, but it produces two findings for one dependency,
        which is the fastest way to make a report feel like noise.
        """
        overlap = {name for packages in self.data.values() for name in packages
                   if name in self.covered
                   and packages[name]["status"] != "active"}
        self.assertFalse(
            overlap,
            f"these packages have a dedicated rule and should be removed from "
            f"abandoned.json (or the rule's `covers` dropped): {sorted(overlap)}")


class Eol(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load("eol.json")

    def test_dates_are_iso_and_parseable(self):
        for runtime, cycle in entries(self.data["cycles"]).items():
            for key, val in cycle.get("eol", {}).items():
                try:
                    _dt.date.fromisoformat(val)
                except ValueError:
                    self.fail(f"{runtime} {key}: {val!r} is not an ISO date")

    def test_every_cycle_links_upstream(self):
        for runtime, cycle in entries(self.data["cycles"]).items():
            self.assertTrue(cycle.get("url", "").startswith("https://"), runtime)

    def test_each_runtime_has_a_supported_release(self):
        """If every cycle is EOL, the recommendation would be to upgrade to nothing."""
        today = _dt.date.today()
        for runtime, cycle in entries(self.data["cycles"]).items():
            live = [k for k, v in cycle.get("eol", {}).items()
                    if _dt.date.fromisoformat(v) > today]
            self.assertTrue(live, f"{runtime} has no supported release in the dataset — "
                                  "run scripts/refresh_data.py")

    def test_action_minimums_are_positive_integers(self):
        for action, info in entries(self.data["github_actions"]).items():
            self.assertIsInstance(info["min_major"], int, action)
            self.assertGreater(info["min_major"], 0, action)
            self.assertTrue(info.get("reason"), f"{action} has no reason")

    def test_runner_entries_name_a_replacement(self):
        for label, info in entries(self.data["github_runners"]).items():
            self.assertIn(info["status"], {"removed", "deprecated"}, label)
            self.assertTrue(info.get("replacement"), label)


if __name__ == "__main__":
    unittest.main(verbosity=2)
