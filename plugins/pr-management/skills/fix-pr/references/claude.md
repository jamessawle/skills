# Claude Code notes

## Recommended permissions

Add these to your settings so only the final push and comment require approval:

```text
Bash(gh pr view*)
Bash(gh pr checks*)
Bash(gh run view*)
Bash(gh repo clone*)
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
