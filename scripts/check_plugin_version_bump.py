#!/usr/bin/env python3
"""Fail if a plugin's source changed without bumping its manifest version.

Motivated by plugins/git-guard's hooks changing behavior across two PRs
(#26, #27) without either bumping plugins/git-guard/.claude-plugin/plugin.json
— nothing caught it because there was no check for it. For each plugin
directory touched by this diff, if anything besides its top-level README.md
changed, the "version" field in its .claude-plugin/plugin.json must differ
from the base ref's version too.
"""

from __future__ import annotations

import json
import subprocess
import sys

DEFAULT_BASE_REF = "origin/main"


def changed_files(base_ref: str) -> list[str]:
    out = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
        capture_output=True, text=True, check=True,
    )
    return [line for line in out.stdout.splitlines() if line]


def manifest_version(ref: str, path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"], capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None  # didn't exist at that ref — new plugin, nothing to bump
    return json.loads(result.stdout).get("version")


def main() -> int:
    base_ref = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_BASE_REF
    files = changed_files(base_ref)
    plugins = {f.split("/")[1] for f in files if f.startswith("plugins/") and len(f.split("/")) > 2}

    failures = []
    for name in sorted(plugins):
        prefix = f"plugins/{name}/"
        manifest = f"{prefix}.claude-plugin/plugin.json"
        relevant = [f for f in files if f.startswith(prefix) and f != f"{prefix}README.md"]
        if not relevant:
            continue  # only the README changed — no version bump needed

        old_version = manifest_version(base_ref, manifest)
        new_version = manifest_version("HEAD", manifest)
        if old_version == new_version:
            failures.append(name)

    if failures:
        print("Plugin source changed without a version bump in .claude-plugin/plugin.json:")
        for name in failures:
            print(f"  - {name}")
        print('\nBump the "version" field in plugins/<name>/.claude-plugin/plugin.json.')
        return 1

    print("Plugin version bump check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
