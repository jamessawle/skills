# AI Coding Skills

Reusable skills for AI coding agents, packaged as native plugins for both Claude Code and Codex.

## Skills

| Skill | Description | Plugin | Prerequisites |
|-------|-------------|--------|---------------|
| [`fix-pr`](plugins/pr-management/skills/fix-pr/SKILL.md) | Fix a GitHub PR with merge conflicts or failed CI — diagnoses, rebases, resolves conflicts, and pushes. | pr-management | [GitHub CLI](https://cli.github.com/) (`gh`) |
| [`list-prs`](plugins/pr-management/skills/list-prs/SKILL.md) | List open PRs with enriched state — CI status, reviews, conflicts, and staleness. Single repo or cross-repo. | pr-management | [GitHub CLI](https://cli.github.com/) (`gh`) |
| [`merge-queue`](plugins/pr-management/skills/merge-queue/SKILL.md) | Process approved PRs through a merge queue — fixes and merges each one sequentially, re-querying after each merge. | pr-management | [GitHub CLI](https://cli.github.com/) (`gh`) |
| [`review-pr`](plugins/pr-management/skills/review-pr/SKILL.md) | Review a PR with parallel specialist reviewers (correctness, security, performance, testing, architecture) and produce a structured report. | pr-management | [GitHub CLI](https://cli.github.com/) (`gh`) |
| [`write-pr-description`](plugins/pr-management/skills/write-pr-description/SKILL.md) | Draft a PR description focused on the reasoning behind the change — problem, approach, trade-offs, verification — rather than restating the diff. | pr-management | git (optionally [GitHub CLI](https://cli.github.com/) (`gh`) for linked issues) |
| [`skill-validator`](plugins/skill-tools/skills/skill-validator/SKILL.md) | Validate a single skill — checks markdown formatting, frontmatter fields, and content consistency. | skill-tools | Node.js |

## Installation

Both agents can install this marketplace directly from GitHub — no clone required.

### Claude Code

```text
/plugin marketplace add jamessawle/skills
```

Then `/plugin install pr-management` (or `skill-tools`) from the marketplace picker.

### Codex

```bash
codex plugin marketplace add jamessawle/skills
```

Then start an interactive session with `codex` and install the plugins from the marketplace picker.

Pin to a specific ref with `--ref`, e.g. `codex plugin marketplace add jamessawle/skills --ref v1.0.0`.
