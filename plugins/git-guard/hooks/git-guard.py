#!/usr/bin/env python3
"""PreToolUse guard — the single source of truth for git permission policy:

  - DENY  a push whose destination branch is `main` — an explicit refspec
          (`origin main`, `HEAD:main`, `feature:main`), or a bare push /
          `git push <remote>` while the current branch is `main` (no `main`
          appears in the command then, so the branch is resolved with git).
  - DENY  any attempt to bypass git hooks (`--no-verify`, `git commit -n`).
  - ASK   before any force-push (rewrites remote history).
  - ALLOW recognised read/safe git commands, including normal feature pushes.
  - DEFER otherwise: emit no decision so the normal permission prompt applies.

Denials use exit code 2, not a JSON `"deny"` decision. An exit-2 block stops the
call *before* the permission rules are evaluated, so a push to `main` is blocked
even on a machine whose settings.json carries a broad `Bash(git *)` allow rule;
a JSON deny is only one input to that later rule resolution. The block reason is
written to stderr, which Claude Code surfaces to the model.

A hook `allow` approves the whole Bash call, so the command is tokenised with
shlex (quote-aware) and split on shell operators; every segment must be a
vouched-for git command before the call is auto-allowed. A dangerous part (e.g.
`git reset --hard`) or any non-git segment downgrades the call to a prompt;
deny/ask scan conservatively and win over allow. Using a real tokeniser means a
commit message that merely *mentions* `--no-verify` is not mistaken for the flag.

Read-only pager/filter tools (tail, head, grep, …) are allowlisted as harmless
pipe targets, so the everyday `git push … | tail` and `git log | grep x` still
auto-approve rather than falling through to a prompt. At least one git segment
must be present — a call with no git command is always deferred.
"""

import json
import re
import shlex
import subprocess
import sys

# git subcommands safe to auto-approve. Anything else (reset, clean, gc,
# reflog, …) is left to defer to the normal permission prompt.
SAFE = {
    "status", "diff", "log", "show", "branch", "checkout", "switch", "add",
    "commit", "fetch", "pull", "push", "rebase", "merge", "restore", "stash", "remote",
    "rev-parse", "tag", "describe", "blame", "shortlog", "ls-files",
    "symbolic-ref",
}
# Read-only pager/filter tools harmless as pipe targets. Excludes anything that
# writes or executes (tee, xargs, sed, awk, …) — those still downgrade to prompt.
SAFE_PIPE = {
    "cat", "head", "tail", "less", "more", "grep", "egrep", "fgrep", "wc",
    "sort", "uniq", "nl", "cut", "tr", "rev", "column",
}
OPERATORS     = {"&&", "||", "|", "|&", ";", "&", "(", ")"}
SHORT_NO_VERIFY = re.compile(r"-[A-Za-z]*n[A-Za-z]*")  # -n, -nm, -vn, … (commit only)
_FORCE_FLAG_RE  = re.compile(r"^(?:--force|--force-with-lease(?:=.*)?|-[A-Za-z]*f[A-Za-z]*)$")

# Verdict strings returned by classify_segment().
_GIT_SAFE   = "git-safe"   # vetted git command
_GIT_ASK    = "git-ask"    # needs force-push confirmation
_PIPE_SAFE  = "pipe-safe"  # read-only filter; harmless but doesn't vouch alone
_UNSAFE     = "unsafe"     # unrecognised/dangerous; falls through to prompt
_SKIP       = "skip"       # redirect fragment or empty; ignored
_DENY_HOOKS = "deny:hooks" # hook bypass — hard-block
_DENY_MAIN  = "deny:main"  # push to main — hard-block

_DENY_MESSAGES = {
    _DENY_HOOKS: "Bypassing git hooks (--no-verify) is not allowed.",
    _DENY_MAIN:  "Pushes to main are not allowed — use a feature branch and open a PR.",
}


def emit(decision, reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }}))
    sys.exit(0)


def block(reason):
    """Hard-block via exit 2 — beats even a broad allow rule in settings.json."""
    print(reason, file=sys.stderr)
    sys.exit(2)


def current_branch():
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        branch = out.stdout.strip()
        return None if branch in ("", "HEAD") else branch
    except Exception:
        return None


def segments(cmd):
    """Quote-aware split into command segments (lists of tokens).
    Raises ValueError on unbalanced quotes."""
    lexer = shlex.shlex(cmd, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    out, cur = [], []
    for tok in lexer:
        if tok in OPERATORS:
            if cur:
                out.append(cur)
                cur = []
        else:
            cur.append(tok)
    if cur:
        out.append(cur)
    return out


def push_verdict(args):
    """Analyse `git push` args. Returns "deny" | "ask" | "safe"."""
    force = False
    positionals = []
    for tok in args:
        if _FORCE_FLAG_RE.match(tok):
            force = True
        elif not tok.startswith("-"):
            positionals.append(tok)
    refspecs = positionals[1:]  # first positional is the remote
    targets = []
    if not refspecs:
        targets.append(current_branch())  # bare push → resolve current branch
    else:
        for spec in refspecs:
            if spec.startswith("+"):       # +refspec is a force push
                force, spec = True, spec[1:]
            dest = spec.split(":")[-1] if ":" in spec else spec
            targets.append(current_branch() if dest == "HEAD" else dest)
    if any(t is None for t in targets):
        return "ask"  # can't resolve branch (detached HEAD or git error) → prompt
    if any(t == "main" for t in targets):
        return "deny"
    return "ask" if force else "safe"


def classify_segment(tokens):
    """Classify one command segment and return a verdict string.

    Redirect fragments (e.g. lone ['1'] from splitting '2>&1' on '&') and empty
    lists are skipped. Non-git segments are pipe-safe or unsafe. Git segments are
    checked for hook-bypass and push policy in that order.
    """
    if not tokens or all(t.isdigit() or t in (">", "<", ">>", "<<") for t in tokens):
        return _SKIP
    if tokens[0] != "git":
        return _PIPE_SAFE if tokens[0] in SAFE_PIPE else _UNSAFE

    sub  = tokens[1] if len(tokens) > 1 else ""
    args = tokens[2:]

    if "--no-verify" in tokens[1:] or (
        sub == "commit" and any(SHORT_NO_VERIFY.fullmatch(a) for a in args)
    ):
        return _DENY_HOOKS

    if sub == "push":
        verdict = push_verdict(args)
        if verdict == "deny":
            return _DENY_MAIN
        return _GIT_ASK if verdict == "ask" else _GIT_SAFE

    return _GIT_SAFE if sub in SAFE else _UNSAFE


def main():
    if sys.version_info < (3, 7):
        return  # capture_output needs 3.7+; defer rather than crash

    raw = sys.stdin.read()
    try:
        cmd = json.loads(raw).get("tool_input", {}).get("command", "")
    except Exception:
        return
    if not cmd:
        return

    try:
        all_v = [classify_segment(t) for t in segments(cmd)]
    except ValueError:
        return  # unbalanced quotes → can't parse safely → defer
    verdicts = [v for v in all_v if v != _SKIP]

    # Defer when no git segment is present (pipe-only or non-git commands).
    if all(v in {_PIPE_SAFE, _UNSAFE} for v in verdicts):
        return

    for v in verdicts:
        if v in _DENY_MESSAGES:
            block(_DENY_MESSAGES[v])  # exits immediately

    if any(v == _GIT_ASK for v in verdicts):
        emit("ask", "Force-push rewrites remote history — confirm before proceeding.")
    if all(v in {_GIT_SAFE, _PIPE_SAFE} for v in verdicts):
        emit("allow", "Recognised safe git command.")


if __name__ == "__main__":
    main()
