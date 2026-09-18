"""Tests for package initialization and published metadata."""

from __future__ import annotations

import importlib
from importlib.metadata import distribution, requires, version
from pathlib import Path

import pytest

from pt_snap_cli import __version__

ROOT = Path(__file__).resolve().parents[1]


def _runtime_requirement_names() -> set[str]:
    names: set[str] = set()
    for req in requires("pt-snap-cli") or []:
        name_part, _, marker = req.partition(";")
        if "extra" in marker:
            continue
        name = name_part.split("[", 1)[0]
        for sep in (">", "<", "=", "!"):
            name = name.split(sep, 1)[0]
        names.add(name.strip().lower())
    return names


class TestPackage:
    """Test package initialization."""

    def test_version(self) -> None:
        """Test version is defined."""
        assert __version__ == version("pt-snap-cli")

    def test_version_format(self) -> None:
        """Test version string is not the fallback value."""
        assert __version__ != "0.0.0-dev"

    def test_console_scripts_are_cli_only(self) -> None:
        names = {
            ep.name
            for ep in distribution("pt-snap-cli").entry_points
            if ep.group == "console_scripts"
        }
        assert names == {"pt-snap"}

    def test_runtime_dependencies_exclude_mcp_stack(self) -> None:
        names = _runtime_requirement_names()
        assert names.isdisjoint({"mcp", "starlette", "uvicorn"})

    def test_pyproject_does_not_declare_mcp(self) -> None:
        text = (ROOT / "pyproject.toml").read_text()
        assert "pt-snap-mcp" not in text
        assert "mcp>=" not in text

    def test_mcp_package_is_removed(self) -> None:
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("pt_snap_cli.mcp")
