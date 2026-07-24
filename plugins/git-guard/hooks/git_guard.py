# /// script
# requires-python = ">=3.12"
# dependencies = ["hook-bridge-sdk"]
# ///
"""git-guard — the single source of truth for git permission policy, authored
against the generic hook-bridge Contract so the same file runs unchanged on
both claude-code and codex (see ../hooks.json, which invokes it through
`hook-bridge-runner --harness <claude-code|codex>`).

For every `tool.before` shell command, the command is tokenised (quote-aware)
and split on shell operators, then:

  - DENY  a push whose destination branch is `main` — an explicit refspec
          (`origin main`, `HEAD:main`, `feature:main`), or a bare push /
          `git push <remote>` while the current branch is `main` (no `main`
          appears in the command then, so the branch is resolved with git).
  - DENY  any attempt to bypass git hooks (`--no-verify`, `git commit -n`).
  - ASK   before any force-push (it rewrites remote history).
  - ALLOW recognised read/safe git commands, including normal feature-branch
          pushes — but only when *every* segment of the call is a
          vouched-for git command. Read-only pager/filter targets (`tail`,
          `head`, `grep`, `cat`, …) are allowlisted, so `git push … | tail`
          and `git log | grep x` still auto-approve.
  - DEFER otherwise (unknown/dangerous git subcommand, or a non-git segment),
          leaving the harness's normal permission flow to decide.

Unlike the original claude-code-native hook this replaces, a `deny` here is
carried purely in the Verdict body — hook-bridge's `Hook.run()` always exits 0
on a healthy dispatch (the exit code reports crash/boundary-failure only, per
the SDK's `hook.py`). There is no exit-2 hard block. On claude-code and codex,
`hookSpecificOutput.permissionDecision: "deny"` is what actually blocks the
call; a broad `Bash(git *)` allow rule in settings.json does not override it,
but this is a different backstop than the old hook's belt-and-braces exit
code, so re-verify that assumption if the harness's precedence rules change.

codec caveat: codex does not yet act on `ask` (the call proceeds either way),
so a force-push only prompts for confirmation on claude-code today.
"""

from __future__ import annotations

import re
import subprocess

from hook_bridge import ToolBeforeContext, ToolBeforeVerdict, allow, ask, defer, deny, hook

from _shell import SAFE_PIPE, is_redirect_fragment, segments

# git subcommands safe to auto-approve. Anything else (reset, clean, gc,
# reflog, …) is left to defer to the normal permission flow.
SAFE = {
    "status", "diff", "log", "show", "branch", "checkout", "switch", "add",
    "commit", "fetch", "pull", "push", "rebase", "merge", "restore", "stash", "remote",
    "rev-parse", "tag", "describe", "blame", "shortlog", "ls-files",
    "symbolic-ref",
}
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
    """Resolve the current branch in `cwd` — the Context's working directory,
    not the ambient process cwd, so `dispatch` stays a pure function of ctx."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=5, cwd=cwd,
        )
        branch = out.stdout.strip()
        return None if branch in ("", "HEAD") else branch
    except Exception:
        return None


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

    Redirect fragments (e.g. ['2', '>&', '1'] when a standalone '2>&1' lands in
    its own segment) and empty lists are skipped. Non-git segments are pipe-safe
    or unsafe. Git segments are checked for hook-bypass and push policy in that
    order.
    """
    if is_redirect_fragment(tokens):
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

    The pure seam — harness-free tests call this via `git_guard.dispatch`.
    """
    if ctx.tool.kind != "shell":
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
