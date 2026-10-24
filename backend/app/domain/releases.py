"""Describing a deployed version from the pull request that brought it. Pure, no I/O."""

from __future__ import annotations

import re

MERGE_RE = re.compile(r"^Merge pull request #(\d+) from ")
SQUASH_RE = re.compile(r"^(.*) \(#(\d+)\)$")
TRAILERS = ("Co-Authored-By:", "Claude-Session:", "https://claude.ai/")


SUMMARY_MAX = 220


def _paragraph(body: str) -> str:
    """The first paragraph of a commit message body as one line, without trailers."""
    out: list[str] = []
    for ln in body.splitlines():
        ln = ln.strip()
        if ln.startswith(TRAILERS):
            break
        if not ln:
            if out:
                break
            continue
        out.append(ln)
    return " ".join(out)


def _short(text: str) -> str | None:
    text = " ".join(text.split())
    if not text:
        return None
    return text if len(text) <= SUMMARY_MAX else text[: SUMMARY_MAX - 1].rstrip() + "…"


def describe_commit(subject: str, body: str, children: list[tuple[str, str]]) -> tuple[int | None, str, str | None]:
    """(PR number, PR title, a short summary) from how GitHub words a merge: "Merge pull request #N from …" with the PR title
    as the body, or a squash merge "Title (#N)". `children` are (subject, body) of the commits the merge brought in, oldest
    first; the summary is the first paragraph of the first one that has a body, else the first subject that adds to the title."""
    m = MERGE_RE.match(subject)
    if m:
        lines = [ln.strip() for ln in body.splitlines() if ln.strip() and not ln.strip().startswith(TRAILERS)]
        title = lines[0] if lines else subject
        for _, child_body in children:
            para = _paragraph(child_body)
            if para and para != title:
                return int(m.group(1)), title[:300], _short(para)
        extra = next((c for c, _ in children if c and c != title), "")
        return int(m.group(1)), title[:300], _short(extra)
    sq = SQUASH_RE.match(subject)
    if sq:
        return int(sq.group(2)), sq.group(1)[:300], _short(_paragraph(body))
    return None, subject[:300], _short(_paragraph(body))
