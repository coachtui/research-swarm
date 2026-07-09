"""Tests for execution/broker/credentials.py — Fernet round-trip + DB edge."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from cryptography.fernet import Fernet

from execution.broker.credentials import (
    CredentialsError,
    decrypt_secret,
    encrypt_secret,
    get_active_alpaca_account,
    upsert_alpaca_account,
)


@pytest.fixture
def fernet_env(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("BROKER_KEY_ENCRYPTION_KEY", key)
    return key


class TestEncryptDecrypt:
    def test_round_trip(self, fernet_env):
        ciphertext = encrypt_secret("PKTEST123")
        assert ciphertext != "PKTEST123"
        assert decrypt_secret(ciphertext) == "PKTEST123"

    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("BROKER_KEY_ENCRYPTION_KEY", raising=False)
        with pytest.raises(CredentialsError):
            encrypt_secret("PKTEST123")

    def test_invalid_ciphertext_raises_credentials_error(self, fernet_env):
        with pytest.raises(CredentialsError):
            decrypt_secret("not-a-valid-token")


class TestDbEdge:
    @pytest.mark.asyncio
    async def test_get_active_account_queries_alpaca_paper(self):
        db = MagicMock()
        db.linkedbrokeraccount.find_first = AsyncMock(return_value="row")
        assert await get_active_alpaca_account(db) == "row"
        db.linkedbrokeraccount.find_first.assert_awaited_once_with(
            where={"provider": "alpaca", "mode": "paper", "status": "active"}
        )

    @pytest.mark.asyncio
    async def test_upsert_encrypts_both_secrets(self, fernet_env):
        db = MagicMock()
        db.linkedbrokeraccount.upsert = AsyncMock(return_value="row")
        await upsert_alpaca_account(db, "user1", "key-abc", "secret-xyz")

        kwargs = db.linkedbrokeraccount.upsert.await_args.kwargs
        create = kwargs["data"]["create"]
        assert create["userId"] == "user1"
        assert create["apiKeyEncrypted"] != "key-abc"
        assert decrypt_secret(create["apiKeyEncrypted"]) == "key-abc"
        assert decrypt_secret(create["apiSecretEncrypted"]) == "secret-xyz"
        assert kwargs["where"] == {
            "userId_provider_mode": {
                "userId": "user1", "provider": "alpaca", "mode": "paper",
            }
        }
