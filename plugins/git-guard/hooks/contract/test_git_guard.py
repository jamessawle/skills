"""Harness-free tests for the Contract-ported git-guard.

Each case drives the Hook through the real Contract types — no harness, no
subprocess, no JSON — by calling `git_guard.dispatch(tool_before(shell(cmd)))`
and asserting on the returned Verdict. This is the testability proof-point: the
same Hook the runner invokes is exercised here with nothing but the SDK present.

PREVIEW / not yet runnable: `hook_bridge` (hook-bridge-sdk) is not published yet,
so `import hook_bridge` will fail until hook-bridge v1 ships. See README.md.

Branch-dependent cases (bare push, detached HEAD) reference a named repo from the
module-scoped `repos` fixture and pass its path as the Context's `cwd`, so
git-guard resolves the branch there. dispatch stays a pure function of its
Context — no `os.chdir`.
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
    """Run the Hook's pure seam over a shell command in `cwd`."""
    return git_guard.dispatch(tool_before(shell(command), cwd=cwd))


@pytest.mark.parametrize("command,repo_key", [
    ("git status",                                     "feature"),
    ("git diff --staged",                              "feature"),
    ('git commit -m "feat: x"',                        "feature"),
    ("git fetch origin",                               "feature"),
    ("git rebase main",                                "feature"),
    ("git push -u origin claude/foo",                  "feature"),
    ("git push",                                       "feature"),  # bare push, not on main
    ("git push origin",                                "feature"),  # remote-only, not on main
    ('git commit -m x && git push origin claude/foo',  "feature"),
    ('git commit -m "block --no-verify in the guard"', "feature"),
    ("git push origin feature/x",                      "main"),
    ("git push -u origin claude/foo 2>&1 | tail -20",  "feature"),
    ("git log | grep fix",                             "feature"),
    ("git status | head -5 | cat",                     "feature"),
    ("git fetch -n",                                   "feature"),
    ("git fetch --dry-run",                            "feature"),
])
def test_allow(command: str, repo_key: str, repos: dict[str, str]) -> None:
    assert decide(command, repos[repo_key]).is_allow


@pytest.mark.parametrize("command,repo_key", [
    ("git push origin main",                           "feature"),
    ("git push origin HEAD:main",                      "feature"),
    ("git push origin feature:main",                   "feature"),
    ("git push --force origin main",                   "feature"),
    ("git push origin +main",                          "feature"),  # +refspec to main
    ("make build && git push origin main",             "feature"),
    ("git push origin main | tail -20",                "feature"),  # deny beats pipe-safe
    ("git push",                                       "main"),
    ("git push origin",                                "main"),
    ("git push origin HEAD",                           "main"),
    ("git commit --no-verify -m x",                    "feature"),
    ("git commit -n -m x",                             "feature"),
    ('git commit -nm "x"',                             "feature"),
    ("git push --no-verify origin claude/foo",         "feature"),
    ("git --no-verify push origin claude/foo",         "feature"),  # global git option
    ("git --no-verify commit -m x",                    "feature"),
    ("git commit --no-veri -m x",                      "feature"),  # shortest on commit
    ("git commit --no-verif -m x",                     "feature"),
    ("git push --no-verif origin feature",             "feature"),
])
def test_deny(command: str, repo_key: str, repos: dict[str, str]) -> None:
    verdict = decide(command, repos[repo_key])
    assert verdict.is_deny
    assert verdict.reason  # deny carries a mandatory reason


@pytest.mark.parametrize("command,repo_key", [
    ("git push --force origin claude/foo",             "feature"),
    ("git push --force-with-lease",                    "feature"),
    ("git push -f origin foo",                         "feature"),
    ("git push origin +claude/foo",                    "feature"),  # +refspec = force
    ("git push -fu origin claude/foo",                 "feature"),  # combined flag with f
    ("git push -uf origin foo",                        "feature"),
    ("git push --force-with-leas origin feature",      "feature"),
    ("git push --force-w origin feature",              "feature"),  # shortest unambiguous
    ("git push --force-with-leas=origin/foo origin feature", "feature"),
    ("git push --force origin claude/foo | cat",       "feature"),  # ask beats pipe-safe
    ("git push",                                       "detached"),
    ("git push origin",                                "detached"),
])
def test_ask(command: str, repo_key: str, repos: dict[str, str]) -> None:
    verdict = decide(command, repos[repo_key])
    assert verdict.is_ask
    assert verdict.reason  # ask carries a mandatory reason


@pytest.mark.parametrize("command,repo_key", [
    ("git reset --hard HEAD~1",                        "feature"),
    ("git clean -fd",                                  "feature"),
    ("git status && rm -rf foo",                       "feature"),
    ("make build",                                     "feature"),
    ("git push origin claude/foo | tee out.txt",       "feature"),  # tee writes
    ("git log | xargs rm",                             "feature"),  # xargs executes
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
