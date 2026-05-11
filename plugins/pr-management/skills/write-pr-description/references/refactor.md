# Example: refactor where the "why" is the entire point

Read this when the PR is a refactor, a file split, or any change that does not alter behaviour. The diff alone makes the refactor look mechanical, so the description has to carry the motivation, the boundary choices, and any subtle behaviour changes that slipped in.

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
