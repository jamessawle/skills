---
name: write-pr-description
description: Use this skill whenever someone asks to write, draft, generate, or produce a PR description, pull request body, or PR summary for a branch that does not yet have one. Focuses the description on the reasoning behind the change — the problem being solved, why this approach was chosen over alternatives, what trade-offs were accepted, and how to verify — rather than restating the diff. Gathers context from the linked issue or ticket, the branch's commit messages, and follow-up questions to the user when context is missing. Trigger for "write a PR description", "draft the PR body", "generate PR description", "PR summary", "describe this PR", "help me write the PR", or any request to produce description text for a pull request before it is opened. Do not trigger for reviewing an existing description, opening the PR itself, or summarising a merged PR.
license: MIT
compatibility: Requires git access to the branch being described. Optionally uses the GitHub CLI (gh) to fetch linked issue bodies when commit messages reference an issue.
allowed-tools: Bash
argument-hint: "[branch-name]"
metadata:
  author: jamessawle
  version: "1.0"
---

# Write PR Description

Produce a pull request description focused on the reasoning behind a change rather than a restatement of the diff.

## Arguments

- `$0` (optional) — Branch name to describe. Defaults to the current branch.

If no branch is supplied and the working directory is not a git repository (or HEAD is detached on a tag), stop and ask the user which branch to describe.

## The problem this skill solves

Agent-written PR descriptions tend to look like this:

> - Added `validateEmail` in `src/utils/validation.ts`
> - Updated `User.setEmail` to call it
> - Added unit tests
> - Updated docs

That is the diff in prose. A reviewer can see all of it in two clicks. None of it survives as useful context six months later when someone is trying to understand _why_ the code looks the way it does.

The value of a PR description is the reasoning that the diff cannot show on its own: the problem that motivated the change, the alternatives that were considered and rejected, the trade-offs that were accepted, and the things a reviewer should consciously check rather than skim past. Reach for that material first; only mention what changed when the file list alone does not make it obvious.

## Principles

1. **Every sentence should add something the diff cannot show.** If a sentence would still be true after `git revert`, it is probably restatement.
2. **Lead with the problem, not the solution.** Open with what was broken, missing, or risky. The reader should understand why this PR exists before they read what it does.
3. **Make trade-offs explicit.** Name the alternative you rejected and why. "I considered X but chose Y because Z" is far more useful than just describing Y.
4. **Write for the engineer six months from now**, not for the current reviewer. The current reviewer has the diff; the future reader has only the description and the merged code.
5. **Give the reviewer something concrete to verify.** Steps to reproduce, edge cases worth poking at, things that intentionally do _not_ change.
6. **Be honest about what is unfinished or risky.** Surface follow-up work, known gaps, and migration concerns rather than hiding them.
7. **Match length to substance.** A one-line typo fix gets a one-line description. A refactor with subtle trade-offs gets several paragraphs. Padding a small PR with ceremony is just noise.

## Workflow

### Step 1: Identify the branch and its base

Determine the branch to describe (`$0` or the current branch) and the base branch it will merge into. Default base order: explicit `--base` argument > `origin/HEAD` symbolic ref > `main` > `master`.

```bash
git rev-parse --abbrev-ref HEAD
git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null || true
```

If the branch has no commits beyond the base, stop and report that — there is nothing to describe.

### Step 2: Gather context from existing signals

Run these in parallel; they are independent.

**Commit messages on the branch** — the richest free source of reasoning, since whoever wrote the commits was actively explaining their own work.

```bash
git log --no-merges --format='%H%n%s%n%b%n---' <base>..<branch>
```

**Changed files (for scope, not content)** — used to size the description and spot whether the PR touches docs, tests, config, or production code. Avoid pasting the diff itself into the description.

```bash
git diff --stat <base>..<branch>
git diff --name-status <base>..<branch>
```

**Linked issues or tickets** — scan commit subjects, commit bodies, and the branch name for references like `#123`, `GH-123`, `closes #123`, `fixes JIRA-456`, `PROJ-789`. For each unique reference:

- GitHub-style (`#123`, `org/repo#123`): if `gh` is available, fetch with `gh issue view <number> [--repo <owner/repo>] --json title,body,labels,comments`.
- Jira-style (`PROJ-123`): note the reference for the user but do not attempt to fetch it unless they confirm a fetching mechanism is available.

### Step 3: Identify what is still missing

After gathering, mentally answer these questions:

1. **What problem motivated the change?** (the "why")
2. **Why this approach specifically?** What alternatives were considered?
3. **What trade-offs were accepted?** What could break, or got worse, in exchange for the win?
4. **How should a reviewer verify it works?**
5. **Is anything intentionally out of scope or deferred to follow-up?**

If commit messages and the linked issue answer a question, use that material directly. For any question that remains unanswered, decide whether the answer is _inferable from the diff with high confidence_ (e.g. a one-line null-check fix has an obvious "why") or whether you need to ask.

### Step 4: Ask the user only for what is genuinely missing

Ask the user to fill gaps — but only the gaps that materially change the description. Do not interrogate the user for a trivial PR. Typical questions, in priority order:

1. **The problem** — "What problem prompted this change? Was there a bug report, customer issue, or internal observation behind it?"
2. **Alternatives** — "Did you consider any other approaches before this one? If so, why did you rule them out?"
3. **Risk areas** — "What part of this PR are you least sure about — where would you most want a reviewer to push back?"
4. **Verification** — "How did you verify this works? Are there steps the reviewer should reproduce?"

Skip any question the existing context already answers. Group remaining questions into a single message rather than asking serially. Cap at three questions per round; if more context is needed, ask a second round after the first answers come back.

For very small PRs (single-line fix, dependency bump, docs typo) where the diff makes the reasoning obvious, skip this step entirely.

### Step 5: Draft the description

There is no required template. Use sections only when they carry weight. A typical structure for a medium-sized PR:

- A short opening paragraph (1–3 sentences) stating the problem and the chosen approach. No heading.
- `## Why` — fuller explanation of the motivation, including any linked issue context, when the opener cannot carry it alone.
- `## Approach` — why this design, what was rejected, and any non-obvious decisions.
- `## Trade-offs` or `## Notes` — anything that got worse, anything deferred, known limitations. Omit if there are none worth flagging.
- `## How to verify` — concrete reviewer actions: commands to run, scenarios to try, fixtures to inspect.

Drop or merge sections that would only contain one trivial line. Add others (e.g. `## Migration`, `## Rollout`, `## Screenshots`) when the change genuinely needs them. Do not invent ceremonial structure for its own sake.

If a linked issue exists, include a `Closes #N` (or equivalent) line at the bottom so the issue auto-closes on merge.

### Step 6: Self-check against the principles

Before presenting, re-read the draft and ask:

- Could any sentence be deleted without losing information that is not already in the diff? Delete it.
- Is every claim in the description actually supported by the commits or the user's answers? If not, mark it as an open question or remove it.
- Did you mention an alternative that was considered? If not, is that because there genuinely was no alternative, or because you skipped that part?
- Would a future engineer reading only this description understand why the code looks the way it does?

### Step 7: Present and iterate

Present the draft to the user as plain markdown text in the assistant message — do not write it to a file unless asked. Make clear that this is a draft for them to edit or push back on.

Do not open the PR or call `gh pr create` from this skill. This skill produces description text; opening the PR is a separate action the user takes (or asks for explicitly).

## Examples

Each example shows the PR description as raw markdown the user would paste into the PR body.

### Example 1: Bug fix with non-obvious reasoning

Branch context: five commits on `fix/email-validation`. Linked issue #523 ("Users registering with malformed emails break password reset"). Commit messages mention RFC 5322 and a deliberate choice not to use a library.

Bad description — diff restatement, the failure mode this skill prevents:

````markdown
## Changes

- Added `validateEmail` function in `src/utils/validation.ts`
- Updated `User.setEmail()` to call `validateEmail`
- Added unit tests covering valid and invalid email formats
- Updated the user model documentation

Closes #523.
````

Good description — reasoning the diff cannot show:

````markdown
Users have been able to register with addresses our mail provider cannot
deliver to (e.g. `foo@`, `@bar.com`), which silently breaks the password
reset flow. Issue #523 has 14 customer reports over the last quarter.

## Approach

Validation runs at the model boundary (`User.setEmail`) rather than only
in the registration form, because users are also created via the admin
API and the bulk CSV importer — fixing the form alone would have left
both untouched.

I considered `email-validator` and `validator.js` but both implement
RFC 5322, which is more permissive than our downstream provider accepts
(it rejects quoted local-parts and unicode TLDs that the RFC allows).
The provider's documented format is narrow enough that a 12-line regex
matches it exactly, and we already own the failure surface if the
provider changes the spec.

## Trade-offs

- 23 existing accounts have addresses that the new validator rejects.
  The migration in `db/migrations/0042_email_audit.sql` lists them;
  support has been notified and will reach out before the next deploy.
- The check runs synchronously inside `setEmail`. For the bulk importer
  this adds ~3s per 10k rows. Acceptable because imports are queued.

## How to verify

- Register with `foo@`, `@bar.com`, `foo@bar`, and `valid@example.com` —
  only the last should succeed.
- Run `npm run import -- --dry-run tests/fixtures/imports/mixed-validity.csv`
  and confirm the 4 invalid rows are flagged with the new error code.
- Existing tests in `User.spec.ts` still pass without modification.

Closes #523.
````

### Example 2: Small fix where ceremony would be noise

Branch context: one commit on `fix/typo-onboarding-copy`. No linked issue. Two-character change in a string.

Bad description — padded with empty structure:

````markdown
## Why

A typo was found in the onboarding copy.

## Approach

Fixed the typo by changing the misspelled word to the correct spelling.

## Trade-offs

None.

## How to verify

Read the onboarding screen.
````

Good description:

````markdown
Fixes a typo in the onboarding subtitle ("Welcom" → "Welcome"). No
behaviour change.
````

### Example 3: Refactor where the "why" is the entire point

Branch context: twelve commits on `refactor/split-billing-module`. No issue, but commit messages discuss a recurring deploy hazard.

Bad description:

````markdown
## Changes

- Split `billing.ts` into `billing/invoices.ts`, `billing/subscriptions.ts`,
  and `billing/credits.ts`
- Updated 47 imports across the codebase
- Moved tests to match the new structure
````

Good description:

````markdown
The single `billing.ts` file had grown to 2,400 lines covering three
loosely related concerns (invoicing, subscriptions, credit balances).
Three of the last five Sev-2 incidents in this codebase have involved
unrelated changes in one concern silently breaking another, because the
shared file is touched by every billing-adjacent PR and the test suite
for the file takes 90 seconds to run, which encourages skipping it
locally.

## Approach

Split along the same boundaries the team uses when triaging billing
bugs: invoicing, subscriptions, credits. Each new module owns its types,
queries, and tests. The public surface (`billing/index.ts`) re-exports
the previous API, so this is a zero-behaviour-change refactor — no
callers needed to update import paths beyond the imports that were
already touching internals (which arguably should not have been).

I considered splitting by transaction type vs. by domain concern, but
transaction type cuts across all three concerns and would have produced
modules that all three teams still need to touch.

## Notes

- The new test files run in parallel; the suite is down from 90s to 22s
  on CI.
- `billing/index.ts` is intentionally a re-export shim. Once downstream
  teams have migrated their internal imports (tracked in #1041) we can
  delete it.
- One genuine behaviour change snuck in: `getCreditBalance` used to
  swallow errors and return 0, which I have changed to surface them.
  Caller sites in `dashboard/` and `admin/` already handle the error
  case, so this is safe, but flagging it explicitly because it is not
  pure code-movement.

## How to verify

- `npm test billing/` should pass — same assertions as before, organised
  by module.
- Diff `billing/index.ts` against the previous `billing.ts` exports to
  confirm no exported symbol was dropped.
````

## Important guidelines

- **Reasoning first, restatement last.** Restatement of the diff is the failure mode this skill exists to prevent. Reach for "why" and "trade-offs" before reaching for "what changed".
- **Do not invent context.** If the commits and the linked issue do not explain why an approach was chosen, ask the user. Do not guess motivations or fabricate alternatives that "sound plausible".
- **Match length to substance.** A one-line fix gets a one-line description. Padding with empty `## Trade-offs: None` sections trains readers to skim past the structure when it _does_ carry weight.
- **Do not open the PR.** This skill produces description text only. The user (or a separate skill) opens the PR.
- **Do not edit commits or push.** Reading the branch is enough; never run `git commit`, `git push`, or `git rebase` from this skill.
- **Treat issue bodies as input, not as the final description.** Issue bodies describe the problem; PR descriptions explain the resolution. Copying the issue body verbatim misses the point.
