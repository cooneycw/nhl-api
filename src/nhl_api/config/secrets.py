"""AWS Secrets Manager integration for credential retrieval.

This module provides secure access to database credentials and other secrets
stored in AWS Secrets Manager. It uses caching to minimize API calls.

Usage:
    from nhl_api.config.secrets import get_db_credentials

    creds = get_db_credentials()
    # Returns: {'host': '...', 'port': '...', 'database': '...', ...}
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import boto3
from botocore.exceptions import ClientError


@dataclass(frozen=True)
class DatabaseCredentials:
    """PostgreSQL database connection credentials."""

    host: str
    port: int
    database: str
    username: str
    password: str

    @property
    def connection_string(self) -> str:
        """Return asyncpg-compatible connection string."""
        return (
            f"postgresql://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
        )

    @property
    def dsn(self) -> dict[str, Any]:
        """Return connection parameters as a dict for asyncpg.connect()."""
        return {
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.username,
            "password": self.password,
        }


class SecretsManagerError(Exception):
    """Raised when secrets cannot be retrieved from AWS Secrets Manager."""

    pass


def _get_secrets_client() -> boto3.client:
    """Create boto3 Secrets Manager client.

    Uses credentials from environment variables or IAM role.
    """
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    return boto3.client("secretsmanager", region_name=region)


@lru_cache(maxsize=1)
def get_db_credentials(secret_id: str | None = None) -> DatabaseCredentials:
    """Retrieve database credentials from AWS Secrets Manager.

    Args:
        secret_id: The secret name/ARN. Defaults to NHL_DB_SECRET_ID env var
                   or 'nhl-api'.

    Returns:
        DatabaseCredentials dataclass with connection info.

    Raises:
        SecretsManagerError: If secret cannot be retrieved or parsed.

    Example:
        >>> creds = get_db_credentials()
        >>> creds.host
        '192.168.1.100'
        >>> creds.connection_string
        'postgresql://user:pass@host:5432/nhl_api'
    """
    if secret_id is None:
        secret_id = os.getenv("NHL_DB_SECRET_ID", "nhl-api")

    try:
        client = _get_secrets_client()
        response = client.get_secret_value(SecretId=secret_id)
        secret_string = response["SecretString"]
        secret_data = json.loads(secret_string)
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        raise SecretsManagerError(
            f"Failed to retrieve secret '{secret_id}': {error_code}"
        ) from e
    except json.JSONDecodeError as e:
        raise SecretsManagerError(f"Secret '{secret_id}' contains invalid JSON") from e

    # Map secret keys to our credential format
    # Supports both POSTGRES_* and standard naming conventions
    try:
        return DatabaseCredentials(
            host=secret_data.get("POSTGRES_HOST", secret_data.get("host", "")),
            port=int(secret_data.get("POSTGRES_PORT", secret_data.get("port", 5432))),
            database=secret_data.get("POSTGRES_DB", secret_data.get("database", "")),
            username=secret_data.get("POSTGRES_USER", secret_data.get("username", "")),
            password=secret_data.get(
                "POSTGRES_PASSWORD", secret_data.get("password", "")
            ),
        )
    except (KeyError, ValueError) as e:
        raise SecretsManagerError(
            f"Secret '{secret_id}' is missing required fields: {e}"
        ) from e


def clear_credentials_cache() -> None:
    """Clear the cached credentials.

    Useful when credentials have been rotated and need to be refreshed.
    """
    get_db_credentials.cache_clear()


# Convenience function for getting raw secret data
@lru_cache(maxsize=8)
def get_secret(secret_id: str) -> dict[str, Any]:
    """Retrieve any secret from AWS Secrets Manager as a dictionary.

    Args:
        secret_id: The secret name or ARN.

    Returns:
        Dictionary containing the secret data.

    Raises:
        SecretsManagerError: If secret cannot be retrieved or parsed.
    """
    try:
        client = _get_secrets_client()
        response = client.get_secret_value(SecretId=secret_id)
        result: dict[str, Any] = json.loads(response["SecretString"])
        return result
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        raise SecretsManagerError(
            f"Failed to retrieve secret '{secret_id}': {error_code}"
        ) from e
    except json.JSONDecodeError as e:
        raise SecretsManagerError(f"Secret '{secret_id}' contains invalid JSON") from e
