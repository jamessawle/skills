# Claude Code notes

## Recommended permissions

Add these to your settings so only the final review posting requires approval:

```text
Bash(gh pr view*)
Bash(gh pr diff*)
Bash(gh pr review * --comment*)
Bash(gh api repos/*/pulls/*/comments*)
Bash(gh api repos/*/pulls/*/reviews*)
Bash(gh repo clone*)
Bash(mktemp -d*)
Bash(git -C /tmp/* *)
Bash(git -C /var/folders/* *)
Bash(rm -rf /tmp/tmp.*)
Bash(rm -rf /var/folders/*/T/tmp.*)
```

`Bash(gh repo clone*)` auto-approves cloning any repository. Narrow it to `Bash(gh repo clone <your-org>/*)` if you only review PRs in one org.
