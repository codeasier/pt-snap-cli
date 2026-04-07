"""Tests for package initialization."""

from pt_snap_cli import __version__


class TestPackage:
    """Test package initialization."""

    def test_version(self) -> None:
        """Test version is defined."""
        assert __version__ == "0.1.0"
