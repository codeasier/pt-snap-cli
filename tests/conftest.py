"""Test configuration."""

import pytest

from tests._fixture_provenance import FixtureProvenanceError, verify_snapshot_fixtures


def pytest_sessionstart(session: pytest.Session) -> None:
    """Stop before collection can execute a changed or unreviewed pickle."""
    try:
        verify_snapshot_fixtures()
    except FixtureProvenanceError as exc:
        pytest.exit(f"Executable fixture provenance check failed: {exc}", returncode=4)


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest."""
    config.addinivalue_line("markers", "slow: mark test as slow")
