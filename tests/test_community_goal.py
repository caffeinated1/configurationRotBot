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
        cls.guide, cls.sections, cls.evidence, cls.jurisdictions = builder.load()

    def test_validation_passes(self) -> None:
        builder.validate(self.guide, self.sections, self.evidence, self.jurisdictions)

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

    def test_evidence_sources_are_checkable_when_present(self) -> None:
        for item in self.evidence:
            for src in item.get("sources", []):
                for field in ("title", "publisher", "url"):
                    self.assertTrue(str(src.get(field, "")).strip(),
                                    "%s source missing %s" % (item["id"], field))
                self.assertTrue(src["url"].startswith("https://"), item["id"])

    def test_a_bare_link_is_not_accepted_as_a_source(self) -> None:
        evidence = json.loads(json.dumps(self.evidence))
        evidence[0]["sources"] = [{"url": "https://example.test/report.pdf"}]
        with self.assertRaises(builder.BuildError):
            builder.validate(self.guide, self.sections, evidence, self.jurisdictions)

    def test_overlays_annotate_requirements_that_exist(self) -> None:
        ids = {r["id"] for s in self.sections for r in s["requirements"]}
        for jur in self.jurisdictions:
            self.assertTrue(jur["notes"], "%s annotates nothing" % jur["id"])
            for rid in jur["notes"]:
                self.assertIn(rid, ids, "%s annotates unknown %s" % (jur["id"], rid))

    def test_every_overlay_names_a_maintainer(self) -> None:
        # An overlay nobody maintains goes stale silently, and stale law is
        # worse than no law.
        for jur in self.jurisdictions:
            self.assertTrue(jur.get("maintainers"), jur["id"])

    def test_overlay_annotating_a_missing_requirement_fails(self) -> None:
        jurisdictions = json.loads(json.dumps(self.jurisdictions))
        jurisdictions[0]["notes"]["s4-r404"] = {"note": "nope"}
        with self.assertRaises(builder.BuildError):
            builder.validate(self.guide, self.sections, self.evidence, jurisdictions)

    def test_unmaintained_overlay_fails(self) -> None:
        jurisdictions = json.loads(json.dumps(self.jurisdictions))
        jurisdictions[0]["maintainers"] = []
        with self.assertRaises(builder.BuildError):
            builder.validate(self.guide, self.sections, self.evidence, jurisdictions)

    def test_the_four_pillars_are_intact(self) -> None:
        ids = [p["id"] for p in self.guide["basic_rule"]["pillars"]]
        self.assertEqual(ids, ["limit", "verification", "party", "remedy"])

    def test_broken_reference_fails_validation(self) -> None:
        sections = json.loads(json.dumps(self.sections))
        sections[0]["requirements"][0]["evidence"] = ["ev-does-not-exist"]
        with self.assertRaises(builder.BuildError):
            builder.validate(self.guide, sections, self.evidence, self.jurisdictions)

    def test_misfiled_requirement_id_fails_validation(self) -> None:
        sections = json.loads(json.dumps(self.sections))
        sections[1]["requirements"][0]["id"] = "s9-r99"
        with self.assertRaises(builder.BuildError):
            builder.validate(self.guide, sections, self.evidence, self.jurisdictions)


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

    def test_jurisdiction_endpoints_exist_and_agree_with_the_index(self) -> None:
        index = read(os.path.join(self.api, "jurisdictions.json"))
        self.assertEqual(index["count"], len(index["jurisdictions"]))
        for entry in index["jurisdictions"]:
            path = os.path.join(self.api, "jurisdictions", entry["id"] + ".json")
            self.assertTrue(os.path.isfile(path), entry["id"])
            overlay = read(path)["jurisdiction"]
            self.assertEqual(sorted(overlay["notes"]), entry["annotates"])

    def test_coverage_is_published_and_accurate(self) -> None:
        coverage = read(os.path.join(self.api, "coverage.json"))["citation_coverage"]
        evidence = read(os.path.join(self.api, "evidence.json"))["evidence"]
        cited = [e for e in evidence if e.get("sources")]
        self.assertEqual(coverage["claims"], len(evidence))
        self.assertEqual(coverage["cited"], len(cited))
        self.assertEqual(coverage["uncited"], len(evidence) - len(cited))
        self.assertEqual(sorted(coverage["uncited_ids"]),
                         sorted(e["id"] for e in evidence if not e.get("sources")))

    def test_markdown_flags_uncited_claims_instead_of_hiding_them(self) -> None:
        with open(os.path.join(self.api, "guide.md"), encoding="utf-8") as handle:
            text = handle.read()
        evidence = read(os.path.join(self.api, "evidence.json"))["evidence"]
        if any(not e.get("sources") for e in evidence):
            self.assertIn("No primary source recorded yet", text)

    def test_rebuild_is_clean(self) -> None:
        # A stale file left behind by an earlier build would still be published.
        stray = os.path.join(self.dist, "api", "v1", "stale.json")
        with open(stray, "w", encoding="utf-8") as handle:
            handle.write("{}")
        builder.build(pathlib.Path(self.dist), BASE)
        self.assertFalse(os.path.exists(stray))


class ExtractionTests(unittest.TestCase):
    """The guide is meant to move to its own repository; keep that move working.

    extract.py rewrites paths and URLs that assume a subdirectory. Renaming a
    document here, or moving one, silently breaks it — so the extraction runs
    for real and the result has to build and test on its own.
    """

    @classmethod
    def setUpClass(cls) -> None:
        sys.path.insert(0, GOAL)
        import extract  # noqa: E402

        cls.extract = extract
        cls._tmp = tempfile.TemporaryDirectory()
        cls.dest = pathlib.Path(cls._tmp.name) / "standalone"
        extract.extract(cls.dest, "exampleorg/example-guide", force=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_the_extracted_tree_stands_on_its_own(self) -> None:
        # Builds, tests, and carries no reference to the repository it left.
        self.extract.verify(self.dest)

    def test_content_and_docs_arrive_at_the_root(self) -> None:
        for name in ("build.py", "serve.py", "README.md", "CONTRIBUTING.md",
                     "GOVERNANCE.md", "ROADMAP.md", "CODE_OF_CONDUCT.md",
                     "SECURITY.md", "CITATION.cff", "LICENSE", "LICENSE-CONTENT.md",
                     ".gitignore", "data/guide.json", "data/sections.json",
                     "data/evidence.json", "schema/guide.schema.json",
                     "site/index.html", "tests/test_guide.py",
                     ".github/workflows/ci.yml", ".github/workflows/pages.yml",
                     ".github/PULL_REQUEST_TEMPLATE.md"):
            self.assertTrue((self.dest / name).exists(), name)

    def test_issue_forms_lose_their_prefix_and_stay_linked(self) -> None:
        guide = json.loads((self.dest / "data" / "guide.json").read_text(encoding="utf-8"))
        for kind, url in guide["meta"]["project"]["forms"].items():
            name = url.rsplit("template=", 1)[-1]
            self.assertFalse(name.startswith("cg-"), name)
            self.assertTrue((self.dest / ".github" / "ISSUE_TEMPLATE" / name).exists(),
                            "%s form points at missing %s" % (kind, name))

    def test_urls_point_at_the_new_repository(self) -> None:
        guide = json.loads((self.dest / "data" / "guide.json").read_text(encoding="utf-8"))
        project = guide["meta"]["project"]
        self.assertEqual(project["repository"], "https://github.com/exampleorg/example-guide")
        self.assertNotIn("directory", project)
        for url in list(project["forms"].values()) + [project["contributing"],
                                                      project["governance"], project["roadmap"]]:
            self.assertIn("exampleorg/example-guide", url)
            self.assertNotIn("/community-goal/", url)

    def test_workflows_build_from_the_root(self) -> None:
        pages = (self.dest / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
        self.assertIn("python3 build.py --dist dist", pages)
        self.assertIn("path: dist", pages)
        self.assertNotIn("community-goal/", pages)
        # Pull requests must still build without deploying.
        self.assertIn("pull_request:", pages)
        self.assertIn("if: github.event_name != 'pull_request'", pages)

    def test_it_refuses_to_clobber_an_existing_directory(self) -> None:
        with self.assertRaises(SystemExit):
            self.extract.extract(self.dest, "exampleorg/example-guide", force=False)


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

    def test_issue_forms_the_site_links_to_actually_exist(self) -> None:
        # The site deep-links prefilled issue forms by filename. A renamed form
        # would send a contributor to a 404 with no error anywhere in the build.
        guide = read(os.path.join(GOAL, "data", "guide.json"))
        forms = guide["meta"]["project"]["forms"]
        self.assertTrue(forms, "no contribution forms declared")
        for kind, url in forms.items():
            name = url.rsplit("template=", 1)[-1]
            path = os.path.join(ROOT, ".github", "ISSUE_TEMPLATE", name)
            self.assertTrue(os.path.isfile(path),
                            "%s form points at missing %s" % (kind, name))

    def test_roadmap_lists_every_claim_that_still_needs_a_source(self) -> None:
        # The roadmap is the "what can I pick up" page. A claim that is uncited
        # but missing from it is work nobody can find.
        with open(os.path.join(GOAL, "ROADMAP.md"), encoding="utf-8") as handle:
            roadmap = handle.read()
        evidence = read(os.path.join(GOAL, "data", "evidence.json"))
        for item in evidence:
            if not item.get("sources"):
                self.assertIn(item["id"], roadmap,
                              "%s has no source and no roadmap entry" % item["id"])

    def test_contribution_docs_exist_where_the_site_says_they_do(self) -> None:
        for name in ("CONTRIBUTING.md", "GOVERNANCE.md", "README.md", "ROADMAP.md"):
            self.assertTrue(os.path.isfile(os.path.join(GOAL, name)), name)
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "CODE_OF_CONDUCT.md")))
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "CITATION.cff")))

    def test_external_links_open_safely(self) -> None:
        # Contributed overlays and sources render as links; every one that opens
        # a new tab needs rel=noopener.
        for match in re.finditer(r"target=\\?['\"]_blank", self.app):
            window = self.app[max(0, match.start() - 200):match.end() + 120]
            self.assertIn("noopener", window,
                          "target=_blank without rel=noopener near: %s" % window[-120:])

    def test_storage_access_is_guarded(self) -> None:
        # Blocked storage (private windows, hardened browsers) must not break the page.
        for match in re.finditer(r"localStorage\.", self.app):
            window = self.app[max(0, match.start() - 220):match.end() + 60]
            self.assertIn("try", window,
                          "unguarded localStorage access near: %s" % window.strip()[:80])


if __name__ == "__main__":
    unittest.main(verbosity=2)
