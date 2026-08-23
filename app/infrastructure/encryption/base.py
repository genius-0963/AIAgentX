"""Encryption service base protocols."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID


class EncryptionError(Exception):
    """Exception raised when encryption operations fail."""

    pass


class EncryptionService(Protocol):
    """Protocol for encryption/decryption operations."""

    async def encrypt(self, plaintext: str, tenant_id: UUID) -> str:
        """Encrypt plaintext for a tenant.

        Args:
            plaintext: The text to encrypt
            tenant_id: The tenant ID for key selection

        Returns:
            Encrypted ciphertext (base64 encoded)

        Raises:
            EncryptionError: If encryption fails
        """
        ...

    async def decrypt(self, ciphertext: str, tenant_id: UUID) -> str:
        """Decrypt ciphertext for a tenant.

        Args:
            ciphertext: The encrypted text (base64 encoded)
            tenant_id: The tenant ID for key selection

        Returns:
            Decrypted plaintext

        Raises:
            EncryptionError: If decryption fails
        """
        ...

    async def encrypt_bytes(self, plaintext: bytes, tenant_id: UUID) -> bytes:
        """Encrypt bytes for a tenant.

        Args:
            plaintext: The bytes to encrypt
            tenant_id: The tenant ID for key selection

        Returns:
            Encrypted ciphertext

        Raises:
            EncryptionError: If encryption fails
        """
        ...

    async def decrypt_bytes(self, ciphertext: bytes, tenant_id: UUID) -> bytes:
        """Decrypt bytes for a tenant.

        Args:
            ciphertext: The encrypted bytes
            tenant_id: The tenant ID for key selection

        Returns:
            Decrypted plaintext bytes

        Raises:
            EncryptionError: If decryption fails
        """
        ...
