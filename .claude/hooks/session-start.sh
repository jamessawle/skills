#!/bin/bash
# SessionStart hook: install the uv toolchain and run `make setup` so an agent
# can run the test suite in a fresh Claude Code on the web container. Runs only
# in the remote environment; local machines onboard with `make setup` directly.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

# Install uv if the container doesn't already provide it.
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# Onboard the same way humans do: `make setup` runs `uv sync` and installs the
# pre-commit hook. Idempotent and benefits from container caching.
uv python install
make setup
