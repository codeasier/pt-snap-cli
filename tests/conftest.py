"""Test configuration."""

import gc
from functools import wraps

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


@pytest.fixture
def owned_service_instances(request, monkeypatch):
    """Own services constructed directly by an opted-in test module.

    Only replace that test module's imported constructor bindings. Production
    constructors (including CLI-owned services) and lifecycle tests are untouched.
    Each successful construction registers its public close method immediately,
    including when the test later raises. Do not use in resource-lifetime tests.
    """

    def managed_factory(constructor):
        @wraps(constructor)
        def create(*args, **kwargs):
            instance = constructor(*args, **kwargs)
            request.addfinalizer(instance.close)
            return instance

        return create

    for name in ("SnapshotAnalyzer", "QueryService", "OverviewService", "ReportService"):
        constructor = getattr(request.module, name, None)
        if constructor is not None:
            monkeypatch.setattr(request.module, name, managed_factory(constructor))


@pytest.fixture(autouse=True)
def collect_test_resources():
    """Attribute cyclic-resource warnings to their owning test, not a later one."""
    yield
    gc.collect()
