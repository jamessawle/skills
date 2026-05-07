#!/usr/bin/env bash
set -euo pipefail

MARKETPLACE_ROOT="${1:?Usage: validate.sh <path-to-marketplace-root>}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

CLAUDE_MANIFEST="$MARKETPLACE_ROOT/.claude-plugin/marketplace.json"
CODEX_MANIFEST="$MARKETPLACE_ROOT/.agents/plugins/marketplace.json"

if [ ! -f "$CLAUDE_MANIFEST" ] && [ ! -f "$CODEX_MANIFEST" ]; then
  echo "Error: neither $CLAUDE_MANIFEST nor $CODEX_MANIFEST found"
  exit 1
fi

echo "=== Marketplace structure validation ==="
node "$SCRIPT_DIR/validate.mjs" "$MARKETPLACE_ROOT"
