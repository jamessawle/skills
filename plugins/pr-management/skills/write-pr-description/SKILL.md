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

If no branch is supplied and the working directory is not a git repository, stop and ask which branch to describe.

## Principles

1. **Reasoning over restatement.** Every sentence should add something the diff cannot show. If a sentence would still be true after `git revert`, delete it.
2. **Lead with the problem.** The reader should understand why the PR exists before they read what it does.
3. **Make trade-offs explicit.** Name the alternative rejected and why. "Considered X, chose Y because Z" is more useful than describing Y alone.
4. **Write for the future reader.** Not the current reviewer (who has the diff), but someone hunting for context six months later.
5. **Be honest about risk.** Surface follow-up work, known gaps, and migration concerns; give the reviewer something concrete to verify.
6. **Match length to substance.** A one-line fix gets a one-line description. Padding small PRs with ceremonial sections trains readers to skim past structure when it matters.

## Workflow

### Step 1: Identify the branch and its base

Determine the branch (`$0` or current) and base. Default base order: `origin/HEAD` symbolic ref > `main` > `master`.

```bash
git rev-parse --abbrev-ref HEAD
git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null || true
```

If the branch has no commits beyond the base, stop and report that.

### Step 2: Gather context

Run these in parallel; they are independent.

**Commit messages** — the richest free source of reasoning:

```bash
git log --no-merges --format='%H%n%s%n%b%n---' <base>..<branch>
```

**Changed files for scope** (not content — do not paste the diff into the description):

```bash
git diff --stat <base>..<branch>
git diff --name-status <base>..<branch>
```

**Linked issues** — scan commit subjects, bodies, and the branch name for references like `#123`, `closes #123`, `PROJ-789`. For GitHub-style references, fetch with `gh issue view <number> [--repo <owner/repo>] --json title,body,labels` if `gh` is available. For Jira-style references, note them for the user but do not attempt to fetch.

Treat issue bodies as input, not as the final description. Issue bodies describe the problem; PR descriptions explain the resolution.

### Step 3: Identify gaps

Mentally answer:

1. What problem motivated the change?
2. Why this approach? What alternatives were considered?
3. What trade-offs were accepted?
4. How should a reviewer verify it works?
5. Is anything intentionally deferred?

If commits and the linked issue answer a question, use that material. For any question that remains unanswered, decide whether the answer is inferable from the diff with high confidence (e.g. a one-line null-check fix has an obvious "why") or whether to ask.

### Step 4: Ask only for genuinely missing context

Skip questions the existing context already answers. Group remaining questions into a single message rather than asking serially. Cap at three per round. For single-line fixes, dependency bumps, or docs typos, skip this step entirely.

Typical questions, in priority order:

1. **The problem** — what prompted this change?
2. **Alternatives** — what other approaches were considered, and why ruled out?
3. **Risk areas** — where would the author most want a reviewer to push back?
4. **Verification** — how was this tested?

### Step 5: Draft

There is no required template. Use sections only when they carry weight. A typical medium-sized PR uses:

- An opening paragraph (1–3 sentences) stating the problem and chosen approach, with no heading.
- `## Why`, `## Approach`, `## Trade-offs` or `## Notes`, `## How to verify` — included only when each has something substantive to say. Drop any section that would only contain a trivial line.

If a linked issue exists, end with `Closes #N` so the issue auto-closes on merge.

### Step 6: Present

Present the draft as plain markdown text in the assistant message — do not write it to a file unless asked. Do not open the PR. This skill produces description text only; opening the PR is a separate action.

## Examples

Each example shows the PR description as raw markdown the user would paste into the PR body. Examples use neutral framing ("X was considered", "Y was rejected") rather than first-person voice.

### Example 1: Bug fix with non-obvious reasoning

Branch context: five commits on `fix/email-validation`. Linked issue #523 ("Users registering with malformed emails break password reset"). Commit messages mention RFC 5322 and a deliberate choice not to use a library.

Bad — diff restatement:

````markdown
## Changes

- Added `validateEmail` function in `src/utils/validation.ts`
- Updated `User.setEmail()` to call `validateEmail`
- Added unit tests covering valid and invalid email formats
- Updated the user model documentation

Closes #523.
````

Good — reasoning the diff cannot show:

````markdown
Users have been able to register with addresses the mail provider cannot
deliver to (e.g. `foo@`, `@bar.com`), which silently breaks the password
reset flow. Issue #523 has 14 customer reports over the last quarter.

## Approach

Validation runs at the model boundary (`User.setEmail`) rather than only
in the registration form, because users are also created via the admin
API and the bulk CSV importer — fixing the form alone would have left
both untouched.

Two RFC 5322 libraries (`email-validator` and `validator.js`) were
considered but rejected: both are more permissive than the downstream
mail provider accepts (it rejects quoted local-parts and unicode TLDs
that the RFC allows). The provider's documented format is narrow enough
that a 12-line regex matches it exactly.

## Trade-offs

- 23 existing accounts have addresses the new validator rejects. The
  migration in `db/migrations/0042_email_audit.sql` lists them; support
  has been notified.
- The check runs synchronously inside `setEmail`. For the bulk importer
  this adds ~3s per 10k rows. Acceptable because imports are queued.

## How to verify

- Register with `foo@`, `@bar.com`, `foo@bar`, and `valid@example.com` —
  only the last should succeed.
- Run `npm run import -- --dry-run tests/fixtures/imports/mixed-validity.csv`
  and confirm the 4 invalid rows are flagged with the new error code.

Closes #523.
````

### Example 2: Small fix where ceremony would be noise

Branch context: one commit on `fix/typo-onboarding-copy`. No linked issue.

Bad — padded with empty structure:

````markdown
## Why

A typo was found in the onboarding copy.

## Approach

Fixed the typo by changing the misspelled word to the correct spelling.

## Trade-offs

None.
````

Good:

````markdown
Fixes a typo in the onboarding subtitle ("Welcom" → "Welcome"). No
behaviour change.
````

### Example 3: Refactor where the "why" is the entire point

Branch context: twelve commits on `refactor/split-billing-module`. No issue, but commit messages discuss a recurring deploy hazard.

Bad:

````markdown
## Changes

- Split `billing.ts` into `billing/invoices.ts`, `billing/subscriptions.ts`,
  and `billing/credits.ts`
- Updated 47 imports across the codebase
````

Good:

````markdown
The single `billing.ts` file had grown to 2,400 lines covering three
loosely related concerns (invoicing, subscriptions, credit balances).
Three of the last five Sev-2 incidents in this codebase have involved
unrelated changes in one concern silently breaking another, because the
shared file is touched by every billing-adjacent PR.

## Approach

Split along the boundaries the team uses when triaging billing bugs.
Each new module owns its types, queries, and tests. The public surface
(`billing/index.ts`) re-exports the previous API, so callers do not
need to update import paths.

Splitting by transaction type was considered but rejected: transaction
type cuts across all three concerns and would have produced modules
every team still needs to touch.

## Notes

- Test suite is down from 90s to 22s on CI now that the files run in
  parallel.
- `billing/index.ts` is intentionally a re-export shim. Once downstream
  teams migrate their internal imports (tracked in #1041) it can be
  deleted.
- One genuine behaviour change is included: `getCreditBalance` used to
  swallow errors and return 0; it now surfaces them. Caller sites in
  `dashboard/` and `admin/` already handle the error case, but flagging
  it explicitly because this is not pure code-movement.
````
