"""Tests for package initialization."""

from importlib.metadata import version

from pt_snap_cli import __version__


class TestPackage:
    """Test package initialization."""

    def test_version(self) -> None:
        """Test version is defined."""
        assert __version__ == version("pt-snap-cli")

    def test_version_format(self) -> None:
        """Test version string is not the fallback value."""
        assert __version__ != "0.0.0-dev"
