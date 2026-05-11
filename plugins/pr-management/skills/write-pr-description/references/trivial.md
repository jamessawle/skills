# Example: small fix where ceremony would be noise

Read this when the PR is a single-line fix, a typo, a dependency bump, or any change small enough that the diff carries its own reasoning. The goal is to avoid padding the description with empty sections.

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
