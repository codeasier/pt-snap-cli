"""Tests for the MCP server module."""

import sqlite3
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def valid_db() -> Path:
    """Create a valid test database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE dictionary (" "`table` TEXT, `column` TEXT, `key` TEXT, `value` TEXT)"
    )
    conn.execute(
        "CREATE TABLE trace_entry_0 ("
        "id INTEGER PRIMARY KEY, action INTEGER, address INTEGER, "
        "size INTEGER, stream INTEGER, allocated INTEGER, "
        "active INTEGER, reserved INTEGER, callstack TEXT)"
    )
    conn.execute(
        "CREATE TABLE block_0 ("
        "id INTEGER PRIMARY KEY, address INTEGER, size INTEGER, "
        "requestedSize INTEGER, state INTEGER, allocEventId INTEGER, "
        "freeEventId INTEGER)"
    )
    conn.commit()
    conn.close()

    yield db_path
    db_path.unlink(missing_ok=True)


@pytest.fixture(autouse=True)
def _reset_registry():
    """Reset the query registry singleton between tests."""
    from pt_snap_cli.query.registry import QueryRegistry

    QueryRegistry.reset()


@pytest.fixture(autouse=True)
def _fresh_analyzer():
    """Reset the module-level _analyzer for each test."""
    import pt_snap_cli.mcp.server as server_mod

    yield

    # Reset the analyzer so it doesn't hold stale state
    server_mod._analyzer = type(server_mod._analyzer)()


class TestMCPServerStructure:
    """Test that the MCP server is properly structured."""

    def test_mcp_server_is_fastmcp(self) -> None:
        """Verify MCP server is a FastMCP instance."""
        from mcp.server.fastmcp import FastMCP

        from pt_snap_cli.mcp.server import mcp

        assert isinstance(mcp, FastMCP)

    def test_mcp_server_name(self) -> None:
        """Verify MCP server has correct name."""
        from pt_snap_cli.mcp.server import mcp

        assert mcp.name == "pt-snap"

    def test_mcp_server_has_tool_decorator(self) -> None:
        """Verify MCP server has tool decorator."""
        from pt_snap_cli.mcp.server import mcp

        assert hasattr(mcp, "tool")

    def test_mcp_server_has_resource_decorator(self) -> None:
        """Verify MCP server has resource decorator."""
        from pt_snap_cli.mcp.server import mcp

        assert hasattr(mcp, "resource")

    def test_mcp_server_has_prompt_decorator(self) -> None:
        """Verify MCP server has prompt decorator."""
        from pt_snap_cli.mcp.server import mcp

        assert hasattr(mcp, "prompt")


class TestMCPToolFunctions:
    """Test MCP tool functions through the analyzer layer."""

    def test_get_focus_returns_dict(self, valid_db: Path) -> None:
        """Test get_focus returns proper dict structure."""
        from pt_snap_cli.api import SnapshotAnalyzer

        analyzer = SnapshotAnalyzer(db_path=valid_db)
        state = analyzer.get_focus()
        # MCP wrapper converts to dict
        result = {
            "db_path": state.db_path,
            "device_id": state.device_id,
            "source": state.source,
            "available_devices": state.available_devices,
        }
        assert isinstance(result, dict)
        assert result["db_path"] == str(valid_db)
        assert result["source"] == "explicit"

    def test_set_focus_returns_dict(self, valid_db: Path) -> None:
        """Test set_focus returns proper dict structure."""
        from pt_snap_cli.api import SnapshotAnalyzer

        analyzer = SnapshotAnalyzer()
        state = analyzer.set_focus(db_path=str(valid_db))
        result = {
            "db_path": state.db_path,
            "device_id": state.device_id,
            "available_devices": state.available_devices,
        }
        assert isinstance(result, dict)
        assert result["db_path"] == str(valid_db)

    def test_list_templates_returns_list(self) -> None:
        """Test list_templates returns a list of dicts."""
        from pt_snap_cli.api import SnapshotAnalyzer

        analyzer = SnapshotAnalyzer()
        result = analyzer.list_templates()
        assert isinstance(result, list)
        if result:
            assert "name" in result[0]
            assert "description" in result[0]

    def test_get_template_info(self) -> None:
        """Test get_template_info returns template details."""
        from pt_snap_cli.api import SnapshotAnalyzer

        analyzer = SnapshotAnalyzer()
        info = analyzer.get_template_info("leak_detection")
        assert info is not None
        assert "name" in info
        assert "parameters" in info

    def test_get_template_info_not_found(self) -> None:
        """Test get_template_info handles missing template."""
        from pt_snap_cli.api import SnapshotAnalyzer

        analyzer = SnapshotAnalyzer()
        info = analyzer.get_template_info("does_not_exist")
        assert info is None

    def test_execute_query_returns_dict(self, valid_db: Path) -> None:
        """Test execute_query returns proper dict structure."""
        from pt_snap_cli.api import SnapshotAnalyzer

        analyzer = SnapshotAnalyzer(db_path=valid_db)
        result = analyzer.execute_query("leak_detection", max_rows=10)
        assert isinstance(result, dict)
        assert "total" in result
        assert "returned" in result
        assert "device_id" in result
        assert "rows" in result


class TestMCPEntryPoint:
    """Test the MCP server entry point."""

    def test_main_function_exists(self) -> None:
        """Verify main() function is defined."""
        from pt_snap_cli.mcp.server import main

        assert callable(main)
