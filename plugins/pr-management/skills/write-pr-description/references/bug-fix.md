# Example: bug fix with non-obvious reasoning

Read this when the PR fixes a bug and the choice of fix (where to validate, which library to use, what scope to take) is not obvious from the diff.

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
