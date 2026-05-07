---
name: marketplace-validator
description: Validate a dual Claude Code + Codex skills marketplace repository end-to-end. Checks both .claude-plugin/marketplace.json and .agents/plugins/marketplace.json, verifies all plugin references and directory structure, validates every per-plugin manifest (.claude-plugin/plugin.json and .codex-plugin/plugin.json), confirms the two marketplaces list the same plugin set, then runs skill-validator on each skill found. Use this skill whenever someone asks to validate, check, or audit an entire marketplace repo, verify marketplace structure, check that plugin paths and JSON schemas are correct, or run a full validation sweep before publishing. This is for whole-marketplace validation — for checking a single skill, use skill-validator instead.
license: MIT
compatibility: Requires Node.js
allowed-tools: Bash, Read
argument-hint: <path-to-marketplace-root>
metadata:
  author: jamessawle
  version: "1.1"
---

# Marketplace Validator

Validates a dual Claude Code + Codex skills marketplace repository, then validates each skill and role within it.

1. **Marketplace structure** — JSON schemas, plugin paths, directory layout for both Claude (`.claude-plugin/marketplace.json`) and Codex (`.agents/plugins/marketplace.json`) manifests
2. **Per-skill validation** — delegates to the skill-validator's tooling for each skill found
3. **Role validation** — delegates to the role-validator's tooling for each role file found in `agents/`

## Required permissions

Add this to your settings so the validation runs without prompts:

**Allow:**

```text
Bash(*/scripts/validate.sh*)
```

## Arguments

- `$0` — Path to a marketplace root (directory containing `.claude-plugin/marketplace.json` and/or `.agents/plugins/marketplace.json`). Defaults to the current working directory if not provided.

## Workflow

### Step 1: Verify target

Check that `$0/.claude-plugin/marketplace.json` or `$0/.agents/plugins/marketplace.json` exists. If neither does, report an error and stop.

### Step 2: Marketplace structure validation

```bash
${CLAUDE_SKILL_DIR}/scripts/validate.sh '$0'
```

This checks:

- **Claude marketplace** (`.claude-plugin/marketplace.json`) is valid JSON with required fields (`name`, `plugins` array). Each plugin entry has `name`, `source`, `description`; the source directory exists; the plugin has a `.claude-plugin/plugin.json` with `name`, `description`, `version` (and `name` matching the marketplace entry); the plugin has a `skills/` directory with at least one skill; each skill directory contains a `SKILL.md` with valid frontmatter
- **Codex marketplace** (`.agents/plugins/marketplace.json`) is valid JSON with required fields (`name`, `plugins` array). Each plugin entry has `name`, `source` (with `source: "local"` and `path`), `policy` (with `installation`); the source directory exists; the plugin has a `.codex-plugin/plugin.json` with `name`, `description`, `version` (and `name` matching the marketplace entry)
- **Cross-marketplace consistency** — both manifests list the same plugin names

### Step 3: Per-skill validation

For each skill directory found in Step 2, delegate to the `skill-validator` skill to perform full validation (markdown formatting, frontmatter fields, content review). Pass the skill directory path as the argument.

### Step 4: Role validation

If an `agents/` directory exists at the marketplace root, delegate to the `role-validator` skill to validate all role files. Pass the `agents/` directory path as the argument.

If no `agents/` directory exists, skip this step (roles are optional).

### Step 5: Summary

Output a combined report:

- **Marketplace structure**: X passed, Y failed
- **Per-skill results**: for each skill, markdown formatting + content review findings
- **Role validation**: for each role, structural validation results (or "No roles found — skipped")
- **Overall verdict**: PASS / FAIL with actionable next steps for any failures
