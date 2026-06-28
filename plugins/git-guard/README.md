# git-guard

A Claude Code plugin that enforces git **and GitHub CLI (`gh`)** policy for
coding agents via two `PreToolUse(Bash)` hooks. It is the single source of truth
for what `git` and `gh` commands an agent may run, so the policy travels with the
plugin instead of living in each repo's `settings.json`.

> **Claude Code only.** The hooks speak Claude Code's `PreToolUse` protocol
> (`hookSpecificOutput` / `permissionDecision`) and have no Codex equivalent.

## git policy (`git-guard.py`)

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

## GitHub CLI policy (`gh-guard.py`)

A companion hook governs `gh` with an allow-or-ask policy (it never hard-blocks):

- **ALLOW** recognised read-only `gh` commands —
  `view`/`list`/`diff`/`status`/`checks`/`watch`/`download` across `pr`, `issue`,
  `run`, `workflow`, `repo`, `release`, …; every `gh search …`; and `gh api`
  GET/HEAD requests (so reading PR/issue comments and workflow state/results is
  friction-free) — plus the one vouched-for write, `gh pr create`.
- **ASK** for every other `gh` command — merges, closes, comments, edits,
  reviews, reruns, repo/secret/auth mutations, and `gh api` POST/PATCH/PUT/DELETE
  (a method flag or any `-f`/`-F` body field marks the request as a mutation).
- **DEFER** when no `gh` segment is present, so `git-guard` and the normal
  permission prompt own non-`gh` commands untouched.

Branch creation is intentionally **not** handled here — branches are made with
`git`, which `git-guard` already auto-approves. As with the git hook, the call is
tokenised quote-aware and split on shell operators; every segment must be an
allowed `gh` command (or a read-only pipe target like `jq`, `grep`, `tail`) for
the call to auto-approve, and an unrecognised `gh` segment downgrades it to
`ask`.

## Layout

```
git-guard/
  .claude-plugin/plugin.json   # plugin manifest
  hooks/
    hooks.json                 # wires PreToolUse(Bash) → git-guard.py + gh-guard.py
    git-guard.py               # the git guard
    gh-guard.py                # the GitHub CLI guard
    test_git_guard.py          # git guard test suite
    test_gh_guard.py           # gh guard test suite
```

## Tests

```bash
make test
```
