# git-guard

A Claude Code plugin that enforces git policy for coding agents via a `PreToolUse`
hook. It is the single source of truth for what git commands an agent may run,
so the policy travels with the plugin instead of living in each repo's
`settings.json`.

> **Claude Code only.** The hook speaks Claude Code's `PreToolUse` protocol
> (`hookSpecificOutput` / `permissionDecision`) and has no Codex equivalent.

## Policy

For every `Bash` tool call, the hook tokenises the command (quote-aware) and
splits it on shell operators, then decides:

- **DENY** a push whose destination branch is `main` — whether via an explicit
  refspec (`origin main`, `HEAD:main`, `feature:main`) or a bare push / `git push
  <remote>` while the current branch is `main`.
- **DENY** any attempt to bypass git hooks (`--no-verify`, `git commit -n`).
- **ASK** before any force-push (it rewrites remote history).
- **ALLOW** recognised read/safe git commands, including normal feature-branch
  pushes — but only when *every* segment of the call is a vouched-for git
  command. Read-only pager/filter targets (`tail`, `head`, `grep`, `cat`, …) are
  allowlisted, so `git push … | tail` and `git log | grep x` still auto-approve.
- **DEFER** otherwise (unknown/dangerous git subcommand or a non-git segment),
  letting the normal permission prompt apply.

Deny and ask scan conservatively and win over allow. Denials hard-block via
**exit code 2**, which stops the call *before* `settings.json` permission rules
are evaluated — so a push to `main` is blocked even where a broad `Bash(git *)`
allow rule is configured. Ask and allow use a JSON `permissionDecision`.

## Layout

```
git-guard/
  .claude-plugin/plugin.json   # plugin manifest
  hooks/
    hooks.json                 # wires PreToolUse(Bash) → git-guard.py
    git-guard.py               # the guard
    test_git_guard.py          # test suite
```

## Tests

```bash
make test
```
