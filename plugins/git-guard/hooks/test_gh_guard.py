"""Harness-free tests for gh_guard.

Each case drives the Hook through the real Contract types — no harness, no
subprocess, no JSON — via `gh_guard.dispatch(tool_before(shell(cmd)))`,
asserting on the returned Verdict (`.is_allow` / `.is_ask` / `.is_defer`).

Unlike git-guard, the gh guard never resolves branches, so no repo fixtures
are needed — the decision depends only on the command string.
"""

from __future__ import annotations

import pytest
from hook_bridge import ToolBeforeVerdict, shell, tool_before

from gh_guard import gh_guard


def decide(command: str) -> ToolBeforeVerdict:
    return gh_guard.dispatch(tool_before(shell(command)))


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
def test_allow(command: str) -> None:
    assert decide(command).is_allow


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
    # Concatenated shorthand fields (pflag attaches the value) still imply POST.
    "gh api repos/o/r/issues -ftitle=x",
    "gh api repos/o/r/issues -Fbody=@file.json",
    "gh api repos/o/r/issues --field=title=x",
    # ask wins over a read-only pipe target.
    "gh pr merge 1 | cat",
    # An allowed gh command combined with a gh write still asks.
    "gh pr create --fill && gh pr merge 1",
])
def test_ask(command: str) -> None:
    verdict = decide(command)
    assert verdict.is_ask
    assert verdict.reason  # ask carries a mandatory reason


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
def test_defer(command: str) -> None:
    assert decide(command).is_defer


def test_empty_command_defers() -> None:
    # An empty command carries no gh segment to vouch for → no opinion.
    assert decide("").is_defer


@pytest.mark.parametrize("command", [
    "gh pr view 'open",  # unbalanced quote → can't parse safely → defer
])
def test_defer_on_unparseable(command: str) -> None:
    assert decide(command).is_defer


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
