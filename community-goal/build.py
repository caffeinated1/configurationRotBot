#!/usr/bin/env python3
"""Build the Community Goal static API and site.

Reads the three data files in ``data/``, validates their cross-references, and
writes a fully static JSON API plus the interactive site into ``dist/``.

Static because the whole thing has to survive on GitHub Pages: no server, no
database, no runtime. Every endpoint is a file, so a fetch against it works the
same locally, in CI, and in production.

Standard library only, matching the rest of this repository.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SITE = ROOT / "site"
API_VERSION = "v1"

# Overridden by --base-url so generated links work under a project-pages subpath.
DEFAULT_BASE = "https://caffeinated1.github.io/configurationRotBot"


class BuildError(Exception):
    """Raised when the source data is internally inconsistent."""


def load() -> tuple[dict, list, list]:
    guide = json.loads((DATA / "guide.json").read_text(encoding="utf-8"))
    sections = json.loads((DATA / "sections.json").read_text(encoding="utf-8"))
    evidence = json.loads((DATA / "evidence.json").read_text(encoding="utf-8"))
    return guide, sections, evidence


def validate(guide: dict, sections: list, evidence: list) -> None:
    """Fail the build on a broken reference rather than shipping a dead link."""
    errors: list[str] = []

    evidence_ids = {e["id"] for e in evidence}
    instrument_ids = {i["id"] for i in guide["instruments"]}
    section_ids = {s["id"] for s in sections}
    pillar_ids = {p["id"] for p in guide["basic_rule"]["pillars"]}

    if len(evidence_ids) != len(evidence):
        errors.append("duplicate evidence ids")
    if len(section_ids) != len(sections):
        errors.append("duplicate section ids")
    if not pillar_ids:
        errors.append("basic_rule.pillars is empty")

    seen_req: set[str] = set()
    for section in sections:
        for req in section["requirements"]:
            rid = req["id"]
            if rid in seen_req:
                errors.append(f"duplicate requirement id: {rid}")
            seen_req.add(rid)
            if not rid.startswith(section["id"] + "-"):
                errors.append(f"{rid} is not prefixed with its section id {section['id']}")
            if req["type"] not in ("action", "commitment"):
                errors.append(f"{rid} has unknown type {req['type']!r}")
            if req["weight"] not in (1, 2, 3):
                errors.append(f"{rid} has weight {req['weight']} outside 1-3")
            for inst in req.get("instruments", []):
                if inst not in instrument_ids:
                    errors.append(f"{rid} references unknown instrument {inst!r}")
            for ev in req.get("evidence", []):
                if ev not in evidence_ids:
                    errors.append(f"{rid} references unknown evidence {ev!r}")

    for ev in evidence:
        for sid in ev.get("sections", []):
            if sid not in section_ids:
                errors.append(f"{ev['id']} references unknown section {sid!r}")

    for fact in guide["framing"]["facts"]:
        if fact["evidence"] not in evidence_ids:
            errors.append(f"framing fact {fact['id']} references unknown evidence")

    for question in guide["final_questions"]:
        for sid in question["sections"]:
            if sid not in section_ids:
                errors.append(f"{question['id']} references unknown section {sid!r}")

    if errors:
        raise BuildError("data validation failed:\n  - " + "\n  - ".join(errors))


def flatten_requirements(sections: list) -> list[dict]:
    """One flat list, each item carrying enough section context to stand alone."""
    out = []
    for section in sections:
        for order, req in enumerate(section["requirements"], start=1):
            item = dict(req)
            item["section_id"] = section["id"]
            item["section_number"] = section["number"]
            item["section_title"] = section["title"]
            item["section_slug"] = section["slug"]
            item["order"] = order
            item.setdefault("instruments", [])
            item.setdefault("evidence", [])
            item.setdefault("tags", [])
            out.append(item)
    return out


def scoring_model(guide: dict, requirements: list[dict]) -> dict:
    """How the readiness score is computed, published so the number is auditable.

    A ``commitment`` is scored against the four pillars of the basic rule; an
    ``action`` is done or not. Weight is the requirement's own importance.
    """
    pillars = [p["id"] for p in guide["basic_rule"]["pillars"]]
    max_points = sum(
        r["weight"] * (len(pillars) if r["type"] == "commitment" else 1)
        for r in requirements
    )
    return {
        "method": "weighted-pillar",
        "description": (
            "Each commitment is assessed against the four pillars of the basic rule "
            "(stated limit, way to check it, responsible party with money behind it, "
            "practical response when broken). Each action is assessed as done or not "
            "done. Points earned are multiplied by the requirement's weight."
        ),
        "pillars": pillars,
        "weights": {"critical": 3, "important": 2, "supporting": 1},
        "points_per_requirement": {
            "commitment": "weight x pillars satisfied (0-4)",
            "action": "weight x (1 if done else 0)",
        },
        "max_points": max_points,
        "bands": [
            {"id": "not-ready", "label": "Not ready to vote", "min": 0, "max": 39,
             "meaning": "Core protections are unwritten. A vote now spends leverage the town cannot get back."},
            {"id": "gaps", "label": "Material gaps remain", "min": 40, "max": 69,
             "meaning": "The shape of the deal exists but key promises lack limits, verification, or funding."},
            {"id": "close", "label": "Close, with named gaps", "min": 70, "max": 89,
             "meaning": "Most protections are enforceable. Resolve the remaining items before the final vote."},
            {"id": "defensible", "label": "Defensible", "min": 90, "max": 100,
             "meaning": "The town can answer all six questions in plain language and back each answer with a document."},
        ],
    }


def build_search_index(guide: dict, sections: list, evidence: list, requirements: list) -> list[dict]:
    docs = []
    for section in sections:
        docs.append({
            "id": section["id"],
            "kind": "section",
            "title": f"{section['number']}. {section['title']}",
            "body": " ".join([section["summary"], section["goal"]]),
            "href": f"#{section['slug']}",
        })
    for req in requirements:
        docs.append({
            "id": req["id"],
            "kind": "requirement",
            "title": req["title"],
            "body": " ".join(filter(None, [
                req["detail"], req.get("note", ""), req.get("pitfall", ""),
                " ".join(req["tags"]),
            ])),
            "section": req["section_id"],
            "href": f"#{req['id']}",
        })
    for ev in evidence:
        docs.append({
            "id": ev["id"],
            "kind": "evidence",
            "title": ev["headline"],
            "body": " ".join([ev["statement"], ev["use"], ev["verify"]]),
            "href": f"#evidence",
        })
    for pillar in guide["basic_rule"]["pillars"]:
        docs.append({
            "id": pillar["id"],
            "kind": "pillar",
            "title": pillar["name"],
            "body": " ".join([pillar["question"], pillar["failure_mode"]]),
            "href": "#basic-rule",
        })
    return docs


def openapi_spec(base_url: str, guide: dict, sections: list, requirements: list) -> dict:
    """A hand-built OpenAPI 3.1 document describing the static endpoints.

    Every path is GET-only and maps to a file on disk; the spec exists so the
    API is discoverable and testable with ordinary tooling.
    """
    def ok(description: str) -> dict:
        return {"200": {"description": description,
                        "content": {"application/json": {"schema": {"type": "object"}}}}}

    section_enum = [s["id"] for s in sections] + [s["slug"] for s in sections]

    return {
        "openapi": "3.1.0",
        "info": {
            "title": "Community Goal API — " + guide["meta"]["title"],
            "version": guide["meta"]["version"],
            "description": (
                "A read-only JSON API over a civic requirements guide, so a community "
                "can see its goal, the requirements that carry it, and the evidence "
                "behind each one. Every endpoint is a static file; there is no server "
                "and no rate limit.\n\n"
                + guide["meta"]["disclaimer"]
            ),
            "license": {"name": "CC BY 4.0", "url": "https://creativecommons.org/licenses/by/4.0/"},
        },
        "servers": [{"url": f"{base_url}/api/{API_VERSION}"}],
        "paths": {
            "/index.json": {"get": {"summary": "API root: goal, counts, and endpoint list",
                                    "operationId": "getIndex", "responses": ok("API metadata")}},
            "/goal.json": {"get": {"summary": "The community goal this guide serves",
                                   "operationId": "getGoal", "responses": ok("Goal statement")}},
            "/rule.json": {"get": {"summary": "The basic rule and its four pillars",
                                   "operationId": "getRule", "responses": ok("Basic rule")}},
            "/framing.json": {"get": {"summary": "The two facts that frame the decision",
                                      "operationId": "getFraming", "responses": ok("Framing facts")}},
            "/instruments.json": {"get": {"summary": "The six documents that can carry a protection",
                                          "operationId": "listInstruments", "responses": ok("Instruments")}},
            "/sections.json": {"get": {"summary": "All ten sections with their requirements",
                                       "operationId": "listSections", "responses": ok("Sections")}},
            "/sections/{sectionId}.json": {"get": {
                "summary": "One section by id (s1-s10) or slug",
                "operationId": "getSection",
                "parameters": [{"name": "sectionId", "in": "path", "required": True,
                                "schema": {"type": "string", "enum": section_enum}}],
                "responses": ok("Section")}},
            "/requirements.json": {"get": {
                "summary": f"All {len(requirements)} requirements, flattened",
                "operationId": "listRequirements", "responses": ok("Requirements")}},
            "/requirements/{requirementId}.json": {"get": {
                "summary": "One requirement by id (for example s9-r2)",
                "operationId": "getRequirement",
                "parameters": [{"name": "requirementId", "in": "path", "required": True,
                                "schema": {"type": "string", "pattern": "^s([1-9]|10)-r[0-9]+$"}}],
                "responses": ok("Requirement")}},
            "/evidence.json": {"get": {"summary": "Every claim in the guide, with how to verify it locally",
                                       "operationId": "listEvidence", "responses": ok("Evidence")}},
            "/evidence/{evidenceId}.json": {"get": {
                "summary": "One evidence item",
                "operationId": "getEvidence",
                "parameters": [{"name": "evidenceId", "in": "path", "required": True,
                                "schema": {"type": "string"}}],
                "responses": ok("Evidence item")}},
            "/tags.json": {"get": {"summary": "Tag facets with requirement counts",
                                   "operationId": "listTags", "responses": ok("Tags")}},
            "/questions.json": {"get": {"summary": "The six questions to answer before the final vote",
                                        "operationId": "listQuestions", "responses": ok("Questions")}},
            "/checklist.json": {"get": {"summary": "Blank assessment template with the scoring model",
                                        "operationId": "getChecklist", "responses": ok("Checklist template")}},
            "/scoring.json": {"get": {"summary": "How the readiness score is calculated",
                                      "operationId": "getScoring", "responses": ok("Scoring model")}},
            "/search.json": {"get": {"summary": "Client-side search index over the whole guide",
                                     "operationId": "getSearchIndex", "responses": ok("Search index")}},
            "/guide.json": {"get": {"summary": "The entire guide as one document",
                                    "operationId": "getGuide", "responses": ok("Full guide")}},
        },
    }


def render_markdown(guide: dict, sections: list, evidence: list) -> str:
    """A plain-text rendering, so the guide survives outside a browser."""
    out: list[str] = [f"# {guide['meta']['title']}", "", guide["meta"]["subtitle"], ""]
    out += ["## The goal", "", guide["goal"]["statement"], "", guide["goal"]["rule"], ""]
    out += [f"## {guide['framing']['heading']}", ""]
    for fact in guide["framing"]["facts"]:
        out += [f"- **{fact['claim']}** {fact['detail']}"]
    out += ["", guide["framing"]["conclusion"], ""]
    out += ["## The basic rule", "", guide["basic_rule"]["statement"], ""]
    for pillar in guide["basic_rule"]["pillars"]:
        out += [f"- **{pillar['name']}** — {pillar['question']}"]
    out += [""]
    for section in sections:
        out += [f"## {section['number']}. {section['title']}", "", section["summary"], "",
                f"**Goal:** {section['goal']}", ""]
        for req in section["requirements"]:
            out += [f"### {req['id']} — {req['title']}", "", req["detail"], ""]
            if req.get("pitfall"):
                out += [f"> {req['pitfall']}", ""]
            if req.get("note"):
                out += [f"_{req['note']}_", ""]
    out += ["## Before the final vote", ""]
    for question in guide["final_questions"]:
        out += [f"- {question['question']}"]
    out += ["", guide["goal"]["rule"], "", "---", "", guide["meta"]["disclaimer"], ""]
    out += ["## Evidence", ""]
    for ev in evidence:
        out += [f"### {ev['headline']}", "", ev["statement"], "",
                f"**Verify locally:** {ev['verify']}", ""]
    return "\n".join(out)


def write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build(dist: Path, base_url: str) -> dict:
    guide, sections, evidence = load()
    validate(guide, sections, evidence)

    requirements = flatten_requirements(sections)
    scoring = scoring_model(guide, requirements)
    built_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    if dist.exists():
        shutil.rmtree(dist)
    dist.mkdir(parents=True)
    api = dist / "api" / API_VERSION

    tags: dict[str, int] = {}
    for req in requirements:
        for tag in req["tags"]:
            tags[tag] = tags.get(tag, 0) + 1

    meta = dict(guide["meta"])
    meta["built_at"] = built_at
    meta["api_version"] = API_VERSION

    endpoints = [
        "index.json", "goal.json", "rule.json", "framing.json", "instruments.json",
        "sections.json", "sections/{id}.json", "requirements.json",
        "requirements/{id}.json", "evidence.json", "evidence/{id}.json", "tags.json",
        "questions.json", "checklist.json", "scoring.json", "search.json",
        "guide.json", "guide.md", "openapi.json",
    ]

    write_json(api / "index.json", {
        "meta": meta,
        "goal": guide["goal"],
        "counts": {
            "sections": len(sections),
            "requirements": len(requirements),
            "commitments": sum(1 for r in requirements if r["type"] == "commitment"),
            "actions": sum(1 for r in requirements if r["type"] == "action"),
            "evidence": len(evidence),
            "instruments": len(guide["instruments"]),
        },
        "endpoints": [f"{base_url}/api/{API_VERSION}/{e}" for e in endpoints],
        "openapi": f"{base_url}/api/{API_VERSION}/openapi.json",
        "site": base_url + "/",
    })

    write_json(api / "goal.json", {"meta": meta, "goal": guide["goal"],
                                   "final_questions": guide["final_questions"]})
    write_json(api / "rule.json", {"meta": meta, "basic_rule": guide["basic_rule"]})
    write_json(api / "framing.json", {"meta": meta, "framing": guide["framing"]})
    write_json(api / "instruments.json", {"meta": meta, "instruments": guide["instruments"]})
    write_json(api / "questions.json", {"meta": meta, "final_questions": guide["final_questions"]})
    write_json(api / "sections.json", {"meta": meta, "count": len(sections), "sections": sections})
    write_json(api / "requirements.json",
               {"meta": meta, "count": len(requirements), "requirements": requirements})
    write_json(api / "evidence.json", {"meta": meta, "count": len(evidence), "evidence": evidence})
    write_json(api / "tags.json", {"meta": meta,
                                   "tags": [{"tag": t, "count": c} for t, c in sorted(tags.items())]})
    write_json(api / "scoring.json", {"meta": meta, "scoring": scoring})
    write_json(api / "search.json",
               {"meta": meta, "documents": build_search_index(guide, sections, evidence, requirements)})

    for section in sections:
        payload = {"meta": meta, "section": section}
        write_json(api / "sections" / f"{section['id']}.json", payload)
        write_json(api / "sections" / f"{section['slug']}.json", payload)

    by_id = {r["id"]: r for r in requirements}
    ev_by_id = {e["id"]: e for e in evidence}
    for req in requirements:
        write_json(api / "requirements" / f"{req['id']}.json", {
            "meta": meta,
            "requirement": req,
            "evidence": [ev_by_id[e] for e in req["evidence"]],
        })
    for ev in evidence:
        write_json(api / "evidence" / f"{ev['id']}.json", {"meta": meta, "evidence": ev})

    write_json(api / "checklist.json", {
        "meta": meta,
        "scoring": scoring,
        "instructions": (
            "Copy this template, set each item's status, and post the result. A blank "
            "field is a gap, not a neutral value."
        ),
        "items": [{
            "id": r["id"],
            "section": r["section_id"],
            "title": r["title"],
            "type": r["type"],
            "weight": r["weight"],
            "status": "not-started",
            "pillars": ({p: False for p in scoring["pillars"]} if r["type"] == "commitment" else None),
            "owner": None,
            "document": None,
            "notes": "",
        } for r in requirements],
    })

    write_json(api / "guide.json", {
        "meta": meta,
        "goal": guide["goal"],
        "framing": guide["framing"],
        "basic_rule": guide["basic_rule"],
        "instruments": guide["instruments"],
        "sections": sections,
        "requirements": requirements,
        "evidence": evidence,
        "final_questions": guide["final_questions"],
        "scoring": scoring,
    })
    write_json(api / "openapi.json", openapi_spec(base_url, guide, sections, requirements))
    (api / "guide.md").write_text(render_markdown(guide, sections, evidence), encoding="utf-8")

    for item in SITE.iterdir():
        target = dist / item.name
        shutil.copytree(item, target) if item.is_dir() else shutil.copy2(item, target)

    # Pages would otherwise run Jekyll over the output and drop files it dislikes.
    (dist / ".nojekyll").write_text("", encoding="utf-8")

    assert by_id  # referenced for clarity that ids are unique post-validation
    return {"requirements": len(requirements), "sections": len(sections),
            "evidence": len(evidence), "max_points": scoring["max_points"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dist", default=str(ROOT / "dist"), help="output directory")
    parser.add_argument("--base-url", default=DEFAULT_BASE,
                        help="public base URL used in generated links")
    parser.add_argument("--check", action="store_true",
                        help="validate the data and exit without writing anything")
    args = parser.parse_args(argv)

    try:
        if args.check:
            guide, sections, evidence = load()
            validate(guide, sections, evidence)
            print("data ok: %d sections, %d requirements, %d evidence items" % (
                len(sections), sum(len(s["requirements"]) for s in sections), len(evidence)))
            return 0
        stats = build(Path(args.dist), args.base_url.rstrip("/"))
    except BuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print("built {sections} sections, {requirements} requirements, {evidence} evidence items "
          "(max score {max_points} points) -> {dist}".format(dist=args.dist, **stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
