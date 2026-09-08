#!/usr/bin/env python3
"""Checks for the Community Goal guide data, API build, and site.

The site is generated from data/, so a broken reference in a JSON file becomes
a dead link on a public page. These tests are the guardrail: they run the real
build into a temporary directory and assert the published contract — every
endpoint exists, every id resolves, the scoring maths is consistent, and the
site actually references the API it documents.

    python3 tests/test_community_goal.py
"""

from __future__ import annotations

import json
import os
import pathlib
import re
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOAL = os.path.join(ROOT, "community-goal")
sys.path.insert(0, GOAL)

import build as builder  # noqa: E402

BASE = "https://example.test/community-goal"


def read(path: str):
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


class SourceDataTests(unittest.TestCase):
    """The data files on their own, before anything is generated."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.guide, cls.sections, cls.evidence = builder.load()

    def test_validation_passes(self) -> None:
        builder.validate(self.guide, self.sections, self.evidence)

    def test_ten_sections_numbered_in_order(self) -> None:
        self.assertEqual([s["number"] for s in self.sections], list(range(1, 11)))
        self.assertEqual([s["id"] for s in self.sections], ["s%d" % n for n in range(1, 11)])

    def test_slugs_are_url_safe_and_unique(self) -> None:
        slugs = [s["slug"] for s in self.sections]
        self.assertEqual(len(set(slugs)), len(slugs))
        for slug in slugs:
            self.assertRegex(slug, r"^[a-z0-9-]+$")

    def test_every_section_carries_a_goal_and_requirements(self) -> None:
        for section in self.sections:
            self.assertTrue(section["goal"].strip(), section["id"])
            self.assertGreaterEqual(len(section["requirements"]), 3, section["id"])

    def test_evidence_items_say_how_to_verify_them(self) -> None:
        # The source guide does not name its citations, so an unverifiable claim
        # must at least tell a community where to go and check it.
        for item in self.evidence:
            self.assertTrue(item["verify"].strip(), item["id"])
            self.assertTrue(item["use"].strip(), item["id"])

    def test_every_evidence_item_is_referenced(self) -> None:
        referenced = {e for s in self.sections for r in s["requirements"]
                      for e in r.get("evidence", [])}
        referenced |= {f["evidence"] for f in self.guide["framing"]["facts"]}
        orphans = {e["id"] for e in self.evidence} - referenced
        self.assertEqual(orphans, set(), "evidence not cited anywhere: %s" % sorted(orphans))

    def test_the_four_pillars_are_intact(self) -> None:
        ids = [p["id"] for p in self.guide["basic_rule"]["pillars"]]
        self.assertEqual(ids, ["limit", "verification", "party", "remedy"])

    def test_broken_reference_fails_validation(self) -> None:
        sections = json.loads(json.dumps(self.sections))
        sections[0]["requirements"][0]["evidence"] = ["ev-does-not-exist"]
        with self.assertRaises(builder.BuildError):
            builder.validate(self.guide, sections, self.evidence)

    def test_misfiled_requirement_id_fails_validation(self) -> None:
        sections = json.loads(json.dumps(self.sections))
        sections[1]["requirements"][0]["id"] = "s9-r99"
        with self.assertRaises(builder.BuildError):
            builder.validate(self.guide, sections, self.evidence)


class BuildTests(unittest.TestCase):
    """The generated API, exactly as GitHub Pages will serve it."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.dist = os.path.join(cls._tmp.name, "dist")
        cls.stats = builder.build(pathlib.Path(cls.dist), BASE)
        cls.api = os.path.join(cls.dist, "api", "v1")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_top_level_endpoints_exist(self) -> None:
        for name in ("index.json", "goal.json", "rule.json", "framing.json",
                     "sections.json", "requirements.json", "evidence.json",
                     "instruments.json", "questions.json", "checklist.json",
                     "scoring.json", "tags.json", "search.json", "guide.json",
                     "openapi.json", "guide.md"):
            self.assertTrue(os.path.isfile(os.path.join(self.api, name)), name)

    def test_every_requirement_and_section_has_its_own_endpoint(self) -> None:
        guide = read(os.path.join(self.api, "guide.json"))
        for req in guide["requirements"]:
            self.assertTrue(
                os.path.isfile(os.path.join(self.api, "requirements", req["id"] + ".json")),
                req["id"])
        for section in guide["sections"]:
            for key in ("id", "slug"):
                self.assertTrue(
                    os.path.isfile(os.path.join(self.api, "sections", section[key] + ".json")),
                    section[key])

    def test_index_counts_match_the_payloads(self) -> None:
        index = read(os.path.join(self.api, "index.json"))
        guide = read(os.path.join(self.api, "guide.json"))
        self.assertEqual(index["counts"]["sections"], len(guide["sections"]))
        self.assertEqual(index["counts"]["requirements"], len(guide["requirements"]))
        self.assertEqual(index["counts"]["evidence"], len(guide["evidence"]))
        self.assertEqual(index["counts"]["commitments"] + index["counts"]["actions"],
                         len(guide["requirements"]))

    def test_index_endpoints_are_absolute_and_on_the_given_base(self) -> None:
        index = read(os.path.join(self.api, "index.json"))
        for url in index["endpoints"]:
            self.assertTrue(url.startswith(BASE + "/api/v1/"), url)

    def test_requirement_endpoint_inlines_its_evidence(self) -> None:
        payload = read(os.path.join(self.api, "requirements", "s9-r2.json"))
        self.assertEqual(payload["requirement"]["id"], "s9-r2")
        self.assertTrue(payload["evidence"], "s9-r2 cites evidence, so it should be inlined")
        self.assertEqual(payload["evidence"][0]["id"],
                         payload["requirement"]["evidence"][0])

    def test_scoring_max_points_matches_the_requirements(self) -> None:
        scoring = read(os.path.join(self.api, "scoring.json"))["scoring"]
        guide = read(os.path.join(self.api, "guide.json"))
        expected = sum(
            r["weight"] * (len(scoring["pillars"]) if r["type"] == "commitment" else 1)
            for r in guide["requirements"])
        self.assertEqual(scoring["max_points"], expected)
        self.assertEqual(scoring["max_points"], self.stats["max_points"])

    def test_scoring_bands_tile_zero_to_one_hundred(self) -> None:
        bands = read(os.path.join(self.api, "scoring.json"))["scoring"]["bands"]
        self.assertEqual(bands[0]["min"], 0)
        self.assertEqual(bands[-1]["max"], 100)
        for lower, upper in zip(bands, bands[1:]):
            self.assertEqual(upper["min"], lower["max"] + 1)

    def test_checklist_template_is_blank_and_complete(self) -> None:
        checklist = read(os.path.join(self.api, "checklist.json"))
        guide = read(os.path.join(self.api, "guide.json"))
        self.assertEqual(len(checklist["items"]), len(guide["requirements"]))
        for item in checklist["items"]:
            self.assertEqual(item["status"], "not-started")
            if item["type"] == "commitment":
                self.assertEqual(set(item["pillars"].values()), {False})
            else:
                self.assertIsNone(item["pillars"])

    def test_openapi_documents_every_shipped_path(self) -> None:
        spec = read(os.path.join(self.api, "openapi.json"))
        self.assertEqual(spec["openapi"], "3.1.0")
        self.assertEqual(spec["servers"][0]["url"], BASE + "/api/v1")
        for path, item in spec["paths"].items():
            self.assertIn("get", item)
            if "{" in path:
                continue
            self.assertTrue(os.path.isfile(os.path.join(self.api, path.lstrip("/"))), path)

    def test_search_index_covers_every_requirement(self) -> None:
        docs = read(os.path.join(self.api, "search.json"))["documents"]
        guide = read(os.path.join(self.api, "guide.json"))
        indexed = {d["id"] for d in docs if d["kind"] == "requirement"}
        self.assertEqual(indexed, {r["id"] for r in guide["requirements"]})

    def test_markdown_rendering_contains_every_section_heading(self) -> None:
        with open(os.path.join(self.api, "guide.md"), encoding="utf-8") as handle:
            text = handle.read()
        for section in read(os.path.join(self.api, "sections.json"))["sections"]:
            self.assertIn(section["title"], text)
        self.assertIn("This is not legal advice", text)

    def test_site_is_copied_and_pages_will_not_run_jekyll(self) -> None:
        self.assertTrue(os.path.isfile(os.path.join(self.dist, "index.html")))
        self.assertTrue(os.path.isfile(os.path.join(self.dist, "assets", "app.js")))
        self.assertTrue(os.path.isfile(os.path.join(self.dist, "assets", "styles.css")))
        self.assertTrue(os.path.isfile(os.path.join(self.dist, ".nojekyll")))

    def test_site_fetches_the_api_it_documents(self) -> None:
        with open(os.path.join(self.dist, "assets", "app.js"), encoding="utf-8") as handle:
            app = handle.read()
        self.assertIn("api/v1", app)
        self.assertIn("guide.json", app)

    def test_rebuild_is_clean(self) -> None:
        # A stale file left behind by an earlier build would still be published.
        stray = os.path.join(self.dist, "api", "v1", "stale.json")
        with open(stray, "w", encoding="utf-8") as handle:
            handle.write("{}")
        builder.build(pathlib.Path(self.dist), BASE)
        self.assertFalse(os.path.exists(stray))


class SiteTests(unittest.TestCase):
    """The source site, checked for the mistakes that only show up in a browser."""

    @classmethod
    def setUpClass(cls) -> None:
        with open(os.path.join(GOAL, "site", "index.html"), encoding="utf-8") as handle:
            cls.html = handle.read()
        with open(os.path.join(GOAL, "site", "assets", "app.js"), encoding="utf-8") as handle:
            cls.app = handle.read()

    def test_html_references_only_bundled_assets(self) -> None:
        for url in re.findall(r'(?:src|href)="([^"]+)"', self.html):
            if url.startswith(("#", "data:", "api/")):
                continue
            self.assertFalse(url.startswith(("http://", "https://", "//")),
                             "site must not load third-party assets: %s" % url)
            self.assertTrue(os.path.isfile(os.path.join(GOAL, "site", url)), url)

    def test_every_element_the_app_addresses_exists_in_the_html(self) -> None:
        ids = set(re.findall(r'id="([^"]+)"', self.html))
        for used in set(re.findall(r"\$\('#([a-z0-9-]+)'\)", self.app)):
            self.assertIn(used, ids, "app.js addresses #%s, which the page never defines" % used)

    def test_storage_access_is_guarded(self) -> None:
        # Blocked storage (private windows, hardened browsers) must not break the page.
        for match in re.finditer(r"localStorage\.", self.app):
            window = self.app[max(0, match.start() - 220):match.end() + 60]
            self.assertIn("try", window,
                          "unguarded localStorage access near: %s" % window.strip()[:80])


if __name__ == "__main__":
    unittest.main(verbosity=2)
