"""MCP server for pt-snap-cli."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from pt_snap_cli.api import SnapshotAnalyzer

mcp = FastMCP(
    "pt-snap",
    instructions="PyTorch Memory Snapshot Analysis",
)

_analyzer = SnapshotAnalyzer()


@mcp.tool()
def get_focus() -> dict[str, Any]:
    """Get the current analysis focus (database path and device)."""
    state = _analyzer.get_focus()
    return {
        "db_path": state.db_path,
        "device_id": state.device_id,
        "source": state.source,
        "available_devices": state.available_devices,
    }


@mcp.tool()
def set_focus(db_path: str | None = None, device_id: int | None = None) -> dict[str, Any]:
    """Set the analysis focus to a specific database and optional device.

    Use this before running queries to point to the correct snapshot file.
    """
    state = _analyzer.set_focus(db_path, device_id)
    return {
        "db_path": state.db_path,
        "device_id": state.device_id,
        "available_devices": state.available_devices,
    }


@mcp.tool()
def list_templates(category: str | None = None) -> list[dict[str, Any]]:
    """List available query templates, optionally filtered by category.

    Common categories include 'basic' for simple queries and 'analysis'
    for advanced memory analysis templates.
    """
    return _analyzer.list_templates(category)


@mcp.tool()
def get_template_info(template_name: str) -> dict[str, Any]:
    """Get detailed information about a query template including parameters and output schema.

    Use this to understand what parameters a template accepts before calling execute_query.
    """
    info = _analyzer.get_template_info(template_name)
    if info is None:
        return {"error": f"Template '{template_name}' not found"}
    return info


@mcp.tool()
def execute_query(
    template: str,
    params: dict[str, Any] | None = None,
    device_id: int | None = None,
    max_rows: int = 100,
) -> dict[str, Any]:
    """Execute a query template against the focused database.

    Args:
        template: Template name (e.g., 'leak_detection', 'callstack_analysis').
            Use list_templates to discover available templates.
        params: Query parameters as a dict. Use get_template_info to see
            what parameters each template accepts.
        device_id: Device ID to query (uses focused device if not specified).
        max_rows: Maximum rows to return (0 for unlimited, default: 100).
    """
    return _analyzer.execute_query(template, params, device_id, max_rows)


@mcp.resource("focus://current")
def focus_resource() -> dict[str, Any]:
    """Current analysis focus state."""
    state = _analyzer.get_focus()
    return {
        "db_path": state.db_path,
        "device_id": state.device_id,
        "source": state.source,
        "available_devices": state.available_devices,
    }


@mcp.prompt()
def analyze_memory_leaks(
    db_path: str,
    device_id: int = 0,
) -> str:
    """Generate a prompt template for analyzing memory leaks in a PyTorch snapshot."""
    return (
        f"Analyze the PyTorch memory snapshot at '{db_path}' for device {device_id}. "
        f"First, set focus to the database, then run the leak_detection template. "
        f"Review the results and summarize any potential memory leaks found."
    )


def main() -> None:
    """Entry point for the MCP server."""
    mcp.run()


if __name__ == "__main__":
    main()
