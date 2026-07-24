"""Unit tests for _shell.py — the tokenising shared by git_guard and gh-guard.

Both guards' own test suites exercise this indirectly, but only through
commands where each guard happens to route around a given edge case the same
way. These tests drive `segments()`/`is_redirect_fragment()` directly so a
tokenising bug is caught at the source.
"""

from __future__ import annotations

import pytest

from _shell import is_redirect_fragment, segments


@pytest.mark.parametrize("cmd,expected", [
    ("git status",                       [["git", "status"]]),
    ("",                                  []),
    ("git commit -m x && git push",       [["git", "commit", "-m", "x"], ["git", "push"]]),
    ("git log | grep fix",               [["git", "log"], ["grep", "fix"]]),
    ("git status; git push",             [["git", "status"], ["git", "push"]]),
    ("git push || echo failed",          [["git", "push"], ["echo", "failed"]]),
    ("git status | head -5 | cat",       [["git", "status"], ["head", "-5"], ["cat"]]),
    ('git commit -m "a && b"',           [["git", "commit", "-m", "a && b"]]),
    # "2>&1" has no bare "&"/"|" token to split on — ">&" is one punctuation
    # token, so it stays glued to the segment it trails rather than forming
    # its own fragment. Only a real operator on both sides isolates one (below).
    ("git push -u origin foo 2>&1 | tail -20",
     [["git", "push", "-u", "origin", "foo", "2", ">&", "1"], ["tail", "-20"]]),
    # A redirect flanked by real operators *does* land in its own segment —
    # and it is NOT a pure digit/bracket fragment, so is_redirect_fragment
    # doesn't recognise it either (see test_is_redirect_fragment_false below).
    ("git status ; 2>&1 ; git push",
     [["git", "status"], ["2", ">&", "1"], ["git", "push"]]),
])
def test_segments(cmd: str, expected: list[list[str]]) -> None:
    assert segments(cmd) == expected


def test_segments_raises_on_unbalanced_quotes() -> None:
    with pytest.raises(ValueError):
        segments("git commit -m 'open")


@pytest.mark.parametrize("tokens", [
    [],
    ["1"],
    [">"],
    ["<<"],
    ["1", "2"],
])
def test_is_redirect_fragment_true(tokens: list[str]) -> None:
    assert is_redirect_fragment(tokens)


@pytest.mark.parametrize("tokens", [
    ["git", "status"],
    ["cat"],
    ["1", "git"],       # a real command mixed with a digit isn't a pure fragment
    ["2", ">&", "1"],   # the ">&" token isn't one of the recognised redirect
                        # symbols (">", "<", ">>", "<<") — a standalone "2>&1"
                        # segment defers rather than being skipped as noise.
                        # Overly cautious, not unsafe: a segment this classify_segment
                        # doesn't recognise just downgrades the whole call to defer.
])
def test_is_redirect_fragment_false(tokens: list[str]) -> None:
    assert not is_redirect_fragment(tokens)
