# Example PR descriptions

Three worked examples covering common PR shapes: a non-trivial bug fix, a one-line typo, and a refactor where "why" is the entire point. Each example contrasts a bad description (diff restatement, the failure mode this skill prevents) with a good one (reasoning the diff cannot show).

Examples use neutral framing ("X was considered, rejected because…") rather than first-person voice — a PR description should outlive any individual author and represent the team's reasoning.

## Example 1: Bug fix with non-obvious reasoning

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

## Example 2: Small fix where ceremony would be noise

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

## Example 3: Refactor where the "why" is the entire point

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
