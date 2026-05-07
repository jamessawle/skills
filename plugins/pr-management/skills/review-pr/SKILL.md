---
name: review-pr
description: Use this skill whenever someone asks to review a pull request, check code quality, or get feedback on PR changes. Dynamically discovers specialist roles from the agents/ directory and spawns them in parallel to analyse the diff independently, then collates and deduplicates findings into a structured review. Trigger for "review PR", "review this PR", "code review", "check the code in PR", "look at the changes in PR", "what do you think of this PR", or any request to assess the quality of a pull request's changes.
license: MIT
compatibility: Requires GitHub CLI (gh) authenticated with read access to the target repo. Requires agents/*.md role definitions at the marketplace repository root.
allowed-tools: Bash, Read, Grep, Glob, Agent
argument-hint: "[owner/repo] [pr-number]"
metadata:
  author: jamessawle
  version: "2.0"
---

# Review PR

Review a pull request by spawning parallel specialist reviewers, then collating their findings into a single structured report.

## Arguments

Positional arguments are interpreted based on their format:

| Arguments | Behaviour |
|-----------|-----------|
| `owner/repo 123` | Review PR #123 in that repo |
| `123` | Review PR #123 in the current repo |
| _(none)_ | Detect the PR for the current branch |

**Dispatch logic:**

- If two arguments are provided, the first (containing `/`) is `owner/repo` and the second is the PR number
- If one argument is provided and is numeric, treat it as a PR number in the current repo
- If one argument is provided and contains `/`, treat it as `owner/repo` and detect the PR from the current branch
- If no arguments are provided, detect the current branch's PR

Validate inputs before using them in any command:

- **PR number**: must contain only digits
- **owner/repo**: must match the pattern `[a-zA-Z0-9._-]+/[a-zA-Z0-9._-]+`

When no arguments are provided, detect the current branch's PR:

```bash
gh pr view --json number,headRefName --jq '.number'
```

If no PR is associated with the current branch, report that and stop.

## Workflow

### Step 1: Gather PR context

Determine the PR number and optional `--repo` flag from the arguments (see dispatch logic above). Then run these in parallel (separate tool calls in a single message):

```bash
gh pr view <number> [--repo <owner/repo>] --json title,body,baseRefName,headRefName,additions,deletions,changedFiles,labels,author
```

```bash
gh pr view <number> [--repo <owner/repo>] --json files --jq '.files[].path'
```

From the results, determine:

- **PR scope**: small (<100 lines changed), medium (100-500), large (500+)
- **Primary languages**: detect from file extensions in the changeset
- **PR type**: feature, bugfix, refactor, dependency update, config change, docs — infer from title, labels, and file patterns

### Step 2: Clone the PR for review

Clone the repository into a temporary directory and check out the PR branch so that subagents can read files directly rather than receiving the entire diff in their prompt:

```bash
REVIEW_DIR=$(mktemp -d)
gh repo clone <owner/repo> "$REVIEW_DIR" -- --depth=1 --single-branch
git -C "$REVIEW_DIR" fetch origin "pull/<number>/head:pr-review"
git -C "$REVIEW_DIR" checkout pr-review
```

If the clone fails (e.g. very large repo or network issues), fall back to fetching the diff via `gh pr diff` and passing it directly to subagents. Note this fallback in the subagent prompts.

For large repositories, check size before cloning:

```bash
gh api "repos/<owner>/<repo>" --jq '.size'
```

If the repo is over 500000 KB, skip the clone and use the diff-only fallback.

Also fetch the diff via the GitHub API (avoids shallow clone limitations):

```bash
gh pr diff <number> [--repo <owner/repo>] > "$REVIEW_DIR/.pr-diff.txt"
```

Reuse the `baseRefName` value already fetched in Step 1 — do not make a redundant `gh pr view` call.

### Step 3: Discover and select roles

Resolve the marketplace repository root by walking up from this SKILL.md file's own directory until you find a directory containing `CLAUDE.md`. Glob `agents/*.md` from there — not from the cloned PR repo. If no role files are found, report an error ("No role definitions found at agents/*.md — ensure the agents directory is present at the marketplace repository root") and stop.

Read each role file to evaluate relevance. Based on each role's identity, perspective, and areas of expertise — combined with the PR context (languages, file types, scope, PR type) — decide which roles would add value to this review. The general principle: skip roles whose areas of expertise have no overlap with the file types and content in the changeset. Common patterns:

- **Docs-only PRs** (`.md`, `.txt`, `.rst`) — skip Performance Engineer, QA Engineer
- **Config-only PRs** (`.json`, `.yaml`, `.toml`) — skip Performance Engineer, QA Engineer
- **Dependency updates** (lockfiles) — skip QA Engineer, Architect
- **Small code PRs** (<100 lines) — skip Architect
- **No executable code** — skip QA Engineer

Software Engineer and Security Engineer are included for all PR types — correctness and security concerns apply regardless of file type.

These are calibration examples, not rigid rules. Apply the same principle to any new roles discovered — use judgment for mixed or unusual PRs.

If no roles are selected (e.g. a trivial whitespace-only change), skip Steps 4 and 5 and produce a summary noting that the PR did not warrant specialist review.

For any roles not selected, note in the final report: "Skipped [role] — [brief reason]."

The role file contents read here will be reused in Step 4 prompts — do not re-read the files.

### Step 4: Spawn specialist reviewers

Spawn the selected roles as subagents in parallel using the Agent tool. Use the role file contents already read in Step 3 — embed them directly in each subagent's prompt. Each subagent also receives:

- The PR metadata (title, description, author, base branch)
- The path to the cloned repo (`$REVIEW_DIR`)
- The list of changed files
- The PR scope, primary languages, and type
- The path to the diff file (`$REVIEW_DIR/.pr-diff.txt`)

For each subagent, the prompt should be structured as:

```text
## Your role
[full contents of the role file]

## Your task
Review this pull request from the perspective described above.

## PR Context
- Title: [title]
- Author: [author]
- Base: [baseRefName] <- [headRefName]
- Scope: [small/medium/large] ([additions] additions, [deletions] deletions, [changedFiles] files)
- Languages: [detected languages]
- PR description: [body]

## Repository
The PR has been checked out at: [REVIEW_DIR]
The diff is at: [REVIEW_DIR]/.pr-diff.txt

## Changed files
[file list]

## Instructions
- Read the diff file to understand what changed
- Use Read to examine specific changed files for full context
- Focus on the changed files listed above — do not review unrelated code
- If the PR contains no content relevant to your expertise, respond with an empty array and a brief note explaining why
- Respond with ONLY a JSON array (no markdown fences, no surrounding text)

Each finding in the array should have:
- "severity": "critical" | "important" | "suggestion" | "nitpick"
- "file": the file path (or null if general)
- "line": approximate line number in the file (or null if general)
- "title": short summary (one line)
- "detail": explanation of the issue and why it matters
- "suggestion": recommended fix or alternative (if applicable)

If you have no findings, respond with an empty array: []
```

### Step 5: Collate and deduplicate

Once all reviewers return, merge their findings:

1. **Parse** each reviewer's JSON response. If a response is not valid JSON, attempt to extract a JSON array from within markdown code fences. If that also fails, note the reviewer as having returned no findings and continue with the remaining reviewers.
2. **Deduplicate** — two findings are duplicates if they reference the same file, are within 5 lines of each other, and describe the same underlying issue. When merging duplicates, keep the finding with the longer `detail` field and note all reviewers that flagged it. Examples: two reviewers flagging a missing null check on the same line = duplicate; one flagging a null check and another flagging a type error on the same line = distinct (different issues).
3. **Sort** by severity: critical first, then important, suggestions, nitpicks
4. **Count** findings per severity level

### Step 6: Clean up

Remove the temporary clone directory:

```bash
rm -rf "$REVIEW_DIR"
```

Always clean up the temp directory, even on early exit or failure. If any workflow step fails, clean up before reporting the error.

### Step 7: Output the review

Present the review in this format:

```markdown
## PR Review: [title]

**[owner/repo]#[number]** | [author] | [additions]+/[deletions]- across [changedFiles] files

### Summary

[2-3 sentence overview: what the PR does, overall quality assessment, key risk areas]

### Risk Assessment

| Dimension | Rating |
|-----------|--------|
| Risk level | Low / Medium / High / Critical |
| Complexity | Low / Medium / High |
| Test coverage | Adequate / Needs work / Missing |

### Findings

#### Critical ([count])

- **[title]** (`file:line`) — [detail]. *Suggestion: [suggestion]*

#### Important ([count])

- **[title]** (`file:line`) — [detail]. *Suggestion: [suggestion]*

#### Suggestions ([count])

- **[title]** (`file:line`) — [detail]

#### Nitpicks ([count])

- **[title]** (`file:line`) — [detail]

### Positive observations

[Note good practices, clean code, thorough tests — always include something positive]

### Verdict

One of:
- **Approve** — no critical or important findings
- **Approve with comments** — no critical findings, 1-2 important findings
- **Request changes** — has critical findings or 3+ important findings
- **Block** — has critical security vulnerabilities or data loss/corruption findings (supersedes Request changes; display-only — GitHub has no "block" review action)
```

Omit severity sections that have zero findings.

### Step 8: Offer to post

After presenting the review, ask the user:

> "Would you like me to post this as a review on the PR? I can submit it as a GitHub review with inline comments."

If they say yes:

1. Post the summary as a PR review comment using a heredoc to avoid shell injection:

   ```bash
   gh pr review <number> [--repo <owner/repo>] --comment --body "$(cat <<'EOF'
   [review body — wrap any code/diff excerpts in fenced code blocks]
   EOF
   )"
   ```

2. For critical and important findings that have specific file+line references, post inline comments. Note: these appear as standalone comments on the PR timeline, not grouped with the review summary — the GitHub API does not support adding inline comments to an existing review after submission.

   ```bash
   gh api repos/<owner>/<repo>/pulls/<number>/comments \
     -f body="$(cat <<'EOF'
   [finding detail — wrap code excerpts in fenced code blocks]
   EOF
   )" \
     -f path="[file path]" \
     -f side="RIGHT" \
     -F line=[line number] \
     -f commit_id="$(gh pr view <number> [--repo <owner/repo>] --json headRefOid --jq '.headRefOid')"
   ```

If they say no, the review is complete.

## Important guidelines

- **ALWAYS offer to post** — after presenting the review, you MUST ask the user whether they want it posted to the PR. Never skip Step 8. This is the final step of every review, not optional.
- **Read-only by default** — never post to GitHub without explicit user approval
- **Never approve or request changes programmatically** — only use `gh pr review --comment`, never `--approve` or `--request-changes`, unless the user explicitly asks for it
- **Follow all workflow steps** — every numbered step must be executed in order. Do not skip steps because they seem unnecessary in context.
- **Be constructive** — explain _why_ something is problematic and suggest alternatives
- **Be proportional** — match review depth to PR risk; don't block on style for a hotfix
- **Always find positives** — every PR has something done well; mention it
- **Respect the diff** — only review what changed, not pre-existing code unless the change makes it worse
- **Sanitize output** — wrap any code or diff excerpts in fenced code blocks when assembling the review body to prevent unintended markdown rendering
