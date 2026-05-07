#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="${1:?Usage: validate.sh <path-to-skill-directory>}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_MD="$SKILL_DIR/SKILL.md"

if [ ! -f "$SKILL_MD" ]; then
  echo "Error: $SKILL_MD not found"
  exit 1
fi

echo "=== Markdown formatting ==="
npx markdownlint-cli2 --config "$SCRIPT_DIR/../assets/.markdownlint-cli2.jsonc" "$SKILL_MD" 2>&1 || true
echo ""

echo "=== Frontmatter validation ==="
node "$SCRIPT_DIR/validate-skill.mjs" "$SKILL_MD"
