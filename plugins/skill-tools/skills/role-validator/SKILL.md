---
name: role-validator
description: Validate role definition files in the agents/ directory for structural correctness. Checks that each role file has a title, identity statement, Perspective section, Areas of expertise section with bold-labeled items, and Severity calibration section with all four levels (Critical, Important, Suggestion, Nitpick). Also verifies filename conventions. Use this skill whenever someone asks to validate, lint, or check role definitions, verify agents are well-formed, audit the agents/ directory, or catch problems with role files before publishing. This is for role validation — for checking skills, use skill-validator instead.
license: MIT
compatibility: Requires Node.js
allowed-tools: Bash
argument-hint: "<path-to-role-file-or-agents-directory>"
metadata:
  author: jamessawle
  version: "1.0"
---

# Role Validator

Validates role definition files in the `agents/` directory for structural correctness.

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
- Has a title (H1 heading)
- Title is followed by an identity statement (not another heading)
- Has `## Perspective` section
- Has `## Areas of expertise` section with bold-labeled items
- Has `## Severity calibration` section with all four levels (Critical, Important, Suggestion, Nitpick)
- Filename uses lowercase-hyphen convention

### Step 3: Report results

Output the validation results. For each role file, show pass/fail for each check with a summary count.
