#!/usr/bin/env bash
#
# Build a Skill ZIP for upload to Claude (claude.ai / Claude Desktop / Claude Code).
#
# Output: dist/survey-qa-skill.zip
#
# Bundle contents:
#   SKILL.md            — required, includes the description Claude reads
#   scripts/            — entry point Python scripts
#   survey_qa/          — full source code (copied from src/survey_qa/)
#
# Upload instructions:
#   claude.ai           Settings → Features → Capabilities → upload ZIP
#   Claude Code         Extract into ~/.claude/skills/survey-qa/
#   Claude API          POST /v1/skills (see Anthropic docs)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
BUILD="$DIST/skill-build/survey-qa"
OUT="$DIST/survey-qa-skill.zip"

cd "$ROOT"

# Verify inputs
for f in skills/survey-qa/SKILL.md skills/survey-qa/scripts/parse_xml.py src/survey_qa/__init__.py; do
  if [ ! -f "$f" ]; then
    echo "error: missing $f" >&2
    exit 1
  fi
done

# Clean previous build
rm -rf "$DIST/skill-build" "$OUT"
mkdir -p "$BUILD"

# Copy SKILL.md and scripts/
cp skills/survey-qa/SKILL.md "$BUILD/"
cp -r skills/survey-qa/scripts "$BUILD/"

# Copy survey_qa package source (the bundled library)
cp -r src/survey_qa "$BUILD/"

# Strip caches and any leftover runtime self-install dir.
# The Skill's _bootstrap.py creates vendor/ at first invocation in the
# target sandbox — we don't ship it from the build machine because native
# wheels (lxml, pydantic-core, rapidfuzz) are platform/ABI-specific.
find "$BUILD" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
find "$BUILD" -type d -name vendor -prune -exec rm -rf {} + 2>/dev/null || true
find "$BUILD" -name '*.pyc' -delete 2>/dev/null || true

# Zip the survey-qa directory (Skills expect a single folder at the zip root)
(cd "$DIST/skill-build" && zip -rq "$OUT" survey-qa)

SIZE="$(du -h "$OUT" | cut -f1)"
echo "Built: $OUT ($SIZE)"
echo
echo "To install on claude.ai: Settings → Capabilities → upload this ZIP."
echo "To install in Claude Code: unzip into ~/.claude/skills/"
