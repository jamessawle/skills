#!/usr/bin/env python3
"""Tests for git-guard.py.

Each case feeds a PreToolUse JSON payload to the guard and asserts the outcome:
"deny" when the guard hard-blocks via exit code 2, the emitted permissionDecision
("ask"/"allow") otherwise, or "defer" when the guard emits nothing and the call
falls through to the normal permission prompt. Branch-dependent cases run inside a
throwaway repo on a known branch so they're deterministic anywhere.
"""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

GUARD = str(Path(__file__).with_name("git-guard.py"))


def make_repo(branch):
    """A throwaway git repo with one commit on `branch`; returns its path."""
    path = tempfile.mkdtemp()

    def git(*args):
        subprocess.run(["git", "-C", path, *args], check=True, capture_output=True)

    git("init", "-q", "-b", branch)
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "test")
    git("config", "commit.gpgsign", "false")
    git("commit", "-q", "--allow-empty", "-m", "init")
    return path


def decide(command, cwd):
    """Run the guard against `command` from `cwd`; return its decision."""
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
    proc = subprocess.run(
        ["python3", GUARD], input=payload, capture_output=True, text=True, cwd=cwd,
    )
    if proc.returncode == 2:  # hard block via exit code, reason on stderr
        return "deny"
    out = proc.stdout.strip()
    if not out:
        return "defer"
    return json.loads(out)["hookSpecificOutput"]["permissionDecision"]


class GitGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.feature = make_repo("feature/test")
        cls.main = make_repo("main")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.feature, ignore_errors=True)
        shutil.rmtree(cls.main, ignore_errors=True)

    def expect(self, decision, commands, cwd=None):
        for command in commands:
            with self.subTest(command=command):
                self.assertEqual(decide(command, cwd or self.feature), decision)

    # ALLOW — recognised safe git, including normal feature-branch pushes.
    def test_allow_safe_git(self):
        self.expect("allow", [
            "git status",
            "git diff --staged",
            'git commit -m "feat: x"',
            "git fetch origin",
            "git rebase main",
            "git push -u origin claude/foo",
            "git push",                                  # bare push on a feature branch
            "git push origin",                           # remote only, on a feature branch
            'git commit -m x && git push origin claude/foo',
        ])

    def test_allow_commit_message_mentioning_the_flag(self):
        # The words "--no-verify" in a message must not be read as the flag.
        self.expect("allow", ['git commit -m "block --no-verify in the guard"'])

    def test_allow_explicit_non_main_push_from_main(self):
        self.expect("allow", ["git push origin feature/x"], cwd=self.main)

    def test_allow_git_piped_to_safe_filter(self):
        # Piping git output through a read-only pager/filter still auto-approves.
        self.expect("allow", [
            "git push -u origin claude/foo 2>&1 | tail -20",
            "git log | grep fix",
            "git status | head -5 | cat",
        ])

    # DENY/ASK still win when a safe filter is in the pipe.
    def test_deny_push_to_main_piped(self):
        self.expect("deny", ["git push origin main | tail -20"])

    def test_ask_force_push_piped(self):
        self.expect("ask", ["git push --force origin claude/foo | cat"])

    # ASK — force-push to any branch.
    def test_ask_force_push(self):
        self.expect("ask", [
            "git push --force origin claude/foo",
            "git push --force-with-lease",
            "git push -f origin foo",
            "git push origin +claude/foo",               # +refspec is a force push
        ])

    # DENY — any push whose destination is main.
    def test_deny_push_to_main(self):
        self.expect("deny", [
            "git push origin main",
            "git push origin HEAD:main",
            "git push origin feature:main",
            "git push --force origin main",
            "make build && git push origin main",
        ])

    def test_deny_uses_exit_2_with_stderr_reason(self):
        # The hardening contract: denials hard-block via exit 2 (beats allow
        # rules) and explain themselves on stderr, not stdout.
        payload = json.dumps({"tool_input": {"command": "git push origin main"}})
        proc = subprocess.run(
            ["python3", GUARD], input=payload, capture_output=True, text=True,
            cwd=self.feature,
        )
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout.strip(), "")
        self.assertIn("main", proc.stderr.lower())

    def test_deny_push_while_on_main(self):
        self.expect("deny", [
            "git push",                                  # bare push, branch resolved with git
            "git push origin",                           # remote only
            "git push origin HEAD",                      # HEAD resolves to main
        ], cwd=self.main)

    # DENY — bypassing git hooks.
    def test_deny_hook_bypass(self):
        self.expect("deny", [
            "git commit --no-verify -m x",
            "git commit -n -m x",
            'git commit -nm "x"',
            "git push --no-verify origin claude/foo",
        ])

    # DEFER — unrecognised/dangerous git, or a non-git segment.
    def test_defer_unrecognised(self):
        self.expect("defer", [
            "git reset --hard HEAD~1",
            "git clean -fd",
            "git status && rm -rf foo",
            "make build",
            "git push origin claude/foo | tee out.txt",  # tee writes — not allowlisted
            "git log | xargs rm",                        # xargs executes — not allowlisted
        ])


if __name__ == "__main__":
    unittest.main(verbosity=2)
