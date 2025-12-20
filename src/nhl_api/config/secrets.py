"""AWS Secrets Manager integration for credential retrieval.

This module provides secure access to database credentials and other secrets
stored in AWS Secrets Manager. It uses caching to minimize API calls.

Supports two modes:
1. AWS Secrets Manager (production) - Fetches credentials from AWS
2. Direct environment variables (local dev) - Uses DB_* env vars from .env

The module automatically loads environment variables from .env file if present.

Usage:
    from nhl_api.config.secrets import get_db_credentials

    creds = get_db_credentials()
    # Returns: {'host': '...', 'port': '...', 'database': '...', ...}
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load .env file from project root (searches up from current directory)
_env_path = Path(__file__).resolve().parents[3] / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
    logger.debug(f"Loaded environment from {_env_path}")


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


def _get_credentials_from_env() -> DatabaseCredentials | None:
    """Try to get database credentials from environment variables.

    Looks for DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD.
    Returns None if required variables are not set.
    """
    host = os.getenv("DB_HOST")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    database = os.getenv("DB_NAME", os.getenv("DB_DATABASE"))

    if all([host, user, password, database]):
        logger.info("Using database credentials from environment variables")
        # All values are verified non-None by the all() check above
        assert host is not None
        assert user is not None
        assert password is not None
        assert database is not None
        return DatabaseCredentials(
            host=host,
            port=int(os.getenv("DB_PORT", "5432")),
            database=database,
            username=user,
            password=password,
        )
    return None


def _get_credentials_from_aws(secret_id: str) -> DatabaseCredentials:
    """Retrieve database credentials from AWS Secrets Manager."""
    try:
        client = _get_secrets_client()
        response = client.get_secret_value(SecretId=secret_id)
        secret_string = response["SecretString"]
        secret_data = json.loads(secret_string)
    except NoCredentialsError as e:
        raise SecretsManagerError(
            "AWS credentials not found. Set AWS_ACCESS_KEY_ID and "
            "AWS_SECRET_ACCESS_KEY in .env file, or use DB_* variables for local dev."
        ) from e
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


@lru_cache(maxsize=1)
def get_db_credentials(secret_id: str | None = None) -> DatabaseCredentials:
    """Retrieve database credentials.

    Tries sources in order:
    1. Direct environment variables (DB_HOST, DB_USER, DB_PASSWORD, DB_NAME)
    2. AWS Secrets Manager (using NHL_DB_SECRET_ID or provided secret_id)

    Args:
        secret_id: The secret name/ARN. Defaults to NHL_DB_SECRET_ID env var
                   or 'nhl-api'. Only used if env vars not set.

    Returns:
        DatabaseCredentials dataclass with connection info.

    Raises:
        SecretsManagerError: If credentials cannot be retrieved.

    Example:
        >>> creds = get_db_credentials()
        >>> creds.host
        '192.168.1.100'
        >>> creds.connection_string
        'postgresql://user:pass@host:5432/nhl_api'
    """
    # First try direct environment variables (for local development)
    env_creds = _get_credentials_from_env()
    if env_creds is not None:
        return env_creds

    # Fall back to AWS Secrets Manager
    if secret_id is None:
        secret_id = os.getenv("NHL_DB_SECRET_ID", "nhl-api")

    logger.info(f"Fetching credentials from AWS Secrets Manager: {secret_id}")
    return _get_credentials_from_aws(secret_id)


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
