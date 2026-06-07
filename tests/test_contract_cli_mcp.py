"""CLI/MCP semantic contract tests.

These tests intentionally compare normalized semantics rather than raw CLI text and MCP
JSON formatting. They guard the shared API/core contract from adapter drift.
"""

from __future__ import annotations

import ast
import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from pt_snap_cli.api import SnapshotAnalyzer
from pt_snap_cli.cli import app
from pt_snap_cli.query.registry import QueryRegistry

runner = CliRunner()


def create_contract_db(db_path: Path) -> Path:
    """Create a tiny snapshot database shared by CLI and MCP contract paths."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE dictionary (
            `table` TEXT, `column` TEXT, `key` TEXT, `value` TEXT
        )
    """)
    for device_id, rows in {
        0: [
            (1, 0x1000, 2048, 2000, 1, 1, -1),
            (2, 0x2000, 512, 500, 0, 2, 3),
        ],
        1: [
            (3, 0x3000, 4096, 4000, 1, 4, None),
        ],
    }.items():
        conn.execute(f"""
            CREATE TABLE trace_entry_{device_id} (
                id INTEGER PRIMARY KEY, action INTEGER, address INTEGER,
                size INTEGER, stream INTEGER, allocated INTEGER,
                active INTEGER, reserved INTEGER, callstack TEXT
            )
        """)
        conn.execute(f"""
            CREATE TABLE block_{device_id} (
                id INTEGER PRIMARY KEY, address INTEGER, size INTEGER,
                requestedSize INTEGER, state INTEGER, allocEventId INTEGER,
                freeEventId INTEGER
            )
        """)
        conn.executemany(
            f"""
            INSERT INTO block_{device_id}
              (id, address, size, requestedSize, state, allocEventId, freeEventId)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture(autouse=True)
def _isolate_contract_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PT_SNAP_DB_PATH", raising=False)
    with patch.object(Path, "home", return_value=tmp_path):
        QueryRegistry.reset()
        yield
        QueryRegistry.reset()


@pytest.fixture
def contract_db(tmp_path: Path) -> Path:
    return create_contract_db(tmp_path / "contract.db")


@pytest.fixture
def mcp_server() -> Iterator[ModuleType]:
    import pt_snap_cli.mcp.server as server

    original_analyzer = server._analyzer
    server._analyzer = SnapshotAnalyzer()
    try:
        yield server
    finally:
        server._analyzer = original_analyzer


def _set_mcp_focus(server: ModuleType, db_path: Path, device_id: int | None = None) -> ModuleType:
    server._analyzer = SnapshotAnalyzer(db_path=db_path, device_id=device_id)
    return server


def _coerce_cli_default(default_text: str) -> object:
    if default_text in {"True", "False"}:
        return default_text == "True"
    try:
        return int(default_text)
    except ValueError:
        try:
            return float(default_text)
        except ValueError:
            return default_text


def _normalize_cli_focus(output: str) -> dict[str, object]:
    focus: dict[str, object] = {}
    for line in output.splitlines():
        if line.startswith("Using project database: "):
            focus["db_path"] = line.removeprefix("Using project database: ")
        elif line.startswith("Focused device: "):
            focus["device_id"] = int(line.removeprefix("Focused device: "))
        elif line.startswith("Available devices: "):
            focus["available_devices"] = [
                int(device.strip())
                for device in line.removeprefix("Available devices: ").split(",")
            ]
    focus.setdefault("device_id", None)
    focus.setdefault("available_devices", [])
    return focus


def _normalize_cli_template_list(output: str) -> list[dict[str, str]]:
    templates: list[dict[str, str]] = []
    category: str | None = None
    lines = output.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.endswith(" Queries:"):
            category = line.removesuffix(" Queries:").lower().replace(" ", "_")
        elif line.startswith("  ") and not line.startswith("    "):
            name = line.strip()
            description = lines[index + 1].strip() if index + 1 < len(lines) else ""
            templates.append({"name": name, "description": description, "category": category or ""})
            index += 2
            continue
        index += 1
    return templates


def _normalize_cli_template_info(output: str) -> dict[str, object]:
    info: dict[str, object] = {"parameters": {}, "output_schema": []}
    section: str | None = None
    current_param: str | None = None

    for raw_line in output.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if stripped.startswith("Template: "):
            info["name"] = stripped.removeprefix("Template: ")
        elif stripped.startswith("Description: "):
            info["description"] = stripped.removeprefix("Description: ")
        elif stripped.startswith("Category: "):
            info["category"] = stripped.removeprefix("Category: ")
        elif stripped.startswith("Devices: "):
            info["devices"] = stripped.removeprefix("Devices: ")
        elif stripped == "Parameters:":
            section = "parameters"
        elif stripped == "Output Schema:":
            section = "output_schema"
        elif stripped == "Example Usage:":
            section = None
        elif section == "parameters" and line.startswith("  ") and not line.startswith("    "):
            name, metadata = stripped.split(": ", 1)
            param_type = metadata.split(" ", 1)[0]
            required = "(required)" in metadata
            default = None
            if "[default: " in metadata:
                default_text = metadata.split("[default: ", 1)[1].removesuffix("]")
                default = _coerce_cli_default(default_text)
            info["parameters"][name] = {
                "type": param_type,
                "default": default,
                "required": required,
                "description": "",
            }
            current_param = name
        elif section == "parameters" and current_param and line.startswith("    "):
            info["parameters"][current_param]["description"] = stripped
        elif section == "output_schema" and line.startswith("  ") and stripped != "Dynamic (depends on query)":
            column, column_type = stripped.split(": ", 1)
            info["output_schema"].append({"column": column, "type": column_type})

    return info


def _normalize_cli_query_result(output: str, device_id: int) -> dict[str, object]:
    lines = output.splitlines()
    header = lines[0]
    total = int(header.split("Found ", 1)[1].split(" results", 1)[0])
    returned = int(header.split("showing ", 1)[1].split(":", 1)[0])
    rows = [ast.literal_eval(line.strip()) for line in lines[1:] if line.startswith("  {")]
    return {"total": total, "returned": returned, "device_id": device_id, "rows": rows}


def _normalize_cli_missing_template(output: str) -> dict[str, str]:
    return {"error": output.strip().removeprefix("Error: ")}


def _normalize_cli_missing_focus(output: str) -> dict[str, str]:
    return {"kind": "focus_not_configured"}


def test_focus_contract_matches_cli_and_mcp_semantics(contract_db: Path, mcp_server: ModuleType) -> None:
    cli_result = runner.invoke(app, ["focus", str(contract_db), "--device", "1"])
    assert cli_result.exit_code == 0

    cli_focus = _normalize_cli_focus(cli_result.stdout)
    mcp_focus = mcp_server.set_focus(str(contract_db), device_id=1)

    assert cli_focus == {
        "db_path": mcp_focus["db_path"],
        "device_id": mcp_focus["device_id"],
        "available_devices": mcp_focus["available_devices"],
    }


def test_template_list_contract_matches_cli_and_mcp_semantics(mcp_server: ModuleType) -> None:
    cli_result = runner.invoke(app, ["query", "--category", "basic"])
    assert cli_result.exit_code == 0

    cli_templates = _normalize_cli_template_list(cli_result.stdout)
    mcp_templates = [
        {"name": item["name"], "description": item["description"], "category": item["category"]}
        for item in mcp_server.list_templates("basic")
    ]

    assert cli_templates == mcp_templates


def test_template_info_contract_matches_cli_and_mcp_semantics(
    contract_db: Path, mcp_server: ModuleType
) -> None:
    cli_result = runner.invoke(
        app,
        ["query", str(contract_db), "--template-info", "leak_detection"],
    )
    assert cli_result.exit_code == 0
    assert "Category: business" in cli_result.stdout
    assert "Devices: all, 0, 1" in cli_result.stdout

    server = _set_mcp_focus(mcp_server, contract_db)
    cli_info = _normalize_cli_template_info(cli_result.stdout)
    mcp_info = server.get_template_info("leak_detection")

    assert cli_info == mcp_info


def test_query_execution_contract_matches_cli_and_mcp_semantics(
    contract_db: Path, mcp_server: ModuleType
) -> None:
    params = {"min_size": 1024}
    device_id = 1
    cli_result = runner.invoke(
        app,
        [
            "query",
            str(contract_db),
            "--template-use",
            "leak_detection",
            "--params",
            json.dumps(params),
            "--device",
            str(device_id),
            "-n",
            "0",
        ],
    )
    assert cli_result.exit_code == 0

    server = _set_mcp_focus(mcp_server, contract_db)
    cli_query = _normalize_cli_query_result(cli_result.stdout, device_id=device_id)
    mcp_query = server.execute_query(
        "leak_detection", params=params, device_id=device_id, max_rows=0
    )

    assert cli_query == mcp_query


def test_missing_focus_error_contract_matches_cli_and_mcp_semantics(
    mcp_server: ModuleType,
) -> None:
    cli_result = runner.invoke(app, ["query", "--template-use", "leak_detection"])
    assert cli_result.exit_code == 1

    with pytest.raises(RuntimeError) as exc_info:
        mcp_server.execute_query("leak_detection")

    assert _normalize_cli_missing_focus(cli_result.stdout) == {"kind": "focus_not_configured"}
    assert str(exc_info.value) == "No database configured. Call set_focus() first."


def test_missing_template_error_contract_matches_cli_and_mcp_semantics(
    mcp_server: ModuleType,
) -> None:
    template_name = "does_not_exist"
    cli_result = runner.invoke(app, ["query", "--template-info", template_name])
    assert cli_result.exit_code == 0

    assert _normalize_cli_missing_template(cli_result.stdout) == mcp_server.get_template_info(
        template_name
    )
