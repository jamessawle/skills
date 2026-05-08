# Finding output format

Specialist subagents return their findings as a JSON array. The orchestrator (`review-pr`) parses this array, deduplicates findings across subagents, and renders the final review.

## Schema

Each finding is an object with these fields:

| Field | Type | Description |
|---|---|---|
| `severity` | `"critical"` \| `"important"` \| `"suggestion"` \| `"nitpick"` | Required. Maps to the role's severity calibration. |
| `file` | string \| `null` | Required. Path to the file the finding applies to, relative to the repo root. `null` for findings that aren't tied to a specific file. |
| `line` | integer \| `null` | Required. Approximate line number in `file`. `null` if the finding is general or `file` is `null`. |
| `title` | string | Required. One-line summary. |
| `detail` | string | Required. 1–2 sentences explaining the issue and why it matters. Do not write essays. |
| `suggestion` | string \| `null` | Optional. Concrete recommended fix. `null` (or omit) if no fix is being recommended. |

## Output rules

- Respond with the JSON array and **nothing else** — no markdown fences, no narrative, no preamble, no closing summary.
- If you have no findings, respond with `[]`.
- Keep `detail` tight. Long prose belongs in commit messages, not review findings.

## Examples

A finding with all fields populated:

```json
[
  {
    "severity": "important",
    "file": "src/api/auth.js",
    "line": 42,
    "title": "Login endpoint has no rate limit",
    "detail": "Allows credential stuffing — no per-IP throttle. Visible in the diff at the new app.post('/login', ...) handler.",
    "suggestion": "Add express-rate-limit (e.g. 5 req/min per IP) to the route."
  }
]
```

A general finding (not tied to a file/line):

```json
[
  {
    "severity": "suggestion",
    "file": null,
    "line": null,
    "title": "PR mixes refactor with behaviour change",
    "detail": "The rename of UserService and the new role-check in fetchProfile are independent changes that would be easier to review separately.",
    "suggestion": "Split into two PRs."
  }
]
```

A finding with no recommended fix:

```json
[
  {
    "severity": "nitpick",
    "file": "src/utils/format.js",
    "line": 8,
    "title": "Inconsistent quote style with surrounding code",
    "detail": "This file mixes single and double quotes; rest of the module uses single."
  }
]
```

No findings:

```json
[]
```
