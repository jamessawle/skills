#!/usr/bin/env python3
"""Tests for gh-guard.py.

Each parametrized case feeds a PreToolUse JSON payload to the guard and asserts
the emitted permissionDecision ("allow"/"ask"), or "defer" when the guard emits
nothing and the call falls through to the normal permission prompt.

Unlike git-guard, the gh guard never resolves branches, so no repo fixtures are
needed — the decision depends only on the command string.
"""

import json
import subprocess
from pathlib import Path

import pytest

GUARD = str(Path(__file__).with_name("gh-guard.py"))


def decide(command):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    proc = subprocess.run(["python3", GUARD], input=payload, capture_output=True, text=True)
    out = proc.stdout.strip()
    return "defer" if not out else json.loads(out)["hookSpecificOutput"]["permissionDecision"]


@pytest.mark.parametrize("command", [
    # Read-only commands across the common groups.
    "gh pr view 123",
    "gh pr list",
    "gh pr diff 123",
    "gh pr checks 123",
    "gh pr status",
    "gh issue view 5",
    "gh issue list",
    "gh run list",
    "gh run view 999",
    "gh run watch 999",
    "gh workflow list",
    "gh workflow view ci.yml",
    "gh repo view",
    "gh release list",
    "gh release download v1.0.0",
    "gh auth status",
    "gh secret list",                      # lists names only, not values
    # Whole-group reads.
    "gh search prs --author @me",
    "gh search issues label:bug",
    "gh status",
    # Bare / help / version are harmless no-ops.
    "gh",
    "gh --version",
    # The one vouched-for write.
    "gh pr create --fill",
    'gh pr create -t "feat: x" -b "body"',
    # Reading comments via the API (GET is the default, explicit GET, with flags).
    "gh api repos/o/r/pulls/1/comments",
    "gh api -X GET repos/o/r/issues/1/comments",
    "gh api --method GET repos/o/r/issues/1/comments",
    # Read-only pipe targets don't downgrade an allowed gh command.
    "gh pr view 1 --comments | grep LGTM",
    "gh run view 1 2>&1 | tail -20",
    "gh api repos/o/r/commits | jq '.[].sha'",
    # Flags before positionals still resolve the command group/verb.
    "gh pr view 1 -R owner/repo",
])
def test_allow(command):
    assert decide(command) == "allow"


@pytest.mark.parametrize("command", [
    # Writes that are not on the allowlist.
    "gh pr merge 1",
    "gh pr close 1",
    "gh pr comment 1 -b hi",
    "gh pr edit 1 --add-label bug",
    "gh pr review 1 --approve",
    "gh issue create -t x -b y",
    "gh issue close 1",
    "gh run rerun 1",
    "gh run cancel 1",
    "gh run delete 1",
    "gh workflow run ci.yml",
    "gh workflow disable ci.yml",
    "gh repo create foo",
    "gh repo delete foo",
    "gh repo fork",
    "gh secret set TOKEN",
    "gh auth login",
    # gh api mutations — explicit method or body fields imply a write.
    "gh api -X POST repos/o/r/issues -f title=x",
    "gh api repos/o/r/issues -f title=x",          # fields → POST
    "gh api --method DELETE repos/o/r/issues/1",
    "gh api -XPATCH repos/o/r/pulls/1 -f state=closed",
    # ask wins over a read-only pipe target.
    "gh pr merge 1 | cat",
    # An allowed gh command combined with a gh write still asks.
    "gh pr create --fill && gh pr merge 1",
])
def test_ask(command):
    assert decide(command) == "ask"


@pytest.mark.parametrize("command", [
    # No gh segment — git-guard / the normal prompt own these.
    "git push origin claude/foo",
    "make build",
    "ls -la",
    "cat README.md | grep gh",
    # An allowed gh command mixed with a dangerous non-gh segment defers to the
    # normal prompt rather than auto-approving or asking on gh's behalf.
    "gh pr view 1 && rm -rf foo",
])
def test_defer(command):
    assert decide(command) == "defer"


@pytest.mark.parametrize("raw", [
    "not valid json",
    json.dumps({"tool_input": {"command": "gh pr view 'open"}}),  # unbalanced quote
])
def test_defer_malformed_input(raw):
    """Malformed JSON and unbalanced quotes both defer — no output, exit 0."""
    proc = subprocess.run(["python3", GUARD], input=raw, capture_output=True, text=True)
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
