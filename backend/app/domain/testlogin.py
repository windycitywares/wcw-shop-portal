"""Who may sign in while Test mode is on.

Test mode works on a copy of the live data, and the copy holds real customers' password hashes. So in Test mode only
the accounts an admin lists (Admin → Environment → Test sign-in) can sign in. When that list is empty, only admin
accounts can, so the owner can still get in to set it up.
"""

from collections.abc import Iterable

from app.core.enums import UserRole


def test_login_allowed(email: str, role: str, allowlist: Iterable[str]) -> bool:
    normalized = email.strip().lower()
    approved = {e.strip().lower() for e in allowlist if e and e.strip()}
    if approved:
        return normalized in approved
    return role == UserRole.ADMIN
