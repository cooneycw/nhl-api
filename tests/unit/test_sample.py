"""Sample tests to verify pytest configuration."""

import pytest

import nhl_api


@pytest.mark.unit
def test_version_exists() -> None:
    """Verify that the package version is defined."""
    assert hasattr(nhl_api, "__version__")


@pytest.mark.unit
def test_version_format() -> None:
    """Verify that the version follows semantic versioning format."""
    version = nhl_api.__version__
    parts = version.split(".")
    assert len(parts) == 3, "Version should have 3 parts (major.minor.patch)"
    assert all(part.isdigit() for part in parts), "Version parts should be numeric"


@pytest.mark.unit
def test_package_docstring() -> None:
    """Verify that the package has a docstring."""
    assert nhl_api.__doc__ is not None
    assert len(nhl_api.__doc__) > 0
