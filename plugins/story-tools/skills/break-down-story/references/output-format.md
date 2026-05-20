# Breakdown output format

The source of truth for the markdown shape `break-down-story` emits. Read this file before synthesising in Step 3.

## Top-level shape

```
# Breakdown of <KEY>: <summary>

## Slicing rationale
<2-4 sentences: how you sliced the story and why — by user journey, by layer
of the stack, by AC grouping, etc. — and what "releasable" means for each
slice (user-visible vs. behind a named flag).>

## Slice 1

**Summary:** <one-line ticket title>

**Description:**
<Jira-style prose, 2-5 sentences. Name the outcome explicitly: either the
user-visible change, or the named feature flag the work hides behind.>

**Acceptance Criteria:**
- <verbatim AC from parent>
- <verbatim AC from parent>

---

_Reviewer notes (not part of the ticket):_
- **Size:** S | M | L
- **Code areas:** <bullet list of files/modules from the codebase brief>
- **Depends on:** none | Slice N

## Slice 2

…
```

The ticket-shaped portion above the `---` separator carries only Summary / Description / Acceptance Criteria — the fields v1 is responsible for. Other Jira fields (Labels, Components, Parent epic, Issue Type) are inherited from the parent story when a future v2 create-issue step runs.

## Optional trailing sections

Include these sections only when needed, placed AFTER the last slice:

- `## Unplaced ACs` — any parent AC you could not cleanly place. One sentence each explaining why.
- `## Slices needing review` — any slice that could not meet the "independently releasable" bar. One sentence each with the reason.
- `## Suggested additional ACs` — ACs you believe are missing from the parent. NEVER fabricate ACs inside a slice — surface them here.

## Invariant checklist

Before emitting the breakdown, verify each invariant. If any fails, fix the breakdown first.

- [ ] **AC partition.** Build the list of parent ACs first, then assign each to exactly one slice. Every parent AC appears in exactly one slice or in `## Unplaced ACs`. None appears twice. None is silently dropped.
- [ ] **Releasability.** Each slice's `Description` names either a user-visible change or a specific named feature flag the work hides behind. If neither is true, the slice goes under `## Slices needing review`.
- [ ] **Dependency order.** If Slice N depends on Slice M, then M is listed before N and `Depends on:` names M explicitly.
- [ ] **No invented ACs in slices.** ACs under a slice are verbatim text from the parent. New ACs go under `## Suggested additional ACs`.
