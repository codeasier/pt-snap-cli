"""Version information for pt-snap-cli."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("pt-snap-cli")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"
