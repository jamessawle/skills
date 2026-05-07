---
name: role-validator
description: Validate specialist subagent role files in a plugin's agents/ directory for structural correctness. Checks both the subagent YAML frontmatter (name matching filename, non-empty description) and the role-definition body (H1 title, identity statement, Perspective section, Areas of expertise section with bold-labeled items, and Severity calibration section with all four levels — Critical, Important, Suggestion, Nitpick). Also verifies filename conventions. Use this skill whenever someone asks to validate, lint, or check role definitions, verify subagents are well-formed, audit a plugin's agents/ directory, or catch problems with role files before publishing. This is for role validation — for checking skills, use skill-validator instead.
license: MIT
compatibility: Requires Node.js
allowed-tools: Bash
argument-hint: "<path-to-role-file-or-agents-directory>"
metadata:
  author: jamessawle
  version: "2.0"
---

# Role Validator

Validates specialist subagent role files in a plugin's `agents/` directory for both subagent-frontmatter correctness and role-definition body structure.

## Required permissions

Add this to your settings so the validation runs without prompts:

**Allow:**

```text
Bash(*/scripts/validate.sh*)
```

## Arguments

- `<path>` — Path to a single role file (e.g. `agents/engineer.md`) or the `agents/` directory to validate all roles. Defaults to `./agents/` relative to the current working directory if not provided.

## Workflow

### Step 1: Resolve target

If no argument is provided, default to `./agents/` relative to the current working directory.

If a directory is provided, validate all `.md` files within it. If a single file is provided, validate just that file.

### Step 2: Run validation

```bash
<path-to-this-skill>/scripts/validate.sh '<target>'
```

This checks each role file for:

- File exists and is readable
- Has YAML frontmatter (the subagent metadata block delimited by `---`)
- Frontmatter `name` matches the filename (without `.md`)
- Frontmatter has a non-empty `description`
- Body has a title (H1 heading) at the top, after the frontmatter
- Title is followed by an identity statement (not another heading)
- Has `## Perspective` section
- Has `## Areas of expertise` section with bold-labeled items
- Has `## Severity calibration` section with all four levels (Critical, Important, Suggestion, Nitpick)
- Filename uses lowercase-hyphen convention

### Step 3: Report results

Output the validation results. For each role file, show pass/fail for each check with a summary count.
