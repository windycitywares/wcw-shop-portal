"""Describing a deployed version from the pull request that brought it. Pure, no I/O."""

from __future__ import annotations

import re

MERGE_RE = re.compile(r"^Merge pull request #(\d+) from ")
SQUASH_RE = re.compile(r"^(.*) \(#(\d+)\)$")
TRAILERS = ("Co-Authored-By:", "Claude-Session:", "https://claude.ai/")


def describe_commit(subject: str, body: str, children: list[str]) -> tuple[int | None, str, str | None]:
    """(PR number, PR title, what it did) from how GitHub words a merge: "Merge pull request #N from …" with the PR title
    as the body, or a squash merge "Title (#N)". `children` are the subjects of the commits the merge brought in."""
    lines = [ln.strip() for ln in body.splitlines() if ln.strip() and not ln.strip().startswith(TRAILERS)]
    m = MERGE_RE.match(subject)
    if m:
        title = lines[0] if lines else subject
        did = [c for c in children if c and c != title]
        return int(m.group(1)), title[:300], ("\n".join(did)[:1500] or None)
    sq = SQUASH_RE.match(subject)
    if sq:
        return int(sq.group(2)), sq.group(1)[:300], ("\n".join(lines)[:1500] or None)
    return None, subject[:300], ("\n".join(lines)[:1500] or None)
