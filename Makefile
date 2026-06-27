.PHONY: setup test

# Onboard the toolchain: sync the uv environment (dev deps: pytest, pre-commit)
# and install the git pre-commit hook so commits run the test suite. Idempotent.
setup:
	uv sync
	uv run pre-commit install

# Run the test suite with pytest, which discovers every test_*.py across the
# repo (config in pyproject.toml). Runs as its own CI job and pre-commit hook.
test:
	@uv run pytest
