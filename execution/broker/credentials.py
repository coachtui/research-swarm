"""Encrypt/decrypt broker API credentials and load linked accounts.

Secrets are encrypted at rest with Fernet (symmetric). The Fernet key lives
ONLY in the BROKER_KEY_ENCRYPTION_KEY env var — never in the database, never
in an Inngest step result.
"""
import os
from datetime import datetime, timezone
from typing import Any, Optional


class CredentialsError(Exception):
    """Encryption key missing or ciphertext invalid."""


def _fernet():
    from cryptography.fernet import Fernet  # lazy — runtime dep

    key = os.getenv("BROKER_KEY_ENCRYPTION_KEY", "")
    if not key:
        raise CredentialsError("BROKER_KEY_ENCRYPTION_KEY not set")
    return Fernet(key.encode())


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except Exception as exc:
        raise CredentialsError("invalid ciphertext") from exc


async def get_active_alpaca_account(db) -> Optional[Any]:
    """The single active linked Alpaca paper account row, or None."""
    return await db.linkedbrokeraccount.find_first(
        where={"provider": "alpaca", "mode": "paper", "status": "active"}
    )


async def upsert_alpaca_account(db, user_id: str, api_key: str, api_secret: str) -> Any:
    payload = {
        "apiKeyEncrypted": encrypt_secret(api_key),
        "apiSecretEncrypted": encrypt_secret(api_secret),
        "status": "active",
        "lastVerifiedAt": datetime.now(timezone.utc),
    }
    return await db.linkedbrokeraccount.upsert(
        where={
            "userId_provider_mode": {
                "userId": user_id, "provider": "alpaca", "mode": "paper",
            }
        },
        data={
            "create": {"userId": user_id, "provider": "alpaca", "mode": "paper", **payload},
            "update": dict(payload),
        },
    )
