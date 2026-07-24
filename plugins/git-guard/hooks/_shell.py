"""Shared shell-command tokenising for the git and gh guards.

Both guards classify a Bash call by splitting it into its pipeline/chain
segments before deciding on each one, so the tokeniser and the operator/
redirect-fragment handling live here once instead of twice.
"""

from __future__ import annotations

import shlex

OPERATORS = {"&&", "||", "|", "|&", ";", "&", "(", ")"}

# Read-only pager/filter tools harmless as pipe targets. Excludes anything that
# writes or executes (tee, xargs, sed, awk, …) — those still downgrade the call.
# Guard-specific extras (e.g. gh-guard's `jq`) are added on top of this base.
SAFE_PIPE = {
    "cat", "head", "tail", "less", "more", "grep", "egrep", "fgrep", "wc",
    "sort", "uniq", "nl", "cut", "tr", "rev", "column",
}


def segments(cmd: str) -> list[list[str]]:
    """Quote-aware split into command segments (lists of tokens).
    Raises ValueError on unbalanced quotes."""
    lexer = shlex.shlex(cmd, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    out: list[list[str]] = []
    cur: list[str] = []
    for tok in lexer:
        if tok in OPERATORS:
            if cur:
                out.append(cur)
                cur = []
        else:
            cur.append(tok)
    if cur:
        out.append(cur)
    return out


# Redirect-operator punctuation tokens shlex(punctuation_chars=True) can
# produce. It groups consecutive punctuation characters into one token, so a
# compound redirect like "2>&1" lexes as "2", ">&", "1" — three tokens, not
# one — and a lone ">" or "<" isn't the whole story once fd-duplication
# (">&", "<&"), append (">>", "&>>"), noclobber ("<>", ">|") and here-string
# ("<<<") forms are included. "-" covers fd-close syntax (e.g. "1>&-").
_REDIRECT_OPS = {">", "<", ">>", "<<", ">&", "<&", "&>", "&>>", ">|", "<>", "<<<"}


def is_redirect_fragment(tokens: list[str]) -> bool:
    """True for a segment made entirely of redirect noise — digits, fd-close
    markers, and redirect-operator tokens (e.g. ['2', '>&', '1'] from a
    standalone "2>&1") — or an empty segment. Not a real command."""
    return not tokens or all(t.isdigit() or t in _REDIRECT_OPS or t == "-" for t in tokens)
