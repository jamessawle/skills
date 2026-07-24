# /// script
# requires-python = ">=3.12"
# dependencies = ["hook-bridge-sdk"]
# ///
"""PreToolUse guard — GitHub CLI (`gh`) permission policy, companion to git-guard.

Authored against the generic hook-bridge Contract so the same file runs
unchanged on both claude-code and codex (see ../hooks.json, which invokes it
through `hook-bridge-runner --harness <claude-code|codex>`).

  - ALLOW recognised read-only gh commands (view/list/diff/status/checks/watch/
          download across pr, issue, run, workflow, repo, release, …; every
          `gh search …`; `gh api` GET/HEAD requests) and the one vouched-for
          write, `gh pr create`.
  - ASK   for every other gh command — merges, closes, comments, edits, reviews,
          reruns, repo/secret/auth mutations, and `gh api` POST/PATCH/PUT/DELETE.
  - DEFER when no gh segment is present, so git-guard and the normal permission
          prompt handle non-gh commands untouched.

Branch creation is intentionally NOT handled here: branches are made with git,
which git-guard already auto-approves — this guard governs `gh` only.

As in git-guard, a hook `allow` approves the whole Bash call, so the command is
tokenised with shlex (quote-aware) and split on shell operators; every segment
must be an allowed gh command (or a read-only pipe target) for the call to
auto-approve. An unrecognised gh segment downgrades the call to `ask`; a non-gh,
non-pipe segment makes the guard defer to the normal prompt. Using a real
tokeniser means a PR body that merely mentions `gh pr merge` is never mistaken
for the command.

This guard never hard-blocks (no deny outcome): the policy is allow-or-ask, so
every decision is an advisory Verdict.
"""

from __future__ import annotations

import re

from hook_bridge import ToolBeforeContext, ToolBeforeVerdict, allow, ask, defer, hook

from _shell import SAFE_PIPE as _BASE_SAFE_PIPE
from _shell import is_redirect_fragment, segments

# Cheap pre-filter: no segment can classify as a gh command unless the literal
# word "gh" appears somewhere in the raw string, so this lets non-gh calls (the
# overwhelming majority of Bash calls) skip tokenising entirely. Word-boundary,
# so "high"/"though" don't trigger the slower path; a false positive (e.g. a
# "gh-" prefixed filename) just falls through to the real classification.
_MENTIONS_GH = re.compile(r"\bgh\b")

# gh subcommands (the verb within a command group) that only read state — safe
# to auto-approve wherever they appear: `gh pr view`, `gh run list`,
# `gh release download`, `gh auth status`, `gh secret list` (names only), …
READ_SUBCMDS = {
    "view", "list", "ls", "diff", "status", "checks", "watch", "download",
}
# Top-level gh commands that are read-only regardless of their subcommand.
READ_GROUPS = {"search", "status"}
# The only write commands explicitly vouched for, as (group, subcommand) pairs.
ALLOW_WRITES = {("pr", "create")}
# `jq` is included on top of git-guard's base pipe set since `gh api … | jq` is
# the idiomatic way to read JSON.
SAFE_PIPE = _BASE_SAFE_PIPE | {"jq"}

# `gh api` flags that turn a request into a mutation. Any --field/-f/-F (gh sends
# those as a POST body unless --method says otherwise) or an explicit method.
_API_FIELD_FLAGS = {"-f", "-F", "--field", "--raw-field", "--input"}
_API_METHOD_FLAGS = {"-X", "--method"}

# Verdict strings returned by classify_segment().
_GH_ALLOW = "gh-allow"   # vetted read-only gh command (or gh pr create)
_GH_ASK = "gh-ask"       # any other gh command — confirm first
_PIPE_SAFE = "pipe-safe"  # read-only filter; harmless but doesn't vouch alone
_UNSAFE = "unsafe"        # non-gh, non-pipe segment
_SKIP = "skip"            # redirect fragment or empty; ignored


def command_words(tokens: list[str]) -> tuple[str, str]:
    """Return (group, subcommand) — the first two non-flag words after `gh`.
    Skipping flags means `gh pr view -R o/r` still resolves to ("pr", "view")."""
    words = [t for t in tokens[1:] if not t.startswith("-")]
    return (words[0] if words else "", words[1] if len(words) > 1 else "")


def _is_field_flag(tok: str) -> bool:
    """True if a token is a `gh api` body-field flag in any of its forms:
    `-f`/`-F`/`--field`/`--raw-field`/`--input`, the `--field=value` and `-f=value`
    long-ish forms, and the concatenated shorthand `-fkey=val` / `-Fkey=val`
    (pflag attaches a shorthand's value with no space). No other `gh api`
    shorthand uses f/F, so the `-f`/`-F` prefix never catches an unrelated flag."""
    if tok in _API_FIELD_FLAGS or tok.split("=", 1)[0] in _API_FIELD_FLAGS:
        return True
    return tok[:2] in ("-f", "-F") and not tok.startswith("--")


def api_is_read(args: list[str]) -> bool:
    """True if a `gh api` call only reads — method GET/HEAD (explicit, or the
    default when no body fields are supplied). An explicit method always wins
    over the field-presence heuristic: `--method GET -f x=y` stays a read."""
    method, has_field = None, False
    i = 0
    while i < len(args):
        tok = args[i]
        if tok in _API_METHOD_FLAGS:
            method = args[i + 1].upper() if i + 1 < len(args) else None
            i += 2
            continue
        if tok.startswith("--method="):
            method = tok.split("=", 1)[1].upper()
        elif tok.startswith("-X") and len(tok) > 2:  # combined -XPOST
            method = tok[2:].upper()
        elif _is_field_flag(tok):
            has_field = True
        i += 1
    if method is None:
        method = "POST" if has_field else "GET"
    return method in ("GET", "HEAD")


def classify_segment(tokens: list[str]) -> str:
    """Classify one command segment and return a verdict string."""
    if is_redirect_fragment(tokens):
        return _SKIP
    if tokens[0] != "gh":
        return _PIPE_SAFE if tokens[0] in SAFE_PIPE else _UNSAFE

    group, sub = command_words(tokens)
    if not group:
        return _GH_ALLOW  # bare `gh`, `gh --help`, `gh --version`
    if group == "api":
        idx = tokens.index("api")
        return _GH_ALLOW if api_is_read(tokens[idx + 1:]) else _GH_ASK
    if group in READ_GROUPS:
        return _GH_ALLOW
    if (group, sub) in ALLOW_WRITES:
        return _GH_ALLOW
    if sub in READ_SUBCMDS:
        return _GH_ALLOW
    return _GH_ASK


@hook
def gh_guard(ctx: ToolBeforeContext) -> ToolBeforeVerdict:
    """Apply the gh policy to a `tool.before` event, returning a Verdict.

    The pure seam — harness-free tests call this via `gh_guard.dispatch`.
    """
    if ctx.tool.kind != "shell":
        return defer()
    command = ctx.tool.command
    if not command:
        return defer()
    if not _MENTIONS_GH.search(command):
        return defer()

    try:
        classified = [classify_segment(t) for t in segments(command)]
    except ValueError:
        return defer()  # unbalanced quotes → can't parse safely → no opinion
    verdicts = [v for v in classified if v != _SKIP]

    # Defer when no gh segment is present (pipe-only or non-gh commands), so
    # git-guard and the normal permission prompt own those calls.
    if all(v in (_PIPE_SAFE, _UNSAFE) for v in verdicts):
        return defer()

    if any(v == _GH_ASK for v in verdicts):
        return ask("This gh command isn't on the auto-approved allowlist "
                    "(read-only commands and gh pr create) — confirm before proceeding.")

    if all(v in (_GH_ALLOW, _PIPE_SAFE) for v in verdicts):
        return allow()

    return defer()


if __name__ == "__main__":  # runnable as a subprocess AND importable in tests
    gh_guard.run()
