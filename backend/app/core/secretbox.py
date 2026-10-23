"""Keep a small secret (the SMTP password) in the database without storing it as readable text.

AES-GCM with a key derived from the server's JWT secret, so a copy of the database alone does not reveal it.
If the server secret is ever changed the stored value can no longer be opened: `unseal` then returns None and
the owner types the password again. Not for anything that must survive a secret rotation.
"""

import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import get_settings

_PREFIX = "v1:"
_CONTEXT = b"wcw-secretbox"


def _key() -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=_CONTEXT).derive(get_settings().jwt_secret.encode())


def seal(plain: str) -> str:
    nonce = os.urandom(12)
    return _PREFIX + base64.urlsafe_b64encode(nonce + AESGCM(_key()).encrypt(nonce, plain.encode(), _CONTEXT)).decode()


def unseal(token: str | None) -> str | None:
    if not token or not token.startswith(_PREFIX):
        return None
    try:
        raw = base64.urlsafe_b64decode(token[len(_PREFIX):].encode())
        return AESGCM(_key()).decrypt(raw[:12], raw[12:], _CONTEXT).decode()
    except (InvalidTag, ValueError):
        return None
