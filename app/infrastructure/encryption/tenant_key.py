"""Tenant-specific key management for encryption."""

from __future__ import annotations

import hashlib
import logging
from uuid import UUID

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.infrastructure.encryption.base import EncryptionError

logger = logging.getLogger(__name__)


class TenantKeyManager:
    """Manages tenant-specific encryption keys derived from a master secret."""

    def __init__(self, master_secret: str) -> None:
        """Initialize tenant key manager.

        Args:
            master_secret: Master secret for key derivation (should be from secure config)
        """
        self._master_secret = master_secret.encode()
        self._key_cache: dict[UUID, bytes] = {}

    def derive_key(self, tenant_id: UUID) -> bytes:
        """Derive encryption key for a tenant.

        Args:
            tenant_id: The tenant ID

        Returns:
            32-byte encryption key

        Raises:
            EncryptionError: If key derivation fails
        """
        # Check cache first
        if tenant_id in self._key_cache:
            return self._key_cache[tenant_id]

        try:
            # Derive key using HKDF
            hkdf = HKDF(
                algorithm=hashes.SHA256(),
                length=32,  # 256 bits for AES-256
                salt=self._master_secret[:16],  # Use first 16 bytes as salt
                info=tenant_id.bytes,
            )

            key = hkdf.derive(self._master_secret)

            # Cache the key
            self._key_cache[tenant_id] = key

            logger.debug(f"Derived encryption key for tenant {tenant_id}")
            return key

        except Exception as e:
            logger.error(f"Failed to derive key for tenant {tenant_id}: {e}")
            raise EncryptionError(f"Key derivation failed: {e}") from e

    def rotate_key(self, tenant_id: UUID) -> bytes:
        """Rotate the encryption key for a tenant.

        Args:
            tenant_id: The tenant ID

        Returns:
            New 32-byte encryption key
        """
        # Remove from cache to force re-derivation
        if tenant_id in self._key_cache:
            del self._key_cache[tenant_id]

        # Derive new key
        return self.derive_key(tenant_id)

    def clear_cache(self, tenant_id: UUID | None = None) -> None:
        """Clear cached keys.

        Args:
            tenant_id: Specific tenant ID to clear, or None to clear all
        """
        if tenant_id:
            self._key_cache.pop(tenant_id, None)
        else:
            self._key_cache.clear()

    @classmethod
    def from_secret(cls, secret: str) -> "TenantKeyManager":
        """Create key manager from a secret.

        Args:
            secret: The master secret

        Returns:
            Configured tenant key manager
        """
        return cls(master_secret=secret)
