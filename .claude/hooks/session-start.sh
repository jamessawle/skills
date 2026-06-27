#!/bin/bash
# SessionStart hook: install the uv toolchain and run `make setup` so an agent
# can run the test suite in a fresh Claude Code on the web container. Runs only
# in the remote environment; local machines onboard with `make setup` directly.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

# Install uv if the container doesn't already provide it. Pin the version so
# fresh containers don't silently upgrade; bump this default when upgrading.
UV_INSTALL_VERSION="${UV_INSTALL_VERSION:-0.8.17}"
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | UV_VERSION="$UV_INSTALL_VERSION" sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# Onboard the same way humans do: `make setup` runs `uv sync` and installs the
# pre-commit hook. Idempotent and benefits from container caching.
uv python install
make setup
