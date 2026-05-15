#!/usr/bin/env bash
#
# Build a .mcpb bundle for distribution to Claude Desktop users.
#
# Output: dist/survey-qa.mcpb
#
# Bundle contents:
#   - manifest.json
#   - pyproject.toml
#   - src/survey_qa/
#   - README.md
#   - LICENSE  (if present)
#
# Users install by dragging the .mcpb into Claude Desktop.
# uv (bundled with Claude Desktop runtime) handles Python deps automatically.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DIST="$ROOT/dist"
BUILD="$DIST/build"
OUT="$DIST/survey-qa.mcpb"

cd "$ROOT"

# Verify required files
for f in manifest.json pyproject.toml src/survey_qa/mcp/server.py; do
  if [ ! -f "$f" ]; then
    echo "error: missing $f" >&2
    exit 1
  fi
done

# Clean previous build
rm -rf "$BUILD" "$OUT"
mkdir -p "$BUILD"

# Stage files
cp manifest.json "$BUILD/"
cp pyproject.toml "$BUILD/"
cp -r src "$BUILD/"
[ -f README.md ] && cp README.md "$BUILD/" || true
[ -f LICENSE ] && cp LICENSE "$BUILD/" || true

# Strip pycache and any local caches if they snuck in
find "$BUILD" -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
find "$BUILD" -name '*.pyc' -delete 2>/dev/null || true

# Pack as zip with .mcpb extension
(cd "$BUILD" && zip -rq "$OUT" .)

# Report
SIZE="$(du -h "$OUT" | cut -f1)"
echo "Built: $OUT ($SIZE)"
echo
echo "To distribute: send the .mcpb file to your team."
echo "They install by dragging it into Claude Desktop."
