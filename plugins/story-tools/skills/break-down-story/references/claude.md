# Claude Code notes

## Recommended permissions

Add these to your settings so the common Jira reads and local git checks auto-approve:

```text
Bash(git rev-parse*)
Bash(git -C * rev-parse*)
mcp__claude_ai_Atlassian__getJiraIssue
mcp__claude_ai_Atlassian__searchJiraIssuesUsingJql
mcp__claude_ai_Atlassian__getJiraIssueRemoteIssueLinks
```

Adjust the Atlassian MCP tool name prefix (e.g. `mcp__claude_ai_Atlassian__` vs `mcp__atlassian__`) to match your local MCP server registration.

## Prerequisites

- The Atlassian MCP server must be configured and authenticated against your Jira instance.
- The skill must be run from inside the service repo the story affects (`cwd` is checked at the start).
