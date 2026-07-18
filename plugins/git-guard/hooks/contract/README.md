# git-guard, ported to the hook-bridge Contract (preview)

This directory holds a **preview** of `git-guard` rewritten against the
[hook-bridge](https://github.com/jamessawle/hook-bridge) generic Contract. It is
kept **alongside** the working hook (`../git-guard.py`), which is untouched — this
is not yet wired into the plugin.

## What changed vs `../git-guard.py`

- Reads `ctx.tool.command` (generic Context) instead of parsing stdin JSON, and
  returns a `Verdict` (`allow` / `deny` / `ask` / `defer`) instead of writing
  claude-code-native JSON and exit codes. **All the classification logic —
  `shlex` tokenising, flag-abbreviation matching, the `git` branch shell-out — is
  unchanged.** Only the read and the return are Contract-shaped.
- Resolves the current branch in `ctx.cwd` (carried by the Context) rather than
  the ambient process cwd, so `dispatch` is a pure function of its Context.
- Drops the Python 3.7 version guard (hook-bridge is 3.12+).
- The four native outcomes map 1:1 onto the Contract's four `tool.before` verbs
  (deny/ask/allow/defer) — see hook-bridge
  [ADR-0002](https://github.com/jamessawle/hook-bridge/blob/main/docs/adr/0002-tool-before-verdict-verbs.md).

## Blocked on

This preview is **not runnable yet**. It needs hook-bridge v1 to ship:

1. **`hook-bridge-sdk` published** — `git_guard.py` and `test_git_guard.py`
   `import hook_bridge`, and the PEP 723 header declares `hook-bridge-sdk`.
2. **The runner + claude-code Adapter + CLI** — a Contract-based hook is invoked
   as `hook-bridge --harness claude-code .../git_guard.py` over the generic wire,
   not directly by claude-code. Until that exists, `hooks.json` cannot be pointed
   at this file, so the plugin keeps using `../git-guard.py`.

## Testing

Once `hook-bridge-sdk` is installed, `test_git_guard.py` runs harness-free —
in-process, no subprocess, through the real Contract types:

```python
git_guard.dispatch(tool_before(shell("git push --force origin main")))  # -> deny
```

The suite mirrors `../test_git_guard.py` case-for-case, asserting on Verdicts
(`.is_allow` / `.is_deny` / `.is_ask` / `.is_defer`) instead of exit codes.
