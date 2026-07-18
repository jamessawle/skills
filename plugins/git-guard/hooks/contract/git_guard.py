# /// script
# requires-python = ">=3.12"
# dependencies = ["hook-bridge-sdk"]
# ///
"""git-guard — the single source of truth for git permission policy, authored
against the generic hook-bridge Contract.

PREVIEW / not yet wired. This is the Contract-ported form of ../git-guard.py,
kept alongside the working hook. It runs through hook-bridge rather than being
invoked directly by claude-code, so it is blocked on hook-bridge v1 shipping
(SDK publish + runner + claude-code Adapter). See README.md in this directory.

The Hook is harness-ignorant: it reads `ctx.tool.command` and returns a
`Verdict`, with zero knowledge of which Harness invoked it. hook-bridge adapts
each harness's native protocol to and from this Contract.

Policy (mapped onto the v1 `tool.before` Verdict verbs):

  - DENY  a push whose destination branch is `main` — an explicit refspec
          (`origin main`, `HEAD:main`, `feature:main`), or a bare push /
          `git push <remote>` while the current branch is `main` (no `main`
          appears in the command then, so the branch is resolved with git).
  - DENY  any attempt to bypass git hooks (`--no-verify`, `git commit -n`).
  - ASK   before any force-push (rewrites remote history).
  - ALLOW recognised read/safe git commands, including normal feature pushes.
  - DEFER otherwise: express no opinion so the harness's normal permission flow
          applies.

A hook `allow` auto-approves the whole call, so the command is tokenised with
shlex (quote-aware) and split on shell operators; every segment must be a
vouched-for git command before the call is auto-allowed. A dangerous part (e.g.
`git reset --hard`) or any non-git segment downgrades the call to `defer`;
deny/ask scan conservatively and win over allow. Using a real tokeniser means a
commit message that merely *mentions* `--no-verify` is not mistaken for the flag.

Read-only pager/filter tools (tail, head, grep, …) are allowlisted as harmless
pipe targets, so the everyday `git push … | tail` and `git log | grep x` still
auto-approve rather than downgrading to defer. At least one git segment must be
present — a call with no git command is always deferred.
"""

from __future__ import annotations

import re
import shlex
import subprocess

from hook_bridge import (
    ToolBeforeContext,
    ToolBeforeVerdict,
    allow,
    ask,
    defer,
    deny,
    hook,
)

# git subcommands safe to auto-approve. Anything else (reset, clean, gc,
# reflog, …) is left to defer to the normal permission flow.
SAFE = {
    "status", "diff", "log", "show", "branch", "checkout", "switch", "add",
    "commit", "fetch", "pull", "push", "rebase", "merge", "restore", "stash", "remote",
    "rev-parse", "tag", "describe", "blame", "shortlog", "ls-files",
    "symbolic-ref",
}
# Read-only pager/filter tools harmless as pipe targets. Excludes anything that
# writes or executes (tee, xargs, sed, awk, …) — those still downgrade to defer.
SAFE_PIPE = {
    "cat", "head", "tail", "less", "more", "grep", "egrep", "fgrep", "wc",
    "sort", "uniq", "nl", "cut", "tr", "rev", "column",
}
OPERATORS = {"&&", "||", "|", "|&", ";", "&", "(", ")"}
SHORT_NO_VERIFY = re.compile(r"-[A-Za-z]*n[A-Za-z]*")  # -n, -nm, -vn, … (commit only)
SHORT_FORCE = re.compile(r"-[A-Za-z]*f[A-Za-z]*")  # -f, -fu, -uf, … (combined short)

# git's parse-options API accepts any *unambiguous prefix* of a long option, so
# `--no-veri` runs as `--no-verify` and `--force-with-leas` as `--force-with-lease`.
# Matching only the fully-spelled flag lets an abbreviation slip the guard — and
# since hook-bypass is a hard deny, a miss auto-allows the bypass. We therefore
# treat any prefix of the full flag at least min-length chars long as the flag.
# Shorter prefixes are ambiguous and rejected by git itself (`--no-ver` collides
# with `--no-verbose`, `--forc` with `--force`/`--force-with-lease`), so erring
# toward a match here only ever denies commands git would reject anyway.
_NO_VERIFY = "--no-verify"
_NO_VERIFY_MIN = len("--no-veri")  # shorter is ambiguous with --no-verbose
_FORCE_WITH_LEASE = "--force-with-lease"  # covers bare --force (its prefix) too
_FORCE_MIN = len("--force")  # shorter is ambiguous


def _is_long_abbrev(token: str, full: str, min_len: int) -> bool:
    """True if token is a git-accepted (or git-rejected-ambiguous) prefix of a
    long flag — i.e. a prefix of `full` no shorter than `min_len`."""
    return len(token) >= min_len and full.startswith(token)


def _is_no_verify(token: str) -> bool:
    return _is_long_abbrev(token, _NO_VERIFY, _NO_VERIFY_MIN)


def _is_force(token: str) -> bool:
    if SHORT_FORCE.fullmatch(token):  # combined short flag: -f, -fu, …
        return True
    head = token.split("=", 1)[0]  # --force-with-lease=<value>
    return _is_long_abbrev(head, _FORCE_WITH_LEASE, _FORCE_MIN)


# Verdict strings returned by classify_segment().
_GIT_SAFE = "git-safe"  # vetted git command
_GIT_ASK = "git-ask"  # needs force-push confirmation
_PIPE_SAFE = "pipe-safe"  # read-only filter; harmless but doesn't vouch alone
_UNSAFE = "unsafe"  # unrecognised/dangerous; downgrades to defer
_SKIP = "skip"  # redirect fragment or empty; ignored
_DENY_HOOKS = "deny:hooks"  # hook bypass — hard-block
_DENY_MAIN = "deny:main"  # push to main — hard-block

_DENY_MESSAGES = {
    _DENY_HOOKS: "Bypassing git hooks (--no-verify) is not allowed.",
    _DENY_MAIN: "Pushes to main are not allowed — use a feature branch and open a PR.",
}


def current_branch(cwd: str) -> str | None:
    """Resolve the current branch in `cwd` — the working directory the Context
    carries. Resolving in `ctx.cwd` (not the ambient process cwd) keeps dispatch
    a pure function of its Context: no `os.chdir` needed to test push policy."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
        branch = out.stdout.strip()
        return None if branch in ("", "HEAD") else branch
    except Exception:
        return None


def segments(cmd: str) -> list[list[str]]:
    """Quote-aware split into command segments (lists of tokens).
    Raises ValueError on unbalanced quotes."""
    lexer = shlex.shlex(cmd, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    out: list[list[str]] = []
    cur: list[str] = []
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


def push_verdict(args: list[str], cwd: str) -> str:
    """Analyse `git push` args. Returns "deny" | "ask" | "safe"."""
    force = False
    positionals: list[str] = []
    for tok in args:
        if _is_force(tok):
            force = True
        elif not tok.startswith("-"):
            positionals.append(tok)
    refspecs = positionals[1:]  # first positional is the remote
    targets: list[str | None] = []
    if not refspecs:
        targets.append(current_branch(cwd))  # bare push → resolve current branch
    else:
        for spec in refspecs:
            if spec.startswith("+"):  # +refspec is a force push
                force, spec = True, spec[1:]
            dest = spec.split(":")[-1] if ":" in spec else spec
            targets.append(current_branch(cwd) if dest == "HEAD" else dest)
    if any(t is None for t in targets):
        return "ask"  # can't resolve branch (detached HEAD or git error) → prompt
    if any(t == "main" for t in targets):
        return "deny"
    return "ask" if force else "safe"


def classify_segment(tokens: list[str], cwd: str) -> str:
    """Classify one command segment and return a verdict string.

    Redirect fragments (e.g. lone ['1'] from splitting '2>&1' on '&') and empty
    lists are skipped. Non-git segments are pipe-safe or unsafe. Git segments are
    checked for hook-bypass and push policy in that order.
    """
    if not tokens or all(t.isdigit() or t in (">", "<", ">>", "<<") for t in tokens):
        return _SKIP
    if tokens[0] != "git":
        return _PIPE_SAFE if tokens[0] in SAFE_PIPE else _UNSAFE

    sub = tokens[1] if len(tokens) > 1 else ""
    args = tokens[2:]

    if any(_is_no_verify(t) for t in tokens[1:]) or (
        sub == "commit" and any(SHORT_NO_VERIFY.fullmatch(a) for a in args)
    ):
        return _DENY_HOOKS

    if sub == "push":
        verdict = push_verdict(args, cwd)
        if verdict == "deny":
            return _DENY_MAIN
        return _GIT_ASK if verdict == "ask" else _GIT_SAFE

    return _GIT_SAFE if sub in SAFE else _UNSAFE


@hook
def git_guard(ctx: ToolBeforeContext) -> ToolBeforeVerdict:
    """Apply the git policy to a `tool.before` event, returning a Verdict.

    This is the pure seam: harness-free tests call it via `git_guard.dispatch`.
    The classification logic is unchanged from the original; only the read (from
    the generic Context) and return (a generic Verdict) are Contract-shaped.
    """
    # Forward-compatible discriminator guard: git-guard only vouches for shell
    # commands. When the Contract grows more tool kinds, this filters them out.
    if ctx.tool.kind != "shell":  # pyright: ignore[reportUnnecessaryComparison]
        return defer()
    command = ctx.tool.command
    if not command:
        return defer()

    try:
        classified = [classify_segment(t, ctx.cwd) for t in segments(command)]
    except ValueError:
        return defer()  # unbalanced quotes → can't parse safely → no opinion
    verdicts = [v for v in classified if v != _SKIP]

    # Defer when no git segment is present (pipe-only or non-git commands).
    if all(v in (_PIPE_SAFE, _UNSAFE) for v in verdicts):
        return defer()

    # Hard blocks win: deny scans conservatively and beats ask/allow.
    for v in verdicts:
        if v in _DENY_MESSAGES:
            return deny(_DENY_MESSAGES[v])

    if any(v == _GIT_ASK for v in verdicts):
        return ask("Force-push rewrites remote history — confirm before proceeding.")

    if all(v in (_GIT_SAFE, _PIPE_SAFE) for v in verdicts):
        return allow()

    return defer()


if __name__ == "__main__":  # runnable as a subprocess AND importable in tests
    git_guard.run()
