"""Coupon codes: normalising what a customer types and generating new ones."""

import re
import secrets

# No 0/O or 1/I/L, so a code read off a card or an email can't be mistyped.
ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
CODE_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,39}$")
PREFIX_PATTERN = re.compile(r"^[A-Z0-9]{1,12}$")


def normalize_code(raw: str) -> str:
    """What the customer typed -> how codes are stored: no spaces, upper case."""
    return re.sub(r"\s+", "", raw or "").upper()


def is_valid_code(code: str) -> bool:
    return bool(CODE_PATTERN.match(code))


def random_code(prefix: str = "", length: int = 8) -> str:
    """e.g. WELCOME-K7M2QX4P (prefix given) or K7M2QX4P."""
    body = "".join(secrets.choice(ALPHABET) for _ in range(length))
    return f"{prefix}-{body}" if prefix else body
