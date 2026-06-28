#!/usr/bin/env python3
"""Tests for git-guard.py.

Each parametrized case feeds a PreToolUse JSON payload to the guard and asserts
the outcome: "deny" when the guard hard-blocks via exit code 2, the emitted
permissionDecision ("ask"/"allow") otherwise, or "defer" when the guard emits
nothing and the call falls through to the normal permission prompt.

Branch-dependent cases reference a named repo from the module-scoped `repos`
fixture so they're deterministic anywhere.
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

GUARD = str(Path(__file__).with_name("git-guard.py"))


def make_repo(branch):
    path = tempfile.mkdtemp()
    def git(*args):
        subprocess.run(["git", "-C", path, *args], check=True, capture_output=True)
    git("init", "-q", "-b", branch)
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "test")
    git("config", "commit.gpgsign", "false")
    git("commit", "-q", "--allow-empty", "-m", "init")
    return path


def make_repo_detached():
    path = make_repo("feature/test")
    subprocess.run(["git", "-C", path, "checkout", "--detach"], check=True, capture_output=True)
    return path


@pytest.fixture(scope="module")
def repos():
    paths = {
        "feature":  make_repo("feature/test"),
        "main":     make_repo("main"),
        "detached": make_repo_detached(),
    }
    yield paths
    for p in paths.values():
        shutil.rmtree(p, ignore_errors=True)


def decide(command, cwd):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    proc = subprocess.run(["python3", GUARD], input=payload, capture_output=True, text=True, cwd=cwd)
    if proc.returncode == 2:
        return "deny"
    out = proc.stdout.strip()
    return "defer" if not out else json.loads(out)["hookSpecificOutput"]["permissionDecision"]


@pytest.mark.parametrize("command,repo_key", [
    # Safe read-only and write git commands on a feature branch.
    ("git status",                                           "feature"),
    ("git diff --staged",                                    "feature"),
    ('git commit -m "feat: x"',                             "feature"),
    ("git fetch origin",                                     "feature"),
    ("git rebase main",                                      "feature"),
    ("git push -u origin claude/foo",                       "feature"),
    ("git push",                                             "feature"),  # bare push, not on main
    ("git push origin",                                      "feature"),  # remote-only, not on main
    ('git commit -m x && git push origin claude/foo',       "feature"),
    # "--no-verify" inside a commit message must not be read as the flag.
    ('git commit -m "block --no-verify in the guard"',      "feature"),
    # Explicit non-main refspec is safe even when current branch is main.
    ("git push origin feature/x",                           "main"),
    # Safe pipe targets don't downgrade a safe git command.
    ("git push -u origin claude/foo 2>&1 | tail -20",       "feature"),
    ("git log | grep fix",                                   "feature"),
    ("git status | head -5 | cat",                          "feature"),
    # -n means --dry-run for fetch; the SHORT_NO_VERIFY guard is commit-only.
    ("git fetch -n",                                         "feature"),
    ("git fetch --dry-run",                                  "feature"),
])
def test_allow(command, repo_key, repos):
    assert decide(command, repos[repo_key]) == "allow"


@pytest.mark.parametrize("command,repo_key", [
    # Push to main via various refspec forms.
    ("git push origin main",                                 "feature"),
    ("git push origin HEAD:main",                            "feature"),
    ("git push origin feature:main",                         "feature"),
    ("git push --force origin main",                         "feature"),
    ("git push origin +main",                                "feature"),  # +refspec to main
    ("make build && git push origin main",                   "feature"),
    ("git push origin main | tail -20",                      "feature"),  # deny beats pipe-safe
    # Bare / remote-only push while current branch is main.
    ("git push",                                             "main"),
    ("git push origin",                                      "main"),
    ("git push origin HEAD",                                 "main"),
    # Hook bypass via long flag, short flag, and combined short flag.
    ("git commit --no-verify -m x",                         "feature"),
    ("git commit -n -m x",                                   "feature"),
    ('git commit -nm "x"',                                   "feature"),
    ("git push --no-verify origin claude/foo",              "feature"),
    ("git --no-verify push origin claude/foo",              "feature"),  # global git option
    ("git --no-verify commit -m x",                         "feature"),
    # Abbreviated long option — git accepts any unambiguous prefix.
    ("git commit --no-veri -m x",                           "feature"),  # shortest on commit
    ("git commit --no-verif -m x",                          "feature"),
    ("git push --no-verif origin feature",                  "feature"),
])
def test_deny(command, repo_key, repos):
    assert decide(command, repos[repo_key]) == "deny"


@pytest.mark.parametrize("command,repo_key", [
    # Force flags — various forms.
    ("git push --force origin claude/foo",                  "feature"),
    ("git push --force-with-lease",                         "feature"),
    ("git push -f origin foo",                              "feature"),
    ("git push origin +claude/foo",                         "feature"),  # +refspec = force
    ("git push -fu origin claude/foo",                      "feature"),  # combined flag with f
    ("git push -uf origin foo",                             "feature"),
    # Abbreviated force flags — git accepts any unambiguous prefix.
    ("git push --force-with-leas origin feature",           "feature"),
    ("git push --force-w origin feature",                   "feature"),  # shortest unambiguous
    ("git push --force-with-leas=origin/foo origin feature", "feature"),
    ("git push --force origin claude/foo | cat",            "feature"),  # ask beats pipe-safe
    # Detached HEAD: can't resolve current branch → safer to prompt.
    ("git push",                                            "detached"),
    ("git push origin",                                     "detached"),
])
def test_ask(command, repo_key, repos):
    assert decide(command, repos[repo_key]) == "ask"


@pytest.mark.parametrize("command,repo_key", [
    # Unrecognised / dangerous git subcommands.
    ("git reset --hard HEAD~1",                             "feature"),
    ("git clean -fd",                                       "feature"),
    # Non-git segment in the pipeline downgrades the whole call.
    ("git status && rm -rf foo",                            "feature"),
    ("make build",                                          "feature"),
    ("git push origin claude/foo | tee out.txt",            "feature"),  # tee writes
    ("git log | xargs rm",                                  "feature"),  # xargs executes
])
def test_defer(command, repo_key, repos):
    assert decide(command, repos[repo_key]) == "defer"


def test_deny_contract(repos):
    """Denials must hard-block via exit 2, write reason to stderr, emit nothing to stdout."""
    payload = json.dumps({"tool_input": {"command": "git push origin main"}})
    proc = subprocess.run(["python3", GUARD], input=payload, capture_output=True, text=True,
                          cwd=repos["feature"])
    assert proc.returncode == 2
    assert proc.stdout.strip() == ""
    assert "main" in proc.stderr.lower()


@pytest.mark.parametrize("raw", [
    "not valid json",
    json.dumps({"tool_input": {"command": "git commit -m 'open"}}),  # unbalanced quote
])
def test_defer_malformed_input(raw, repos):
    """Malformed JSON and unbalanced quotes both defer — no output, exit 0."""
    proc = subprocess.run(["python3", GUARD], input=raw, capture_output=True, text=True,
                          cwd=repos["feature"])
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
