#!/usr/bin/env bash
# -e is deliberately omitted — directory mode must continue past per-file failures
set -uo pipefail

ROLE_PATH="${1:?Usage: validate.sh <path-to-role-file-or-agents-directory>}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -d "$ROLE_PATH" ]; then
  # Directory mode: validate all .md files in the directory
  AGENTS_DIR="$ROLE_PATH"
  files=("$AGENTS_DIR"/*.md)

  if [ ${#files[@]} -eq 0 ] || [ ! -f "${files[0]}" ]; then
    echo "Error: No .md files found in $AGENTS_DIR"
    exit 1
  fi

  total_failed=0

  for role_file in "${files[@]}"; do
    echo "=== Validating $(basename "$role_file") ==="
    node "$SCRIPT_DIR/validate-role.mjs" "$role_file" || total_failed=$((total_failed + 1))
    echo ""
  done

  echo "=== Summary: ${#files[@]} role(s) validated, $total_failed with failures ==="
  exit $((total_failed > 0 ? 1 : 0))
else
  # Single file mode
  if [ ! -f "$ROLE_PATH" ]; then
    echo "Error: $ROLE_PATH not found"
    exit 1
  fi

  echo "=== Validating $(basename "$ROLE_PATH") ==="
  node "$SCRIPT_DIR/validate-role.mjs" "$ROLE_PATH"
fi
