#!/bin/sh
# configurationRotBot installer
#
#   curl -fsSL https://raw.githubusercontent.com/caffeinated1/configurationRotBot/main/install.sh | sh
#
# Installs the config-rot skill into .claude/skills/, writes a starter
# CONFIGROT.md if you don't have one, and runs a first scan.
#
# This script is piped into a shell, so it is written to be read before it is
# trusted: no sudo, no writes outside the target directory, no network calls
# beyond fetching this project's own release tarball from GitHub.
#
# Options:
#   --dir PATH      install into PATH (default: ./.claude/skills)
#   --ref REF       install a specific tag, branch or commit (default: main)
#   --no-scan       install without running the first scan
#   --no-policy     do not write a starter CONFIGROT.md
#   --uninstall     remove a previous install and exit
#   -h, --help      show this and exit

set -eu

REPO="caffeinated1/configurationRotBot"
# Defaults to main until release tags are cut; pass --ref v1.0.0 (or set
# CONFIGROT_REF) to pin an install to a specific release.
REF="${CONFIGROT_REF:-main}"
DIR=""
RUN_SCAN=1
WRITE_POLICY=1
UNINSTALL=0

# Colour only when stdout is a terminal; piped output should stay plain.
if [ -t 1 ]; then
    B="$(printf '\033[1m')"; DIM="$(printf '\033[2m')"; R="$(printf '\033[0m')"
else
    B=""; DIM=""; R=""
fi

say()  { printf '%s\n' "$*"; }
step() { printf '%s==>%s %s\n' "$B" "$R" "$*"; }
warn() { printf '%s!%s  %s\n' "$B" "$R" "$*" >&2; }
die()  { printf '%serror:%s %s\n' "$B" "$R" "$*" >&2; exit 1; }

# Print the header comment block, stopping at the first line that is not a
# comment. A hardcoded line range drifts the moment the header changes, and the
# drift shows up as shell source printed into the user's help output.
usage() {
    awk 'NR > 1 { if ($0 !~ /^#/) exit; sub(/^# ?/, ""); print }' "$0"
    exit 0
}

while [ $# -gt 0 ]; do
    case "$1" in
        --dir)        DIR="${2:-}"; [ -n "$DIR" ] || die "--dir needs a path"; shift 2 ;;
        --ref)        REF="${2:-}"; [ -n "$REF" ] || die "--ref needs a value"; shift 2 ;;
        --no-scan)    RUN_SCAN=0; shift ;;
        --no-policy)  WRITE_POLICY=0; shift ;;
        --uninstall)  UNINSTALL=1; shift ;;
        -h|--help)    usage ;;
        *)            die "unknown option: $1 (try --help)" ;;
    esac
done

[ -n "$DIR" ] || DIR="$(pwd)/.claude/skills"
SKILL_DIR="$DIR/config-rot"

if [ "$UNINSTALL" -eq 1 ]; then
    if [ -d "$SKILL_DIR" ]; then
        rm -rf "$SKILL_DIR"
        say "Removed $SKILL_DIR"
        say "${DIM}CONFIGROT.md and .configrot/ were left alone — delete them yourself if you want them gone.${R}"
    else
        say "Nothing installed at $SKILL_DIR"
    fi
    exit 0
fi

# ---------------------------------------------------------------- prerequisites

PYTHON=""
for candidate in python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        if "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
            PYTHON="$candidate"
            break
        fi
    fi
done
[ -n "$PYTHON" ] || die "Python 3.9 or newer is required and was not found on PATH.
       The scanner has no other dependencies — a system Python is enough."

if command -v curl >/dev/null 2>&1; then
    FETCH="curl -fsSL"
elif command -v wget >/dev/null 2>&1; then
    FETCH="wget -qO-"
else
    die "neither curl nor wget is available"
fi

command -v tar >/dev/null 2>&1 || die "tar is required"

# ---------------------------------------------------------------- download

TMP="$(mktemp -d)"
# shellcheck disable=SC2064  # $TMP must expand now, not at trap time
trap "rm -rf '$TMP'" EXIT INT TERM

step "Fetching $REPO@$REF"
if ! $FETCH "https://codeload.github.com/$REPO/tar.gz/$REF" > "$TMP/src.tar.gz" 2>/dev/null; then
    die "could not download $REPO@$REF.
       Check the ref exists, or pass --ref main to install from the default branch."
fi

tar -xzf "$TMP/src.tar.gz" -C "$TMP" || die "the download was not a valid archive"

# The tarball extracts to <repo>-<ref>/, so the skill sits three levels down.
SRC="$(find "$TMP" -maxdepth 4 -type d -name config-rot -path '*/skills/*' | head -n 1)"
[ -n "$SRC" ] || die "the archive did not contain skills/config-rot — is --ref '$REF' correct?"

# ---------------------------------------------------------------- install

UPDATE=0
[ -d "$SKILL_DIR" ] && UPDATE=1

mkdir -p "$DIR"
# Replace rather than merge, so a removed file in a new version actually goes.
rm -rf "$SKILL_DIR"
cp -R "$SRC" "$SKILL_DIR"
chmod +x "$SKILL_DIR"/scripts/*.py 2>/dev/null || true

if [ "$UPDATE" -eq 1 ]; then
    step "Updated the config-rot skill in $DIR"
else
    step "Installed the config-rot skill into $DIR"
fi

# ---------------------------------------------------------------- policy

POLICY="$(pwd)/CONFIGROT.md"
if [ "$WRITE_POLICY" -eq 1 ] && [ ! -f "$POLICY" ]; then
    # Deliberately NOT a copy of assets/CONFIGROT.template.md. That file is
    # annotated with worked examples ("pinned to Node 20 until the Q3
    # migration"), and the agent reads this file as binding fact — a starter
    # policy full of fictional constraints would make it refuse real upgrades
    # for reasons that were never true. Start empty and honest instead.
    cat > "$POLICY" <<'POLICYEOF'
---
# How much autonomy this repo grants: off | ondemand | scheduled | keeper
mode: ondemand

# Paths the agent must never edit.
never_touch: []

# The commands that define "working" here. The agent runs these before and
# after every change and reverts anything that turns them red, so filling this
# in is what makes the safety guarantee real. Inferred from CI if left empty.
verify: []

# Finding ids to ignore. Re-affirm periodically — a permanent suppression is
# just rot with paperwork.
suppress: []
---

## Constraints

Write real constraints here as prose, and give each one its reason and, where
it applies, an expiry date. The reason matters as much as the rule: an agent
can weigh a constraint it understands, and can tell you when the reason has
stopped being true.

Leave this section empty until you have something true to put in it. Anything
written here is read as binding fact, so an example left in by accident will
block real work.

<!-- The fully annotated version, with worked examples, is at
     .claude/skills/config-rot/assets/CONFIGROT.template.md -->
POLICYEOF
    step "Wrote a starter CONFIGROT.md"
    say "${DIM}   It is intentionally empty. Fill in \`verify\` before granting any${R}"
    say "${DIM}   autonomy — that is what lets the agent check its own work.${R}"
elif [ -f "$POLICY" ]; then
    say "${DIM}   Kept your existing CONFIGROT.md.${R}"
fi

# ---------------------------------------------------------------- first scan

if [ "$RUN_SCAN" -eq 1 ]; then
    step "Scanning $(pwd)"
    say ""
    # The scanner exits with the worst severity it found, which is not a failure
    # of the install — don't let `set -e` treat it as one.
    "$PYTHON" "$SKILL_DIR/scripts/scan.py" --repo . --format summary --no-state || true
    say ""
fi

# ---------------------------------------------------------------- next steps

say "${B}Next:${R}"
say "  Full report      $PYTHON .claude/skills/config-rot/scripts/scan.py --repo ."
say "  With registries  $PYTHON .claude/skills/config-rot/scripts/scan.py --repo . --online"
say "  With Claude Code ask it: \"check this repo for configuration rot\""
say ""
say "${DIM}The scanner is read-only and never writes to the repo it scans.${R}"
say "${DIM}Docs: https://github.com/$REPO${R}"
