# git-guard

A plugin that enforces git **and GitHub CLI (`gh`)** policy for coding agents
via two `PreToolUse(Bash)` hooks. It is the single source of truth for what
`git` and `gh` commands an agent may run, so the policy travels with the
plugin instead of living in each repo's `settings.json`.

## git policy (`git_guard.py`)

`git_guard.py` is authored against the generic
[hook-bridge](https://github.com/jamessawle/hook-bridge) Contract and invoked
through `hook-bridge-runner`, so the same file enforces policy on **both
claude-code and codex** — see [Prerequisites](#prerequisites) and
[Wiring into codex](#wiring-into-codex).

`gh_guard.py` (below) is ported onto the same Contract, so both hooks share
identical claude-code/codex parity and wiring.

For every shell tool call, the hook tokenises the command (quote-aware) and
splits it on shell operators, then decides:

- **DENY** a push whose destination branch is `main` — whether via an explicit
  refspec (`origin main`, `HEAD:main`, `feature:main`) or a bare push / `git push
  <remote>` while the current branch is `main`.
- **DENY** a `git commit` while the current branch is `main` — catches the
  problem before an agent strands work it can never push, rather than only at
  the eventual `git push`.
- **DENY** any attempt to bypass git hooks (`--no-verify`, `git commit -n`).
- **ASK** before any force-push (it rewrites remote history).
- **ALLOW** recognised read/safe git commands, including normal feature-branch
  pushes — but only when *every* segment of the call is a vouched-for git
  command. Read-only pager/filter targets (`tail`, `head`, `grep`, `cat`, …) are
  allowlisted, so `git push … | tail` and `git log | grep x` still auto-approve.
- **DEFER** otherwise (unknown/dangerous git subcommand or a non-git segment),
  letting the normal permission prompt apply.

Deny and ask scan conservatively and win over allow. All four outcomes are
carried in the Verdict body that `hook-bridge-runner` translates into each
harness's native `hookSpecificOutput.permissionDecision` — there is no
exit-code hard block (hook-bridge's `Hook.run()` always exits 0 on a healthy
dispatch; the exit code reports crash/boundary-failure only, never the
decision). This differs from a plain claude-code hook, which can additionally
force a block via exit code 2 ahead of `settings.json` rule evaluation;
`permissionDecision: "deny"` is the only backstop here, so don't rely on a
broad `Bash(git *)` allow rule being overridden unless you've re-verified that
precedence on the harness version you're running.

`ask` is also not acted on identically everywhere: codex parses it but does
not yet gate the call on it (confirmed against codex-cli), so a force-push
only actually prompts for confirmation on claude-code today.

## GitHub CLI policy (`gh_guard.py`)

Like `git_guard.py`, this hook is authored against the hook-bridge Contract
and invoked through `hook-bridge-runner`, so it also enforces policy on
**both claude-code and codex**.

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

## Prerequisites

Both `git_guard.py` and `gh_guard.py` are
[hook-bridge](https://github.com/jamessawle/hook-bridge) Hooks, not plain
scripts — `hooks.json` invokes each via `hook-bridge-runner`, which in turn
runs them with `uv run` (each file declares its own `hook-bridge-sdk`
dependency inline via PEP 723, so there's no separate install step for the
Hooks themselves). Both must be on `PATH`:

Both hooks run unconditionally on every Bash call — `hooks.json` deliberately
has no per-hook `if` filter (e.g. `if: "Bash(git *)"`). That looks like a free
win (skip the `hook-bridge-runner` spawn on unrelated calls like `ls`/`npm
test`), but per [anthropics/claude-code#77037](https://github.com/anthropics/claude-code/issues/77037)
the `if` matcher can silently never fire for compound commands (`cmd1 && git
commit`) even though the docs say it should — which would mask the guard
entirely for exactly the commands it most needs to catch. `test_hooks_json.py`
guards against reintroducing it. Each script instead does its own cheap
pre-filter (`_MENTIONS_GIT` / `_MENTIONS_GH`, a `\bgit\b`/`\bgh\b` check on the
raw command) before tokenising, which gets most of the same performance win
without depending on that harness behaviour.

```bash
brew install jamessawle/tap/hook-bridge-runner   # also pulls in uv
```

## Wiring into codex

Installing this plugin only wires the hooks into claude-code (via
`hooks.json`); codex has no plugin-level hook installation, so wiring them in
there is a manual step in `.codex/config.toml` (or `~/.codex/config.toml`):

```toml
[[hooks.PreToolUse]]
matcher = "^Bash$"

[[hooks.PreToolUse.hooks]]
type = "command"
command = "hook-bridge-runner --harness codex /path/to/plugins/git-guard/hooks/git_guard.py"

[[hooks.PreToolUse.hooks]]
type = "command"
command = "hook-bridge-runner --harness codex /path/to/plugins/git-guard/hooks/gh_guard.py"
```

Codex also gates hook execution behind trust review (`/hooks`) and the
`[features] hooks = true` flag.

## Layout

```
git-guard/
  .claude-plugin/plugin.json   # plugin manifest
  hooks/
    hooks.json                 # wires PreToolUse(Bash) → git_guard.py + gh_guard.py (via hook-bridge-runner)
    git_guard.py               # the git guard, a hook-bridge Hook (runs on claude-code + codex)
    gh_guard.py                # the GitHub CLI guard, a hook-bridge Hook (runs on claude-code + codex)
    _shell.py                  # tokeniser + pipe-target allowlist shared by both guards
    test_git_guard.py          # git guard test suite (harness-free, via hook-bridge-sdk)
    test_gh_guard.py           # gh guard test suite (harness-free, via hook-bridge-sdk)
```

## Tests

```bash
make test
```
