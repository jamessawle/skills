# AI Coding Skills

Reusable skills for AI coding agents, packaged as native plugins for both Claude Code and Codex.

## Skills

| Skill | Description | Plugin | Prerequisites |
|-------|-------------|--------|---------------|
| [`fix-pr`](plugins/pr-management/skills/fix-pr/SKILL.md) | Fix a GitHub PR with merge conflicts or failed CI — diagnoses, rebases, resolves conflicts, and pushes. | pr-management | [GitHub CLI](https://cli.github.com/) (`gh`) |
| [`list-prs`](plugins/pr-management/skills/list-prs/SKILL.md) | List open PRs with enriched state — CI status, reviews, conflicts, and staleness. Single repo or cross-repo. | pr-management | [GitHub CLI](https://cli.github.com/) (`gh`) |
| [`merge-queue`](plugins/pr-management/skills/merge-queue/SKILL.md) | Process approved PRs through a merge queue — fixes and merges each one sequentially, re-querying after each merge. | pr-management | [GitHub CLI](https://cli.github.com/) (`gh`) |
| [`review-pr`](plugins/pr-management/skills/review-pr/SKILL.md) | Review a PR with parallel specialist reviewers (correctness, security, performance, testing, architecture) and produce a structured report. | pr-management | [GitHub CLI](https://cli.github.com/) (`gh`) |
| [`skill-validator`](plugins/skill-tools/skills/skill-validator/SKILL.md) | Validate a single skill — checks markdown formatting, frontmatter fields, and content consistency. | skill-tools | Node.js |
| [`marketplace-validator`](plugins/skill-tools/skills/marketplace-validator/SKILL.md) | Validate a skills marketplace — checks repo structure, JSON schemas, plugin paths, then validates each skill. | skill-tools | Node.js |
| [`role-validator`](plugins/skill-tools/skills/role-validator/SKILL.md) | Validate role definition files — checks structure, required sections, severity levels, and naming conventions. | skill-tools | Node.js |

## Installation

### Claude Code

Add this repo as a marketplace in `~/.claude/settings.json`:

```json
{
  "extraKnownMarketplaces": {
    "jamessawle-marketplace": {
      "source": { "source": "github", "repo": "jamessawle/skills" }
    }
  }
}
```

Then run `/plugin marketplace add jamessawle-marketplace` and install the plugins you want.

### Codex

Clone the repo and add it as a local marketplace:

```bash
codex marketplace add jamessawle-skills /path/to/jamessawle/skills
```

Or point Codex at this repo as a GitHub marketplace source. The Codex manifest lives at `.agents/plugins/marketplace.json`.
