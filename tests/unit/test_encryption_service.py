"""Unit tests for encryption service."""

from __future__ import annotations

import pytest
from uuid import uuid4

from app.infrastructure.encryption.aes_gcm import AESGCMEncryptionService
from app.infrastructure.encryption.tenant_key import TenantKeyManager


class TestTenantKeyManager:
    """Tests for TenantKeyManager."""

    def test_derive_key_deterministic(self) -> None:
        manager = TenantKeyManager.from_secret("test-master-secret")
        tenant_id = uuid4()

        key1 = manager.derive_key(tenant_id)
        key2 = manager.derive_key(tenant_id)

        assert key1 == key2
        assert len(key1) == 32  # 256 bits

    def test_derive_key_different_tenants(self) -> None:
        manager = TenantKeyManager.from_secret("test-master-secret")

        key1 = manager.derive_key(uuid4())
        key2 = manager.derive_key(uuid4())

        assert key1 != key2

    def test_derive_key_different_secrets(self) -> None:
        manager1 = TenantKeyManager.from_secret("secret-one")
        manager2 = TenantKeyManager.from_secret("secret-two")
        tenant_id = uuid4()

        key1 = manager1.derive_key(tenant_id)
        key2 = manager2.derive_key(tenant_id)

        assert key1 != key2

    def test_rotate_key(self) -> None:
        manager = TenantKeyManager.from_secret("test-secret")
        tenant_id = uuid4()

        key1 = manager.derive_key(tenant_id)
        key2 = manager.rotate_key(tenant_id)

        assert key1 != key2
        assert len(key2) == 32

    def test_clear_cache_specific(self) -> None:
        manager = TenantKeyManager.from_secret("test-secret")
        tenant_id = uuid4()

        key1 = manager.derive_key(tenant_id)
        manager.clear_cache(tenant_id)
        key2 = manager.derive_key(tenant_id)

        # After clear, should re-derive (but same result with same inputs)
        assert key1 == key2

    def test_clear_cache_all(self) -> None:
        manager = TenantKeyManager.from_secret("test-secret")
        tenant_id1 = uuid4()
        tenant_id2 = uuid4()

        key1a = manager.derive_key(tenant_id1)
        key2a = manager.derive_key(tenant_id2)
        manager.clear_cache()
        key1b = manager.derive_key(tenant_id1)
        key2b = manager.derive_key(tenant_id2)

        assert key1a == key1b
        assert key2a == key2b


class TestAESGCMEncryptionService:
    """Tests for AESGCMEncryptionService."""

    def setup_method(self) -> None:
        self.encryption_service = AESGCMEncryptionService.from_secret("test-master-secret-32-bytes-long!!")
        self.tenant_id = uuid4()

    @pytest.mark.asyncio
    async def test_encrypt_decrypt_roundtrip(self) -> None:
        plaintext = "This is a secret message"

        ciphertext = await self.encryption_service.encrypt(plaintext, self.tenant_id)
        decrypted = await self.encryption_service.decrypt(ciphertext, self.tenant_id)

        assert decrypted == plaintext

    @pytest.mark.asyncio
    async def test_encrypt_produces_different_ciphertext(self) -> None:
        plaintext = "Same message"

        ct1 = await self.encryption_service.encrypt(plaintext, self.tenant_id)
        ct2 = await self.encryption_service.encrypt(plaintext, self.tenant_id)

        # Different nonces should produce different ciphertext
        assert ct1 != ct2

    @pytest.mark.asyncio
    async def test_decrypt_wrong_tenant_fails(self) -> None:
        plaintext = "Secret"
        ciphertext = await self.encryption_service.encrypt(plaintext, self.tenant_id)

        # Try to decrypt with different tenant
        with pytest.raises(Exception):
            await self.encryption_service.decrypt(ciphertext, uuid4())

    @pytest.mark.asyncio
    async def test_decrypt_tampered_ciphertext_fails(self) -> None:
        plaintext = "Secret"
        ciphertext = await self.encryption_service.encrypt(plaintext, self.tenant_id)

        # Tamper with ciphertext (change last char)
        tampered = ciphertext[:-1] + ("Z" if ciphertext[-1] != "Z" else "Y")

        with pytest.raises(Exception):
            await self.encryption_service.decrypt(tampered, self.tenant_id)

    @pytest.mark.asyncio
    async def test_encrypt_decrypt_bytes(self) -> None:
        plaintext = b"Binary data \x00\x01\x02"

        ciphertext = await self.encryption_service.encrypt_bytes(plaintext, self.tenant_id)
        decrypted = await self.encryption_service.decrypt_bytes(ciphertext, self.tenant_id)

        assert decrypted == plaintext

    @pytest.mark.asyncio
    async def test_empty_string(self) -> None:
        plaintext = ""

        ciphertext = await self.encryption_service.encrypt(plaintext, self.tenant_id)
        decrypted = await self.encryption_service.decrypt(ciphertext, self.tenant_id)

        assert decrypted == ""

    @pytest.mark.asyncio
    async def test_unicode_content(self) -> None:
        plaintext = "Hello 世界 🌍 café"

        ciphertext = await self.encryption_service.encrypt(plaintext, self.tenant_id)
        decrypted = await self.encryption_service.decrypt(ciphertext, self.tenant_id)

        assert decrypted == plaintext

    @pytest.mark.asyncio
    async def test_long_content(self) -> None:
        plaintext = "x" * 10000

        ciphertext = await self.encryption_service.encrypt(plaintext, self.tenant_id)
        decrypted = await self.encryption_service.decrypt(ciphertext, self.tenant_id)

        assert decrypted == plaintext