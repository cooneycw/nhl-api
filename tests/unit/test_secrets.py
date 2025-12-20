"""Unit tests for AWS Secrets Manager integration."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from nhl_api.config.secrets import (
    DatabaseCredentials,
    SecretsManagerError,
    clear_credentials_cache,
    get_db_credentials,
    get_secret,
)


@pytest.fixture
def mock_secret_data() -> dict[str, str]:
    """Sample secret data matching AWS structure."""
    return {
        "POSTGRES_HOST": "192.168.1.100",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "nhl_api",
        "POSTGRES_USER": "nhl_user",
        "POSTGRES_PASSWORD": "secret123",
    }


@pytest.fixture
def mock_boto_client(mock_secret_data: dict[str, str]) -> MagicMock:
    """Mock boto3 Secrets Manager client."""
    client = MagicMock()
    client.get_secret_value.return_value = {
        "SecretString": json.dumps(mock_secret_data)
    }
    return client


class TestDatabaseCredentials:
    """Tests for DatabaseCredentials dataclass."""

    def test_connection_string(self) -> None:
        """Test connection string generation."""
        creds = DatabaseCredentials(
            host="localhost",
            port=5432,
            database="testdb",
            username="user",
            password="pass",
        )
        assert creds.connection_string == "postgresql://user:pass@localhost:5432/testdb"

    def test_dsn_dict(self) -> None:
        """Test DSN dictionary for asyncpg."""
        creds = DatabaseCredentials(
            host="localhost",
            port=5432,
            database="testdb",
            username="user",
            password="pass",
        )
        dsn = creds.dsn
        assert dsn["host"] == "localhost"
        assert dsn["port"] == 5432
        assert dsn["database"] == "testdb"
        assert dsn["user"] == "user"
        assert dsn["password"] == "pass"

    def test_immutable(self) -> None:
        """Test that credentials are immutable (frozen dataclass)."""
        creds = DatabaseCredentials(
            host="localhost",
            port=5432,
            database="testdb",
            username="user",
            password="pass",
        )
        with pytest.raises(AttributeError):
            creds.host = "newhost"  # type: ignore[misc]


class TestGetDbCredentials:
    """Tests for get_db_credentials function."""

    def test_retrieves_credentials(
        self, mock_boto_client: MagicMock, mock_secret_data: dict[str, str]
    ) -> None:
        """Test successful credential retrieval."""
        # Clear cache before test
        clear_credentials_cache()

        with patch(
            "nhl_api.config.secrets._get_secrets_client",
            return_value=mock_boto_client,
        ):
            creds = get_db_credentials("test-secret")

        assert creds.host == mock_secret_data["POSTGRES_HOST"]
        assert creds.port == int(mock_secret_data["POSTGRES_PORT"])
        assert creds.database == mock_secret_data["POSTGRES_DB"]
        assert creds.username == mock_secret_data["POSTGRES_USER"]
        assert creds.password == mock_secret_data["POSTGRES_PASSWORD"]

    def test_caches_result(self, mock_boto_client: MagicMock) -> None:
        """Test that credentials are cached."""
        clear_credentials_cache()

        with patch(
            "nhl_api.config.secrets._get_secrets_client",
            return_value=mock_boto_client,
        ):
            creds1 = get_db_credentials("test-secret-cache")
            creds2 = get_db_credentials("test-secret-cache")

        # Should only call get_secret_value once due to caching
        assert mock_boto_client.get_secret_value.call_count == 1
        assert creds1 is creds2

    def test_handles_client_error(self) -> None:
        """Test handling of AWS client errors."""
        from botocore.exceptions import ClientError

        clear_credentials_cache()

        mock_client = MagicMock()
        mock_client.get_secret_value.side_effect = ClientError(
            {"Error": {"Code": "ResourceNotFoundException"}},
            "GetSecretValue",
        )

        with patch(
            "nhl_api.config.secrets._get_secrets_client",
            return_value=mock_client,
        ):
            with pytest.raises(SecretsManagerError) as exc_info:
                get_db_credentials("nonexistent-secret")

        assert "ResourceNotFoundException" in str(exc_info.value)

    def test_handles_invalid_json(self) -> None:
        """Test handling of invalid JSON in secret."""
        clear_credentials_cache()

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {"SecretString": "not valid json"}

        with patch(
            "nhl_api.config.secrets._get_secrets_client",
            return_value=mock_client,
        ):
            with pytest.raises(SecretsManagerError) as exc_info:
                get_db_credentials("invalid-json-secret")

        assert "invalid JSON" in str(exc_info.value)


class TestGetSecret:
    """Tests for generic get_secret function."""

    def test_retrieves_any_secret(self) -> None:
        """Test retrieving arbitrary secret data."""

        # Clear cache
        get_secret.cache_clear()

        mock_client = MagicMock()
        mock_client.get_secret_value.return_value = {
            "SecretString": json.dumps({"api_key": "secret123", "enabled": True})
        }

        with patch(
            "nhl_api.config.secrets._get_secrets_client",
            return_value=mock_client,
        ):
            secret = get_secret("generic-secret")

        assert secret["api_key"] == "secret123"
        assert secret["enabled"] is True


class TestClearCredentialsCache:
    """Tests for cache clearing."""

    def test_clears_cache(self, mock_boto_client: MagicMock) -> None:
        """Test that clearing cache causes fresh retrieval."""
        clear_credentials_cache()

        with patch(
            "nhl_api.config.secrets._get_secrets_client",
            return_value=mock_boto_client,
        ):
            # First call
            get_db_credentials("cache-test")
            assert mock_boto_client.get_secret_value.call_count == 1

            # Clear cache
            clear_credentials_cache()

            # Second call should hit API again
            get_db_credentials("cache-test")
            assert mock_boto_client.get_secret_value.call_count == 2
