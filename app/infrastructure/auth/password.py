"""Password hashing utilities."""

from __future__ import annotations

import secrets
from hashlib import pbkdf2_hmac

# Constants
HASH_ALGORITHM = "sha256"
ITERATIONS = 100_000
SALT_LENGTH = 32
HASH_LENGTH = 32


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256.

    Returns a string in format: algorithm$iterations$salt$hash
    """
    if not password:
        raise ValueError("Password cannot be empty")

    salt = secrets.token_bytes(SALT_LENGTH)
    hash_bytes = pbkdf2_hmac(
        HASH_ALGORITHM,
        password.encode("utf-8"),
        salt,
        ITERATIONS,
        dklen=HASH_LENGTH,
    )
    return f"{HASH_ALGORITHM}${ITERATIONS}${salt.hex()}${hash_bytes.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash."""
    if not password or not password_hash:
        return False

    try:
        parts = password_hash.split("$")
        if len(parts) != 4:
            return False

        algorithm, iterations_str, salt_hex, hash_hex = parts
        if algorithm != HASH_ALGORITHM:
            return False

        iterations = int(iterations_str)
        salt = bytes.fromhex(salt_hex)
        expected_hash = bytes.fromhex(hash_hex)

        computed_hash = pbkdf2_hmac(
            algorithm,
            password.encode("utf-8"),
            salt,
            iterations,
            dklen=len(expected_hash),
        )

        return secrets.compare_digest(computed_hash, expected_hash)
    except (ValueError, AttributeError):
        return False
