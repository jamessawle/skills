.PHONY: setup test

# Onboard the toolchain: sync the uv environment (dev deps: pytest, pre-commit)
# and install the git pre-commit + pre-push hooks (tests on commit, plugin
# version-bump check on push). Idempotent.
setup:
	@uv sync
	@uv run pre-commit install --hook-type pre-commit --hook-type pre-push

# Run the test suite with pytest, which discovers every test_*.py across the
# repo (config in pyproject.toml). Runs as its own CI job and pre-commit hook.
test:
	@uv run pytest
