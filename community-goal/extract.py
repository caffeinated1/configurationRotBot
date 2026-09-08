#!/usr/bin/env python3
"""Extract Community Goal into its own repository.

The guide is built here but is meant to live somewhere a town planner or an NGO
can find it without navigating a developer tool. This performs that move
deterministically: it copies the content, lifts it to the repository root,
rewrites every path and URL that assumed a subdirectory, and leaves a tree that
builds and tests standalone.

    python3 community-goal/extract.py --dest /tmp/community-goal
    python3 community-goal/extract.py --dest /tmp/community-goal --repo you/your-repo --git

Then, in the new empty GitHub repository:

    cd /tmp/community-goal
    git remote add origin git@github.com:you/your-repo.git
    git push -u origin main

Re-runnable: pass --dest a directory that does not exist, or --force to replace
one. Standard library only, like everything else here.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent

SOURCE_REPO = "caffeinated1/configurationRotBot"
DEFAULT_TARGET_REPO = "caffeinated1/community-goal"

# Copied from community-goal/ to the new repository root.
FROM_GUIDE = ["data", "schema", "site", "build.py", "serve.py",
              "README.md", "CONTRIBUTING.md", "GOVERNANCE.md", "ROADMAP.md"]

# Shared with the scanner here; the guide takes its own copy.
FROM_REPO_ROOT = ["CODE_OF_CONDUCT.md", "SECURITY.md", "CITATION.cff"]

# Only meaningful once standalone. See community-goal/standalone/README.md.
FROM_STANDALONE = {"LICENSE": "LICENSE", "LICENSE-CONTENT.md": "LICENSE-CONTENT.md",
                   "ci.yml": ".github/workflows/ci.yml"}

ISSUE_FORMS = ["source", "jurisdiction", "requirement", "correction"]

TEXT_SUFFIXES = {".md", ".yml", ".yaml", ".json", ".py", ".js", ".html", ".cff", ".txt"}


def rewrite_text(text: str, target_repo: str) -> str:
    """Move every reference from 'a subdirectory of the scanner' to 'the repository'."""
    owner, name = target_repo.split("/", 1)
    replacements = [
        (f"https://github.com/{SOURCE_REPO}", f"https://github.com/{target_repo}"),
        ("https://caffeinated1.github.io/configurationRotBot", f"https://{owner}.github.io/{name}"),
        (f"github.com/{SOURCE_REPO}", f"github.com/{target_repo}"),
        # documents move up to the root
        ("/blob/main/community-goal/", "/blob/main/"),
        ("community-goal/CONTRIBUTING.md", "CONTRIBUTING.md"),
        ("community-goal/GOVERNANCE.md", "GOVERNANCE.md"),
        ("community-goal/ROADMAP.md", "ROADMAP.md"),
        ("(../CITATION.cff)", "(CITATION.cff)"),
        ("(../CODE_OF_CONDUCT.md)", "(CODE_OF_CONDUCT.md)"),
        # issue forms no longer need a prefix to avoid colliding with the scanner's
        ("template=cg-", "template="),
        # commands lose the directory
        ("python3 community-goal/build.py", "python3 build.py"),
        ("python3 community-goal/serve.py", "python3 serve.py"),
        ("python3 tests/test_community_goal.py", "python3 tests/test_guide.py"),
        ("community-goal/data/jurisdictions/template.json", "data/jurisdictions/template.json"),
        ("community-goal/data/", "data/"),
        ("community-goal/dist", "dist"),
        ("git clone https://github.com/%s\ncd configurationRotBot" % target_repo,
         "git clone https://github.com/%s\ncd %s" % (target_repo, name)),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


README_HEADER_OLD = """# Community Goal — a town's first data center

An interactive guide and open JSON API built from
*"A town's first data center: what to require before saying yes."*
"""


def readme_header(target_repo: str) -> str:
    owner, name = target_repo.split("/", 1)
    site = f"https://{owner}.github.io/{name}/"
    return f"""# Community Goal

**A town's first data center: what to require before saying yes.**

An open, structured requirements guide for communities facing a first data center
proposal — published as a readable interactive site and a static JSON API that
anyone can build on.

[**Read the guide →**]({site}) ·
[API]({site}api/v1/index.json) ·
[What needs doing](ROADMAP.md) ·
[How to contribute](CONTRIBUTING.md) ·
[Governance](GOVERNANCE.md)

Ten sections · 71 requirements · 18 checkable claims · CC BY 4.0
"""


def fix_readme(text: str, target_repo: str) -> str:
    owner, name = target_repo.split("/", 1)
    site = f"https://{owner}.github.io/{name}/"
    text = text.replace(
        README_HEADER_OLD + f"\n**Site:** {site}\n**API root:** {site}api/v1/index.json\n",
        readme_header(target_repo))
    text = text.replace("## What ships\n\n| Path | What it is |",
                        "## What's in here\n\n| Path | What it is |")
    text = text.replace(
        "| `GOVERNANCE.md` | Who decides, how disputed claims are handled, the disclosure rule |",
        "| `GOVERNANCE.md` | Who decides, how disputed claims are handled, the disclosure rule |\n"
        "| `LICENSE-CONTENT.md` | CC BY 4.0 for the content; MIT for the code |")
    text = text.replace(
        "Standard library only, like the rest of this repository. `build.py` fails on a\n"
        "dangling evidence id, a requirement filed under the wrong section, or an unknown\n"
        "instrument",
        "Standard library only — no dependencies, no package manager, no build tools. A\n"
        "civic tool that needs `npm install` to rebuild is one that stops being rebuilt.\n"
        "`build.py` fails on a dangling evidence id, a requirement filed under the wrong\n"
        "section, or an unknown instrument")
    text = text.replace(
        "Content: **CC BY 4.0**. Code: **MIT**, with the rest of this repository.\n"
        "Contributions are accepted under the same terms; there is no CLA. Cite as\n"
        "described in [CITATION.cff](CITATION.cff).",
        "Content: **CC BY 4.0** ([LICENSE-CONTENT.md](LICENSE-CONTENT.md)).\n"
        "Code: **MIT** ([LICENSE](LICENSE)).\n"
        "Contributions are accepted under the same terms; there is no CLA. Cite as\n"
        "described in [CITATION.cff](CITATION.cff).\n\n---\n\n"
        f"Originally built in\n[{SOURCE_REPO}](https://github.com/{SOURCE_REPO})\n"
        "and extracted so the people this is for — town and county staff, planning\n"
        "boards, agencies, NGOs, clinics, engineers, and counsel — can find it without\n"
        "navigating a developer tool.")
    return text


def fix_contributing(text: str) -> str:
    """Realign the quickstart block: the rewritten commands are shorter."""
    return text.replace(
        "python3 build.py --check   # validate the data, write nothing\n"
        "python3 build.py           # generate dist/\n"
        "python3 serve.py           # build and open http://localhost:8000\n"
        "python3 tests/test_guide.py      # the full check suite",
        "python3 build.py --check    # validate the data, write nothing\n"
        "python3 build.py            # generate dist/\n"
        "python3 serve.py            # build and open http://localhost:8000\n"
        "python3 tests/test_guide.py # the full check suite")


def fix_tests(text: str) -> str:
    # ExtractionTests is about this script, which does not travel with the guide.
    # Leaving it behind would make the new repository's suite fail on an import
    # of a file it has no reason to contain.
    text = re.sub(r"class ExtractionTests\(unittest\.TestCase\):.*?(?=^class )",
                  "", text, flags=re.DOTALL | re.MULTILINE)
    text = text.replace(
        'ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n'
        'GOAL = os.path.join(ROOT, "community-goal")\n'
        'sys.path.insert(0, GOAL)',
        'ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))\n'
        'GOAL = ROOT  # the guide is the repository\n'
        'sys.path.insert(0, ROOT)')
    return text.replace('"""Checks for the Community Goal guide data, API build, and site.',
                        '"""Checks for the guide data, the generated API, and the site.')


def fix_pages_workflow(text: str) -> str:
    """Drop the path filters (everything here is the guide) and lift the paths."""
    text = re.sub(r"    paths:\n(?:      - \"[^\"]+\"\n)+", "", text)
    text = text.replace("  pull_request:\n\n", "  pull_request:\n")
    text = text.replace("name: Community Goal site", "name: Build and publish")
    text = text.replace(
        "# Builds the Community Goal guide (static JSON API + interactive site) and\n"
        "# publishes it to GitHub Pages. Pull requests build without deploying, so a\n"
        "# broken reference in the data fails review rather than production.",
        "# Builds the guide (static JSON API + interactive site) and publishes it to\n"
        "# GitHub Pages. Pull requests build without deploying, so a broken reference in\n"
        "# a contributed data file fails review rather than production.")
    text = text.replace("        run: python3 tests/test_community_goal.py",
                        "        run: python3 tests/test_guide.py")
    # The generic rewrite has already run, so match the lifted form.
    text = re.sub(
        r" *python3 build\.py \\\n"
        r" *--dist dist \\\n"
        r" *--base-url \"\$\{\{ steps\.pages\.outputs\.base_url \}\}\"",
        '          python3 build.py --dist dist '
        '--base-url "${{ steps.pages.outputs.base_url }}"', text)
    return text.replace("          path: community-goal/dist", "          path: dist")


def fix_issue_config(text: str, target_repo: str) -> str:
    text = re.sub(
        r"  - name: configurationRotBot — report a false positive or a rule\n"
        r"    url: [^\n]+\n    about: [^\n]+\n",
        f"  - name: What needs doing\n"
        f"    url: https://github.com/{target_repo}/blob/main/ROADMAP.md\n"
        f"    about: Specific claimable work, starting with the claims that still need a "
        f"primary source.\n", text)
    for prefix in ("Community Goal — read the guide", "Community Goal — how to contribute",
                   "Community Goal — governance and conflict of interest"):
        text = text.replace(prefix, prefix.split("— ", 1)[1].capitalize())
    return text


def fix_security(text: str) -> str:
    scanner = text.find("**configurationRotBot** — the scanner")
    if scanner == -1:
        return text
    end = text.find("## What is not")
    text = text[:scanner] + (
        "The published site is static and stores assessment data only in the reader's own\n"
        "browser. In scope:\n\n"
        "- Anything that causes contributed content — an overlay note, an evidence\n"
        "  headline, a source title — to execute as script in a reader's browser. All\n"
        "  content is escaped on render; a bypass is a real finding.\n"
        "- Anything that would send a reader's assessment off their machine. It is meant\n"
        "  to stay in `localStorage` and go nowhere.\n"
        "- Anything in `build.py` that would execute contributed data rather than\n"
        "  validate it.\n\n") + text[end:]
    return text.replace(
        "- Findings that require a user to run the tool against a repository while\n"
        "  deliberately misconfiguring it.\n"
        "- Content disputes in the guide — those are corrections, not vulnerabilities.\n"
        "  See [CONTRIBUTING.md](CONTRIBUTING.md).",
        "- Content disputes — a wrong figure or a legal statement that does not hold is a\n"
        "  correction, not a vulnerability. See [CONTRIBUTING.md](CONTRIBUTING.md).")


def extract(dest: Path, target_repo: str, force: bool) -> None:
    if dest.exists():
        if not force:
            raise SystemExit(f"error: {dest} exists (pass --force to replace it)")
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    (dest / ".github" / "workflows").mkdir(parents=True)
    (dest / ".github" / "ISSUE_TEMPLATE").mkdir(parents=True)
    (dest / "tests").mkdir()

    for name in FROM_GUIDE:
        src = HERE / name
        target = dest / name
        if src.is_dir():
            shutil.copytree(src, target, ignore=shutil.ignore_patterns("__pycache__", "dist"))
        else:
            shutil.copy2(src, target)
    for name in FROM_REPO_ROOT:
        shutil.copy2(REPO_ROOT / name, dest / name)
    for src_name, target_name in FROM_STANDALONE.items():
        shutil.copy2(HERE / "standalone" / src_name, dest / target_name)

    shutil.copy2(REPO_ROOT / "tests" / "test_community_goal.py", dest / "tests" / "test_guide.py")
    shutil.copy2(REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md",
                 dest / ".github" / "PULL_REQUEST_TEMPLATE.md")
    shutil.copy2(REPO_ROOT / ".github" / "workflows" / "pages.yml",
                 dest / ".github" / "workflows" / "pages.yml")
    forms = REPO_ROOT / ".github" / "ISSUE_TEMPLATE"
    for form in ISSUE_FORMS:
        shutil.copy2(forms / f"cg-{form}.yml", dest / ".github" / "ISSUE_TEMPLATE" / f"{form}.yml")
    shutil.copy2(forms / "config.yml", dest / ".github" / "ISSUE_TEMPLATE" / "config.yml")

    # Every text file gets the generic rewrite; a few need targeted surgery.
    for path in sorted(dest.rglob("*")):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        text = rewrite_text(path.read_text(encoding="utf-8"), target_repo)
        rel = path.relative_to(dest).as_posix()
        if rel == "README.md":
            text = fix_readme(text, target_repo)
        elif rel == "tests/test_guide.py":
            text = fix_tests(text)
        elif rel == ".github/workflows/pages.yml":
            text = fix_pages_workflow(text)
        elif rel == ".github/ISSUE_TEMPLATE/config.yml":
            text = fix_issue_config(text, target_repo)
        elif rel == "SECURITY.md":
            text = fix_security(text)
        elif rel == "CONTRIBUTING.md":
            text = fix_contributing(text)
        path.write_text(text, encoding="utf-8")

    (dest / ".gitignore").write_text(
        "# Build output, published by .github/workflows/pages.yml\n"
        "dist/\n"
        "\n"
        "__pycache__/\n"
        "*.py[cod]\n"
        ".DS_Store\n", encoding="utf-8")

    # meta.project.directory described a subdirectory that no longer exists.
    guide_path = dest / "data" / "guide.json"
    guide = json.loads(guide_path.read_text(encoding="utf-8"))
    guide["meta"]["project"].pop("directory", None)
    guide_path.write_text(json.dumps(guide, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def verify(dest: Path) -> None:
    """Prove the extracted tree stands on its own before anyone pushes it."""
    for args in (["build.py", "--check"], ["tests/test_guide.py"],
                 ["build.py", "--dist", str(dest / "dist")]):
        result = subprocess.run([sys.executable, *args], cwd=dest,
                                capture_output=True, text=True)
        if result.returncode != 0:
            raise SystemExit(f"error: {' '.join(args)} failed in the extracted tree\n"
                             f"{result.stdout}\n{result.stderr}")
    shutil.rmtree(dest / "dist", ignore_errors=True)
    for cache in dest.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)

    stale = []
    for path in dest.rglob("*"):
        if path.is_file() and path.suffix in TEXT_SUFFIXES:
            text = path.read_text(encoding="utf-8")
            for line in text.splitlines():
                if "configurationRotBot" in line and "Originally built in" not in line \
                        and "github.com/caffeinated1/configurationRotBot" not in line:
                    stale.append(f"{path.relative_to(dest)}: {line.strip()[:70]}")
    if stale:
        raise SystemExit("error: references to the old home survived:\n  "
                         + "\n  ".join(stale))


def git_init(dest: Path, target_repo: str) -> None:
    def run(*args):
        subprocess.run(["git", *args], cwd=dest, check=True, capture_output=True)
    run("init", "-b", "main")
    run("add", "-A")
    subprocess.run(
        ["git", "commit", "-m",
         "Community Goal: an open guide and API for a town's first data center\n\n"
         "Ten sections, 71 requirements, and 18 claims covering independent review, site\n"
         "suitability, instrument selection, water, noise, on-site generation, ratepayer\n"
         "and budget exposure, public return, financial security, and phased approval\n"
         "with funded closure. Published as an interactive site and a static JSON API.\n\n"
         f"Extracted from https://github.com/{SOURCE_REPO} so the people this is for can\n"
         "find it without navigating a developer tool."],
        cwd=dest, check=True, capture_output=True)
    owner, name = target_repo.split("/", 1)
    print(f"""
Initialised a git repository with one commit.

Next, create an empty {name} repository on GitHub (no README, no licence, no
.gitignore), then:

    cd {dest}
    git remote add origin git@github.com:{target_repo}.git
    git push -u origin main

Then enable Pages: Settings → Pages → Source: GitHub Actions. The site will be
at https://{owner}.github.io/{name}/""")


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dest", required=True, help="directory to create")
    parser.add_argument("--repo", default=DEFAULT_TARGET_REPO,
                        help=f"owner/name of the new repository (default {DEFAULT_TARGET_REPO})")
    parser.add_argument("--force", action="store_true", help="replace --dest if it exists")
    parser.add_argument("--git", action="store_true",
                        help="initialise a git repository with one commit")
    parser.add_argument("--no-verify", action="store_true",
                        help="skip building and testing the extracted tree")
    args = parser.parse_args(argv)

    if "/" not in args.repo:
        raise SystemExit("error: --repo must be owner/name")

    dest = Path(args.dest).resolve()
    extract(dest, args.repo, args.force)
    if not args.no_verify:
        verify(dest)
    print(f"extracted to {dest} ({sum(1 for p in dest.rglob('*') if p.is_file())} files, "
          f"builds and tests clean)")
    if args.git:
        git_init(dest, args.repo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
