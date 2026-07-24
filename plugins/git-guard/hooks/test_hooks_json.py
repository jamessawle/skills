"""Regression guard for hooks.json wiring.

Both hooks must run unconditionally on every Bash call. A harness-level `if`
filter (e.g. `if: "Bash(git *)"`) looks like a free performance win, but per
anthropics/claude-code#77037 the `if` matcher can silently never fire for
compound commands even though the docs say it should — which would mask
git_guard/gh_guard entirely for the exact commands (`cmd && git ...`) they
most need to catch. The safe optimization lives inside each script instead
(see _MENTIONS_GIT / _MENTIONS_GH), which is not subject to that harness bug.
"""

from __future__ import annotations

import json
from pathlib import Path

HOOKS_JSON = Path(__file__).parent / "hooks.json"


def test_no_if_field_gates_hook_invocation() -> None:
    config = json.loads(HOOKS_JSON.read_text())
    for hooks in config["hooks"]["PreToolUse"]:
        for entry in hooks["hooks"]:
            assert "if" not in entry, (
                f"{entry['command']!r} has an `if` filter — see module docstring "
                "for why that's unsafe here"
            )
