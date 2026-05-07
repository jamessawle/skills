# Claude Code notes

## Recommended permissions

Add these to your settings so the queue runs with minimal prompts:

```text
Bash(gh pr list*)
Bash(gh pr view*)
Bash(gh pr checks*)
Bash(gh pr merge*)
Bash(gh run view*)
Bash(gh repo clone*)
Bash(gh repo view*)
Bash(gh api repos/*)
Bash(mktemp -d*)
Bash(git -C /var/folders/*)
Bash(git -C /tmp/*)
Bash(GIT_EDITOR=true git -C /var/folders/*)
Bash(GIT_EDITOR=true git -C /tmp/*)
Bash(cd /var/folders/* && *)
Bash(cd /tmp/* && *)
Bash(rm -rf /var/folders/*)
Bash(rm -rf /tmp/*)
```
