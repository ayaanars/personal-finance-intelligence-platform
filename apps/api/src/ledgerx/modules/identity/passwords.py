"""Credential hashing and random-token primitives; no transport or persistence."""

import hashlib
import re
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from argon2.profiles import RFC_9106_LOW_MEMORY


class Passwords:
    def __init__(self) -> None:
        self.hasher = PasswordHasher.from_parameters(RFC_9106_LOW_MEMORY)
        # Equal-cost verification for unknown users; generated once per application.
        self.dummy_hash = self.hash(secrets.token_urlsafe(32))

    def hash(self, password: str) -> str:
        return self.hasher.hash(password)

    def verify(self, encoded: str | None, password: str) -> bool:
        try:
            valid = self.hasher.verify(encoded or self.dummy_hash, password)
            return valid and encoded is not None
        except (VerificationError, InvalidHashError):
            return False


def new_secret() -> str:
    return secrets.token_urlsafe(32)


def secret_hash(secret: str) -> bytes:
    return hashlib.sha256(secret.encode("ascii")).digest()


def valid_secret(secret: str | None) -> bool:
    return secret is not None and re.fullmatch(r"[A-Za-z0-9_-]{43}", secret) is not None
