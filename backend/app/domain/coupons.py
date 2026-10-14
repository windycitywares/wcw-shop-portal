"""Coupon codes: normalizing what shoppers type and generating unguessable codes in bulk."""

import re
import secrets
from collections.abc import Iterable

# No 0/O/1/I so a code read out over the phone or typed from a printed card isn't ambiguous.
ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_RE = re.compile(r"^[A-Z0-9]{3,40}$")
MAX_BATCH = 5000


def normalize_code(raw: str | None) -> str:
    """'welcome-10 ' -> 'WELCOME10': letters and digits only, upper-case."""
    return re.sub(r"[^A-Za-z0-9]", "", raw or "").upper()


def is_valid_code(code: str) -> bool:
    return bool(CODE_RE.match(code))


def clean_prefix(prefix: str | None) -> str:
    return normalize_code(prefix)[:12]


def generate_code(prefix: str = "", length: int = 8) -> str:
    prefix = clean_prefix(prefix)
    length = max(6, min(length, 40 - len(prefix)))
    return prefix + "".join(secrets.choice(ALPHABET) for _ in range(length))


def generate_codes(count: int, prefix: str = "", length: int = 8, taken: Iterable[str] = ()) -> list[str]:
    """`count` distinct codes that are not in `taken`. Raises ValueError if the space is too small."""
    if not 1 <= count <= MAX_BATCH:
        raise ValueError(f"Generate between 1 and {MAX_BATCH} codes at a time")
    prefix = clean_prefix(prefix)
    length = max(6, min(length, 40 - len(prefix)))
    if len(ALPHABET) ** length < count * 1000:
        raise ValueError("Code length is too short for that many codes")
    seen = set(taken)
    out: list[str] = []
    while len(out) < count:
        code = generate_code(prefix, length)
        if code not in seen:
            seen.add(code)
            out.append(code)
    return out
