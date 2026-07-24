"""Harness-free tests for git_guard.

Each case drives the Hook through the real Contract types — no harness, no
subprocess, no JSON — via `git_guard.dispatch(tool_before(shell(cmd), cwd=...))`,
asserting on the returned Verdict (`.is_allow` / `.is_deny` / `.is_ask` /
`.is_defer`). This is what hook-bridge's `hook-bridge-sdk` buys over the old
subprocess-and-parse-JSON test style: the same Hook the runner invokes is
exercised directly, in-process.

Branch-dependent cases (bare push, detached HEAD) reference a named repo from
the module-scoped `repos` fixture and pass its path as the Context's `cwd`, so
`current_branch()` resolves it there — dispatch stays a pure function of ctx,
with no `os.chdir` needed.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Iterator

import pytest
from hook_bridge import ToolBeforeVerdict, shell, tool_before

from git_guard import git_guard


def make_repo(branch: str) -> str:
    path = tempfile.mkdtemp()

    def git(*args: str) -> None:
        subprocess.run(["git", "-C", path, *args], check=True, capture_output=True)

    git("init", "-q", "-b", branch)
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "test")
    git("config", "commit.gpgsign", "false")
    git("commit", "-q", "--allow-empty", "-m", "init")
    return path


def make_repo_detached() -> str:
    path = make_repo("feature/test")
    subprocess.run(["git", "-C", path, "checkout", "--detach"], check=True, capture_output=True)
    return path


@pytest.fixture(scope="module")
def repos() -> Iterator[dict[str, str]]:
    paths = {
        "feature": make_repo("feature/test"),
        "main": make_repo("main"),
        "detached": make_repo_detached(),
    }
    yield paths
    for p in paths.values():
        shutil.rmtree(p, ignore_errors=True)


def decide(command: str, cwd: str) -> ToolBeforeVerdict:
    return git_guard.dispatch(tool_before(shell(command), cwd=cwd))


@pytest.mark.parametrize("command,repo_key", [
    # Safe read-only and write git commands on a feature branch.
    ("git status",                                       "feature"),
    ("git diff --staged",                                "feature"),
    ('git commit -m "feat: x"',                          "feature"),
    ("git fetch origin",                                 "feature"),
    ("git rebase main",                                  "feature"),
    ("git push -u origin claude/foo",                    "feature"),
    ("git push",                                         "feature"),  # bare push, not on main
    ("git push origin",                                  "feature"),  # remote-only, not on main
    ('git commit -m x && git push origin claude/foo',    "feature"),
    # "--no-verify" inside a commit message must not be read as the flag.
    ('git commit -m "block --no-verify in the guard"',   "feature"),
    # Explicit non-main refspec is safe even when current branch is main.
    ("git push origin feature/x",                        "main"),
    # Safe pipe targets don't downgrade a safe git command.
    ("git push -u origin claude/foo 2>&1 | tail -20",    "feature"),
    ("git log | grep fix",                               "feature"),
    ("git status | head -5 | cat",                       "feature"),
    # -n means --dry-run for fetch; the SHORT_NO_VERIFY guard is commit-only.
    ("git fetch -n",                                      "feature"),
    ("git fetch --dry-run",                               "feature"),
    # A redirect isolated between real operators lands in its own segment
    # (['2', '>&', '1']) — is_redirect_fragment recognises it as noise rather
    # than downgrading the whole call to defer.
    ("git status ; 2>&1 ; git push origin claude/foo",    "feature"),
])
def test_allow(command: str, repo_key: str, repos: dict[str, str]) -> None:
    assert decide(command, repos[repo_key]).is_allow


@pytest.mark.parametrize("command,repo_key", [
    # Push to main via various refspec forms.
    ("git push origin main",                             "feature"),
    ("git push origin HEAD:main",                        "feature"),
    ("git push origin feature:main",                     "feature"),
    ("git push --force origin main",                     "feature"),
    ("git push origin +main",                            "feature"),  # +refspec to main
    ("make build && git push origin main",               "feature"),
    ("git push origin main | tail -20",                  "feature"),  # deny beats pipe-safe
    # Bare / remote-only push while current branch is main.
    ("git push",                                         "main"),
    ("git push origin",                                  "main"),
    ("git push origin HEAD",                             "main"),
    # Hook bypass via long flag, short flag, and combined short flag.
    ("git commit --no-verify -m x",                      "feature"),
    ("git commit -n -m x",                                "feature"),
    ('git commit -nm "x"',                                "feature"),
    ("git push --no-verify origin claude/foo",           "feature"),
    ("git --no-verify push origin claude/foo",           "feature"),  # global git option
    ("git --no-verify commit -m x",                      "feature"),
    # Abbreviated long option — git accepts any unambiguous prefix.
    ("git commit --no-veri -m x",                        "feature"),  # shortest on commit
    ("git commit --no-verif -m x",                        "feature"),
    ("git push --no-verif origin feature",                "feature"),
    # Committing directly to main strands work that can never be pushed —
    # block at commit time rather than only at the eventual push.
    ('git commit -m "feat: x"',                          "main"),
    ("git commit --amend",                               "main"),
    ('git commit -m x && git push origin claude/foo',    "main"),
])
def test_deny(command: str, repo_key: str, repos: dict[str, str]) -> None:
    verdict = decide(command, repos[repo_key])
    assert verdict.is_deny
    assert verdict.reason  # deny carries a mandatory reason


@pytest.mark.parametrize("command,repo_key", [
    # Force flags — various forms.
    ("git push --force origin claude/foo",               "feature"),
    ("git push --force-with-lease",                      "feature"),
    ("git push -f origin foo",                            "feature"),
    ("git push origin +claude/foo",                      "feature"),  # +refspec = force
    ("git push -fu origin claude/foo",                   "feature"),  # combined flag with f
    ("git push -uf origin foo",                          "feature"),
    # Abbreviated force flags — git accepts any unambiguous prefix.
    ("git push --force-with-leas origin feature",        "feature"),
    ("git push --force-w origin feature",                "feature"),  # shortest unambiguous
    ("git push --force-with-leas=origin/foo origin feature", "feature"),
    ("git push --force origin claude/foo | cat",         "feature"),  # ask beats pipe-safe
    # Detached HEAD: can't resolve current branch → safer to prompt.
    ("git push",                                          "detached"),
    ("git push origin",                                   "detached"),
])
def test_ask(command: str, repo_key: str, repos: dict[str, str]) -> None:
    verdict = decide(command, repos[repo_key])
    assert verdict.is_ask
    assert verdict.reason  # ask carries a mandatory reason


@pytest.mark.parametrize("command,repo_key", [
    # Unrecognised / dangerous git subcommands.
    ("git reset --hard HEAD~1",                          "feature"),
    ("git clean -fd",                                     "feature"),
    # Non-git segment in the pipeline downgrades the whole call.
    ("git status && rm -rf foo",                          "feature"),
    ("make build",                                        "feature"),
    ("git push origin claude/foo | tee out.txt",         "feature"),  # tee writes
    ("git log | xargs rm",                                "feature"),  # xargs executes
])
def test_defer(command: str, repo_key: str, repos: dict[str, str]) -> None:
    assert decide(command, repos[repo_key]).is_defer


def test_empty_command_defers() -> None:
    # An empty command carries no git segment to vouch for → no opinion.
    assert decide("", ".").is_defer


@pytest.mark.parametrize("command", [
    "git commit -m 'open",  # unbalanced quote → can't parse safely → defer
])
def test_defer_on_unparseable(command: str) -> None:
    assert decide(command, ".").is_defer
