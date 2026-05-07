# AI Coding Skills

This repo (`jamessawle/skills` on GitHub) contains reusable skills for AI coding agents, packaged as native plugins for both Claude Code and Codex. The `SKILL.md` format itself is agent-agnostic — the dual-marketplace setup just exposes the same plugins through each agent's native plugin system.

## Repo structure

```
.claude-plugin/marketplace.json     # Claude Code marketplace — lists all plugins
.agents/plugins/marketplace.json    # Codex marketplace — lists the same plugins
plugins/
  pr-management/                    # Plugin: PR management tools
    .claude-plugin/plugin.json      # Claude plugin manifest
    .codex-plugin/plugin.json       # Codex plugin manifest
    agents/                         # Plugin-level role definitions (consumed by review-pr)
      engineer.md                   # Software engineer — correctness and reliability
      security-engineer.md          # Security engineer — threats and vulnerabilities
      performance-engineer.md       # Performance engineer — efficiency and scale
      qa-engineer.md                # QA engineer — test quality and verification
      architect.md                  # Architect — design and maintainability
    skills/
      fix-pr/SKILL.md               # Diagnose and fix broken PRs
      list-prs/SKILL.md             # List open PRs with enriched state
      merge-queue/SKILL.md          # Batch merge approved PRs
      review-pr/SKILL.md            # Review PRs with parallel specialist agents
  skill-tools/                      # Plugin: Skill development tools
    .claude-plugin/plugin.json
    .codex-plugin/plugin.json
    skills/
      skill-validator/SKILL.md      # Validate a single skill
```

Each plugin directory contains:
- `.claude-plugin/plugin.json` — Claude Code plugin manifest (`name`, `version`, `description`, `license`, …)
- `.codex-plugin/plugin.json` — Codex plugin manifest (`name`, `version`, `description`, `license`, `skills`)
- `skills/<skill-name>/` — one directory per skill (the `skills` key in the Codex manifest defaults to `./skills/`)
- `agents/` — optional. Plugin-level role definitions that the plugin's own skills can discover by globbing `<plugin-root>/agents/*.md`

Each skill directory contains:
- `SKILL.md` — the skill definition with YAML frontmatter and markdown instructions
- `references/claude.md` — recommended permission patterns (optional)
- `scripts/` — executable scripts for deterministic tasks (optional)

## Role definitions (specialist subagents)

A plugin's `agents/` directory contains specialist subagents — personas that capture how each specialist thinks, what they prioritise, and what expertise they bring. They follow the standard Claude Code / Codex subagent format (YAML frontmatter + body) so that any skill in the plugin can spawn one by name (e.g. `subagent_type: "engineer"`), and users can also invoke them directly via `/agent`. Today only `pr-management` ships subagents (consumed by `review-pr`); other plugins can add their own `agents/` directory if they need specialist personas.

Each role file must follow this structure:

1. **YAML frontmatter** — `name` (matching filename, lowercase + hyphens), `description` (when to use this subagent — used by Claude/Codex for trigger selection), and `tools` (comma-delimited tool list — usually `Read, Grep, Glob, Bash` for read-only review specialists)
2. **H1 title** — the role name (e.g. `# Software Engineer`), first line of the body
3. **Identity statement** — 1-2 sentences immediately after the title describing who the role is
4. **`## Perspective`** — how this role thinks about code, their mental model and trade-off preferences
5. **`## Areas of expertise`** — technical domains with bold-labeled items (e.g. `**Topic** -- description`)
6. **`## Severity calibration`** — four levels: **Critical**, **Important**, **Suggestion**, **Nitpick**

The body is the subagent's system prompt — it provides the perspective. The calling skill provides the per-invocation task (PR diff, what to focus on, output format). Filenames must use lowercase letters, numbers, and hyphens only (e.g. `security-engineer.md`).

## Adding a new role

1. Decide which plugin owns the role and create the file under its `agents/` directory (e.g. `plugins/pr-management/agents/devops-engineer.md`)
2. Add YAML frontmatter (`name`, `description`, `tools`) and the six-section body structure
3. Skills in that plugin can spawn it by name via the Agent tool — no registration step is needed
4. Run `claude plugin validate plugins/<plugin-name>` to validate the subagent frontmatter

## Skill standard

Skills in this repo follow the [Agent Skills specification](https://agentskills.io/specification). Key points:

- Every skill is a directory containing a `SKILL.md` with YAML frontmatter and markdown instructions
- Required frontmatter: `name` (lowercase, hyphens, must match directory name, max 64 chars) and `description` (max 1024 chars)
- Optional frontmatter: `license`, `compatibility`, `metadata`, `allowed-tools`
- Optional directories: `scripts/` (executable code), `references/` (docs loaded on demand), `assets/` (static resources)
- Keep `SKILL.md` under 500 lines; move detailed content to `references/`
- Progressive disclosure: metadata (~100 tokens) is always loaded, the full body loads on activation, resources load on demand

### Claude Code extensions

These fields are not part of the Agent Skills spec but are used by Claude Code:
- `allowed-tools` — Claude Code uses comma-delimited (e.g. `Bash, Read, Edit`); the spec defines space-delimited
- `argument-hint` — shows usage hint in the skill picker (e.g. `"[owner/repo] [mine]"`)

## Adding a new skill

1. Create a directory under the appropriate plugin: `plugins/<plugin-name>/skills/<skill-name>/`
2. Write `SKILL.md` with frontmatter and workflow
3. Validate the skill with `/skill-tools:skill-validator <path>` (markdown lint + content consistency)
4. Validate the surrounding plugin with `claude plugin validate plugins/<plugin-name>` (manifest + frontmatter)
5. Update `README.md` with the new skill

## Adding a new plugin

1. Create a directory: `plugins/<plugin-name>/`
2. Add `.claude-plugin/plugin.json` with `name`, `version`, `description`, `license` (and optional `author`, `homepage`, `repository`, `keywords`)
3. Add `.codex-plugin/plugin.json` with `name`, `version`, `description`, `keywords`, `skills: "./skills/"`, and (optional) `interface.category` for grouping in the marketplace picker — note that `license` is not part of the Codex manifest spec
4. Add at least one skill under `plugins/<plugin-name>/skills/<skill-name>/`
5. Add an entry to **both** marketplace manifests:
   - `.claude-plugin/marketplace.json`: `{ "name", "source": "./plugins/<name>", "description", "category" }`
   - `.agents/plugins/marketplace.json`: `{ "name", "source": { "source": "local", "path": "./plugins/<name>" }, "policy": { "installation": "AVAILABLE", "authentication": "ON_INSTALL" } }` — note that `category` is not a valid field at this level for Codex (put it under the per-plugin manifest's `interface.category` instead)
6. Validate the Claude side with `claude plugin validate .` (covers marketplace + plugin manifests + subagent frontmatter); validate the Codex side with `codex plugin marketplace add .` from inside the repo (a clean add with no warnings means the manifests parse)

## Validation

Always validate before committing:
- Each modified skill: `/skill-tools:skill-validator <path-to-skill-directory>` (markdown lint + content consistency that Anthropic's validator does not cover)
- Whole repo (Claude side): `claude plugin validate .` for the marketplace, plus `claude plugin validate plugins/<name>` for each plugin

The Codex marketplace and per-plugin `.codex-plugin/plugin.json` files are not currently validated by an automated tool — verify them by adding the marketplace to a real Codex install (`codex marketplace add github:jamessawle/skills`).

## Creating and improving skills

Use `/skill-creator:skill-creator` for the full skill development lifecycle:
- **Creating new skills** — captures intent, writes the SKILL.md draft, generates test cases, and iterates based on feedback
- **Measuring effectiveness** — runs eval prompts with and without the skill to compare output quality
- **Description optimization** — tests whether the skill triggers for natural language queries and improves the description (requires `ANTHROPIC_API_KEY` for the full loop; without it, use the eval-only step via `run_eval.py`)

Typical workflow: draft with `/skill-creator`, validate the skill with `/skill-tools:skill-validator <path>` and the plugin with `claude plugin validate plugins/<plugin-name>`, then commit.

## PR checklist

Before creating a pull request:
1. Run `/skill-tools:skill-validator <path>` on each modified skill and `claude plugin validate .` on the repo — all checks must pass
2. Ensure `README.md` is updated if skills were added or removed
3. Ensure both `.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json` list any new plugin
4. Commit messages should describe what changed and why

## Key conventions

- Skills that interact with external repos use `git -C <path>` rather than `cd <path> && git` — Claude Code's sandbox blocks the latter pattern
- Permission patterns in `references/claude.md` cover both `/var/folders/*` (macOS) and `/tmp/*` (Linux) temp paths
- Skill descriptions should include explicit trigger phrases to aid auto-triggering
- The `references/claude.md` file is not part of the skill spec — it's a Claude Code-specific convention for permission hints
