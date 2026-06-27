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
# Read-only pager/filter tools that are harmless as pipe targets, so a git
# command piped through them (`git log | grep x`, `git push … | tail`) can still
# be vouched for. Deliberately excludes anything that writes or executes (tee,
# xargs, sed, awk, …) — those still downgrade the call to a prompt.
SAFE_PIPE = {
    "cat", "head", "tail", "less", "more", "grep", "egrep", "fgrep", "wc",
    "sort", "uniq", "nl", "cut", "tr", "rev", "column",
}
OPERATORS = {"&&", "||", "|", "|&", ";", "&", "(", ")"}
SHORT_NO_VERIFY = re.compile(r"-[A-Za-z]*n[A-Za-z]*")  # -n, -nm, -vn, … (commit)
# Matches --force, --force-with-lease[=...], and combined short flags containing f (-fu, -uf, …).
_FORCE_FLAG_RE = re.compile(r"^(?:--force|--force-with-lease(?:=.*)?|-[A-Za-z]*f[A-Za-z]*)$")


def emit(decision, reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }}))
    sys.exit(0)


def block(reason):
    """Hard-block the call: exit 2 stops it before permission rules apply, so it
    beats even a broad allow rule. The reason goes to stderr for Claude Code."""
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
    """Quote-aware split into command segments (lists of tokens)."""
    lexer = shlex.shlex(cmd, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    out, cur = [], []
    for tok in lexer:  # may raise ValueError on unbalanced quotes
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
    """`args` are the tokens after `git push`. Returns deny|ask|safe."""
    force = False
    positionals = []
    for tok in args:
        if _FORCE_FLAG_RE.match(tok):
            force = True
        elif tok.startswith("-"):
            continue
        else:
            positionals.append(tok)
    refspecs = positionals[1:]  # first positional is the remote
    targets = []
    if not refspecs:
        targets.append(current_branch())  # bare push → current branch
    else:
        for spec in refspecs:
            if spec.startswith("+"):  # +refspec forces that ref
                force, spec = True, spec[1:]
            dest = spec.split(":")[-1] if ":" in spec else spec
            targets.append(current_branch() if dest == "HEAD" else dest)
    if any(t is None for t in targets):
        return "ask"  # can't determine branch → safer to prompt
    if any(t == "main" for t in targets):
        return "deny"
    return "ask" if force else "safe"


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
        segs = segments(cmd)
    except ValueError:
        return  # can't parse safely → defer to the normal prompt

    has_ask = False
    all_safe = True
    saw_git = False

    for tokens in segs:
        # Skip I/O-redirect fragments produced when 2>&1 is split on the '&'
        # operator (e.g. 'cmd 2>&1 | tail' creates a lone ['1'] segment between
        # the & and the |). These are not commands and must not clear all_safe.
        if tokens and all(t.isdigit() or t in (">", "<", ">>", "<<") for t in tokens):
            continue
        if not tokens or tokens[0] != "git":
            if not tokens or tokens[0] not in SAFE_PIPE:
                all_safe = False  # non-git segment: can't vouch for the whole call
            continue  # harmless pager/filter: doesn't block, but can't vouch alone
        saw_git = True
        sub = tokens[1] if len(tokens) > 1 else ""
        args = tokens[2:]

        # Bypassing git hooks is never allowed, whatever the subcommand.
        # Check tokens[1:] (not just args) so 'git --no-verify push' is also caught.
        if "--no-verify" in tokens[1:] or (
            sub == "commit" and any(SHORT_NO_VERIFY.fullmatch(a) for a in args)
        ):
            block("Bypassing git hooks (--no-verify) is not allowed.")

        if sub == "push":
            verdict = push_verdict(args)
            if verdict == "deny":
                block("Pushes to main are not allowed — use a feature branch and open a PR.")
            elif verdict == "ask":
                has_ask = True
        elif sub not in SAFE:
            all_safe = False  # unknown/dangerous git subcommand → defer

    if not saw_git:
        return
    if has_ask:
        emit("ask", "Force-push rewrites remote history — confirm before proceeding.")
    if all_safe:
        emit("allow", "Recognised safe git command.")


if __name__ == "__main__":
    main()
