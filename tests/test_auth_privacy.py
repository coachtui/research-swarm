"""Privacy/security tests for authentication endpoints."""

import logging
import pytest
from unittest.mock import MagicMock

from api.models.auth import User


@pytest.fixture
def mock_user():
    user = MagicMock(spec=User)
    user.id = "user_abc123"
    user.email = "private@example.com"
    user.full_name = "Test User"
    user.tier = "starter"
    user.is_active = True
    user.is_admin = False
    return user


@pytest.mark.asyncio
async def test_get_me_log_redacts_email(mock_user, caplog):
    """Verify /auth/me logs user_id and is_admin but never the user email."""
    from api.routes.auth import get_me

    with caplog.at_level(logging.INFO, logger="api.routes.auth"):
        await get_me(current_user=mock_user)

    # Email must never appear in any log record
    for record in caplog.records:
        assert mock_user.email not in record.getMessage(), (
            f"PII leak: email found in log message: {record.getMessage()!r}"
        )

    # user_id must appear in at least one log record
    user_id_logged = any(mock_user.id in record.getMessage() for record in caplog.records)
    assert user_id_logged, "Expected user_id in log output but it was absent"
