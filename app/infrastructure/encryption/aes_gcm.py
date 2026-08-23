"""AES-256-GCM encryption implementation."""

from __future__ import annotations

import base64
import logging
import os
from uuid import UUID

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.infrastructure.encryption.base import EncryptionError, EncryptionService
from app.infrastructure.encryption.tenant_key import TenantKeyManager

logger = logging.getLogger(__name__)


class AESGCMEncryptionService(EncryptionService):
    """AES-256-GCM encryption service with tenant-specific keys."""

    def __init__(self, key_manager: TenantKeyManager) -> None:
        """Initialize encryption service.

        Args:
            key_manager: Tenant key manager for key derivation
        """
        self._key_manager = key_manager

    async def encrypt(self, plaintext: str, tenant_id: UUID) -> str:
        """Encrypt plaintext for a tenant.

        Args:
            plaintext: The text to encrypt
            tenant_id: The tenant ID for key selection

        Returns:
            Base64-encoded ciphertext with nonce

        Raises:
            EncryptionError: If encryption fails
        """
        try:
            # Get tenant-specific key
            key = self._key_manager.derive_key(tenant_id)

            # Generate random nonce (96 bits for GCM)
            nonce = os.urandom(12)

            # Encrypt
            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)

            # Combine nonce and ciphertext
            combined = nonce + ciphertext

            # Base64 encode
            return base64.b64encode(combined).decode("utf-8")

        except Exception as e:
            logger.error(f"Encryption failed for tenant {tenant_id}: {e}")
            raise EncryptionError(f"Encryption failed: {e}") from e

    async def decrypt(self, ciphertext: str, tenant_id: UUID) -> str:
        """Decrypt ciphertext for a tenant.

        Args:
            ciphertext: Base64-encoded ciphertext with nonce
            tenant_id: The tenant ID for key selection

        Returns:
            Decrypted plaintext

        Raises:
            EncryptionError: If decryption fails
        """
        try:
            # Get tenant-specific key
            key = self._key_manager.derive_key(tenant_id)

            # Base64 decode
            combined = base64.b64decode(ciphertext.encode("utf-8"))

            # Extract nonce (first 12 bytes) and ciphertext
            nonce = combined[:12]
            actual_ciphertext = combined[12:]

            # Decrypt
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, actual_ciphertext, None)

            return plaintext.decode("utf-8")

        except Exception as e:
            logger.error(f"Decryption failed for tenant {tenant_id}: {e}")
            raise EncryptionError(f"Decryption failed: {e}") from e

    async def encrypt_bytes(self, plaintext: bytes, tenant_id: UUID) -> bytes:
        """Encrypt bytes for a tenant.

        Args:
            plaintext: The bytes to encrypt
            tenant_id: The tenant ID for key selection

        Returns:
            Encrypted ciphertext with nonce

        Raises:
            EncryptionError: If encryption fails
        """
        try:
            # Get tenant-specific key
            key = self._key_manager.derive_key(tenant_id)

            # Generate random nonce
            nonce = os.urandom(12)

            # Encrypt
            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(nonce, plaintext, None)

            # Combine nonce and ciphertext
            return nonce + ciphertext

        except Exception as e:
            logger.error(f"Bytes encryption failed for tenant {tenant_id}: {e}")
            raise EncryptionError(f"Bytes encryption failed: {e}") from e

    async def decrypt_bytes(self, ciphertext: bytes, tenant_id: UUID) -> bytes:
        """Decrypt bytes for a tenant.

        Args:
            ciphertext: The encrypted bytes with nonce
            tenant_id: The tenant ID for key selection

        Returns:
            Decrypted plaintext bytes

        Raises:
            EncryptionError: If decryption fails
        """
        try:
            # Get tenant-specific key
            key = self._key_manager.derive_key(tenant_id)

            # Extract nonce and ciphertext
            nonce = ciphertext[:12]
            actual_ciphertext = ciphertext[12:]

            # Decrypt
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, actual_ciphertext, None)

            return plaintext

        except Exception as e:
            logger.error(f"Bytes decryption failed for tenant {tenant_id}: {e}")
            raise EncryptionError(f"Bytes decryption failed: {e}") from e

    @classmethod
    def from_secret(cls, secret: str) -> "AESGCMEncryptionService":
        """Create encryption service from a master secret.

        Args:
            secret: The master secret for key derivation

        Returns:
            Configured encryption service
        """
        key_manager = TenantKeyManager.from_secret(secret)
        return cls(key_manager=key_manager)
