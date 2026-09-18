"""CLI/SnapshotAnalyzer semantic contract tests.

These tests compare normalized CLI semantics with SnapshotAnalyzer rather than
raw CLI text. They guard the shared API/core contract from adapter drift.

API-specific shapes are asserted as-is: ``get_template_info()`` returns ``None``
for a missing template, and ``execute_query()`` defaults to ``max_rows=None``.
"""

from __future__ import annotations

import ast
import inspect
import json
import sqlite3
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from pt_snap_cli.api import FocusState, SnapshotAnalyzer
from pt_snap_cli.cli import app
from pt_snap_cli.core import InvalidDeviceError, TemplateRenderError
from pt_snap_cli.query.config import QueryParameter, QueryTemplate
from pt_snap_cli.query.registry import QueryRegistry, register_query

runner = CliRunner()


def create_contract_db(db_path: Path) -> Path:
    """Create a tiny snapshot database shared by CLI and API contract paths."""
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
def analyzer() -> SnapshotAnalyzer:
    return SnapshotAnalyzer()


def _focused_analyzer(db_path: Path, device_id: int | None = None) -> SnapshotAnalyzer:
    return SnapshotAnalyzer(db_path=db_path, device_id=device_id)


def _focus_payload(state: FocusState) -> dict[str, object]:
    return {
        "db_path": state.db_path,
        "device_id": state.device_id,
        "available_devices": state.available_devices,
        "callstack_layout": state.callstack_layout,
        "callstack_layout_error": state.callstack_layout_error,
    }


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
        elif line.startswith("Callstack layout: "):
            focus["callstack_layout"] = line.removeprefix("Callstack layout: ").split(" ", 1)[0]
        elif line.startswith("Warning: "):
            focus["callstack_layout_error"] = line.removeprefix("Warning: ")
    focus.setdefault("device_id", None)
    focus.setdefault("available_devices", [])
    focus.setdefault("callstack_layout", None)
    focus.setdefault("callstack_layout_error", None)
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
    info: dict[str, object] = {
        "parameters": {},
        "output_schema": [],
        "semantics_version": None,
        "interpretation_limits": [],
    }
    section: str | None = None
    current_param: str | None = None
    current_column: dict[str, object] | None = None

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
        elif stripped.startswith("Semantics Version: "):
            text = stripped.removeprefix("Semantics Version: ")
            info["semantics_version"] = None if text == "none" else int(text)
        elif stripped == "Parameters:":
            section = "parameters"
            current_column = None
        elif stripped == "Output Schema:":
            section = "output_schema"
            current_column = None
        elif stripped == "Interpretation Limits:":
            section = "template_interpretation_limits"
            current_column = None
        elif stripped == "Example Usage:":
            section = None
            current_column = None
        elif section == "parameters" and line.startswith("  ") and not line.startswith("    "):
            name, metadata = stripped.split(": ", 1)
            param_type = metadata.split(" ", 1)[0]
            required = "(required)" in metadata
            default = None
            if "[default: " in metadata:
                default_text = metadata.split("[default: ", 1)[1].removesuffix("]")
                default = _coerce_cli_default(default_text)
            choices = None
            if "[choices: " in metadata:
                choices_text = metadata.split("[choices: ", 1)[1].split("]", 1)[0]
                choices = [_coerce_cli_default(item) for item in choices_text.split(", ")]
            info["parameters"][name] = {
                "type": param_type,
                "default": default,
                "required": required,
                "description": "",
                "choices": choices,
            }
            current_param = name
        elif section == "parameters" and current_param and line.startswith("    "):
            info["parameters"][current_param]["description"] = stripped
        elif section == "output_schema" and stripped == "Dynamic (depends on query)":
            continue
        elif section == "output_schema" and line.startswith("      - "):
            assert current_column is not None
            limits = current_column.setdefault("interpretation_limits", [])
            assert isinstance(limits, list)
            limits.append(stripped[2:])
        elif (
            section == "output_schema" and line.startswith("    ") and not line.startswith("     ")
        ):
            assert current_column is not None
            if stripped.endswith(":") and ": " not in stripped:
                current_column[stripped[:-1]] = []
            else:
                key, value = stripped.split(": ", 1)
                current_column[key] = _coerce_cli_default(value) if key == "sentinel" else value
        elif section == "output_schema" and line.startswith("  ") and not line.startswith("    "):
            column, column_type = stripped.split(": ", 1)
            current_column = {"column": column, "type": column_type}
            schema = info["output_schema"]
            assert isinstance(schema, list)
            schema.append(current_column)
        elif section == "template_interpretation_limits" and stripped.startswith("- "):
            limits = info["interpretation_limits"]
            assert isinstance(limits, list)
            limits.append(stripped[2:])

    return info


def _normalize_cli_query_result(output: str, device_id: int) -> dict[str, object]:
    lines = output.splitlines()
    header = lines[0]
    total = int(header.split("Found ", 1)[1].split(" results", 1)[0])
    returned = int(header.split("showing ", 1)[1].split(":", 1)[0])
    rows = [ast.literal_eval(line.strip()) for line in lines[1:] if line.startswith("  {")]
    return {"total": total, "returned": returned, "device_id": device_id, "rows": rows}


def _assert_query_execution_contract(
    cli_query: dict[str, object],
    api_query: dict[str, object],
    template: str,
    semantics_version: int | None,
) -> None:
    shared = {key: api_query[key] for key in ("total", "returned", "device_id", "rows")}
    assert cli_query == shared
    assert api_query["template"] == template
    assert api_query["semantics_version"] == semantics_version


def _normalize_cli_missing_focus(output: str) -> dict[str, str]:
    return {"kind": "focus_not_configured"}


def test_execute_query_default_max_rows_is_unlimited() -> None:
    """API default remains max_rows=None. Do not restore the removed MCP cap of 100."""
    default = inspect.signature(SnapshotAnalyzer.execute_query).parameters["max_rows"].default
    assert default is None


def test_focus_contract_matches_cli_and_api_semantics(
    contract_db: Path, analyzer: SnapshotAnalyzer
) -> None:
    cli_result = runner.invoke(app, ["focus", str(contract_db), "--device", "1"])
    assert cli_result.exit_code == 0

    cli_focus = _normalize_cli_focus(cli_result.stdout)
    api_focus = _focus_payload(analyzer.set_focus(str(contract_db), device_id=1))

    assert cli_focus == api_focus
    assert cli_focus["callstack_layout"] == "v1"
    assert cli_focus["callstack_layout_error"] is None


def test_invalid_focus_device_contract_matches_cli_and_api_semantics(
    contract_db: Path, analyzer: SnapshotAnalyzer
) -> None:
    cli_result = runner.invoke(app, ["focus", str(contract_db), "--device", "99"])
    assert cli_result.exit_code == 1

    with pytest.raises(InvalidDeviceError) as exc_info:
        analyzer.set_focus(str(contract_db), device_id=99)

    assert str(exc_info.value) in cli_result.stdout


def test_template_list_contract_matches_cli_and_api_semantics(analyzer: SnapshotAnalyzer) -> None:
    cli_result = runner.invoke(app, ["query", "--category", "basic"])
    assert cli_result.exit_code == 0

    assert _normalize_cli_template_list(cli_result.stdout) == analyzer.list_templates("basic")


def test_template_info_contract_matches_cli_and_api_semantics(contract_db: Path) -> None:
    cli_result = runner.invoke(
        app,
        ["query", str(contract_db), "--template-info", "allocation"],
    )
    assert cli_result.exit_code == 0
    assert "Category: basic" in cli_result.stdout
    assert "Devices: all" in cli_result.stdout

    cli_info = _normalize_cli_template_info(cli_result.stdout)
    api_info = _focused_analyzer(contract_db).get_template_info("allocation")

    assert cli_info == api_info
    json.dumps(api_info)
    assert cli_info["semantics_version"] is None
    assert cli_info["interpretation_limits"] == []
    assert cli_info["parameters"]["order_by"]["choices"] == [
        "id",
        "allocated",
        "active",
        "reserved",
    ]
    assert cli_info["parameters"]["order_dir"]["choices"] == ["ASC", "DESC"]


def test_template_semantics_contract_matches_cli_and_api(contract_db: Path) -> None:
    """Issue #141: field units and interpretation limits pass through unchanged."""
    analyzer = _focused_analyzer(contract_db)
    for name in (
        "leak_detection",
        "memory_peak",
        "allocator_gap",
        "active_memory_callstack_at_event",
    ):
        cli_result = runner.invoke(
            app,
            ["query", str(contract_db), "--template-info", name],
        )
        assert cli_result.exit_code == 0, cli_result.stdout
        cli_info = _normalize_cli_template_info(cli_result.stdout)
        api_info = analyzer.get_template_info(name)
        assert cli_info == api_info
        json.dumps(api_info)
        assert api_info["semantics_version"] == 1
        assert api_info["interpretation_limits"]


def test_leak_detection_template_does_not_advertise_device_id(contract_db: Path) -> None:
    """Regression for issue #90: ``device_id`` is resolved from focus / --device,
    not from template parameters, so the template metadata must not expose it.
    """
    cli_result = runner.invoke(
        app,
        ["query", str(contract_db), "--template-info", "leak_detection"],
    )
    assert cli_result.exit_code == 0

    cli_info = _normalize_cli_template_info(cli_result.stdout)
    api_info = _focused_analyzer(contract_db).get_template_info("leak_detection")

    for info in (cli_info, api_info):
        assert info is not None
        assert "parameters" in info
        assert "device_id" not in info["parameters"], (
            "leak_detection must not advertise device_id; use --device / "
            "API device_id / focus selection instead."
        )
        assert "min_size" in info["parameters"]


def test_query_execution_contract_matches_cli_and_api_semantics(contract_db: Path) -> None:
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

    cli_query = _normalize_cli_query_result(cli_result.stdout, device_id=device_id)
    api_query = _focused_analyzer(contract_db).execute_query(
        "leak_detection", params=params, device_id=device_id, max_rows=0
    )

    _assert_query_execution_contract(cli_query, api_query, "leak_detection", 1)


def test_event_query_contract_reads_v1_inline_callstack(contract_db: Path) -> None:
    conn = sqlite3.connect(str(contract_db))
    conn.execute(
        """
        INSERT INTO trace_entry_1
          (id, action, address, size, stream, allocated, active, reserved, callstack)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (1, 4, 0x1000, 2048, 0, 2048, 2048, 4096, "train.py:10"),
    )
    conn.commit()
    conn.close()

    cli_result = runner.invoke(
        app,
        [
            "query",
            str(contract_db),
            "--template-use",
            "event",
            "--params",
            json.dumps({"id": 1}),
            "--device",
            "1",
            "-n",
            "0",
        ],
    )
    assert cli_result.exit_code == 0

    cli_query = _normalize_cli_query_result(cli_result.stdout, device_id=1)
    api_query = _focused_analyzer(contract_db).execute_query(
        "event", params={"id": 1}, device_id=1, max_rows=0
    )

    _assert_query_execution_contract(cli_query, api_query, "event", None)
    assert api_query["rows"][0]["callstack"] == "train.py:10"


def test_query_parameter_error_contract_matches_cli_and_api_semantics(contract_db: Path) -> None:
    register_query(
        QueryTemplate(
            name="required_query",
            query="SELECT {{ count }}",
            parameters={
                "count": QueryParameter(name="count", type="int", required=True),
            },
        )
    )
    cli_result = runner.invoke(
        app,
        ["query", str(contract_db), "--template-use", "required_query"],
    )
    assert cli_result.exit_code == 1
    analyzer = _focused_analyzer(contract_db)

    with pytest.raises(TemplateRenderError) as exc_info:
        analyzer.execute_query("required_query")

    assert str(exc_info.value) in cli_result.stdout


def test_missing_focus_error_contract_matches_cli_and_api_semantics(
    analyzer: SnapshotAnalyzer,
) -> None:
    cli_result = runner.invoke(app, ["query", "--template-use", "leak_detection"])
    assert cli_result.exit_code == 1

    with pytest.raises(RuntimeError) as exc_info:
        analyzer.execute_query("leak_detection")

    assert _normalize_cli_missing_focus(cli_result.stdout) == {"kind": "focus_not_configured"}
    assert str(exc_info.value) == "No database configured. Call set_focus() first."


def test_unknown_parameter_error_contract_matches_cli_and_api_semantics(contract_db: Path) -> None:
    """Regression for issue #120: both surfaces reject undeclared parameters identically."""
    cli_result = runner.invoke(
        app,
        [
            "query",
            str(contract_db),
            "--template-use",
            "leak_detection",
            "--params",
            '{"min_sze": 1024}',
        ],
    )
    assert cli_result.exit_code == 1

    analyzer = _focused_analyzer(contract_db)
    with pytest.raises(TemplateRenderError) as exc_info:
        analyzer.execute_query("leak_detection", params={"min_sze": 1024})

    assert "Unknown parameter(s) for template 'leak_detection': min_sze" in str(exc_info.value)
    assert str(exc_info.value) in cli_result.stdout


def test_choices_error_contract_matches_cli_and_api_semantics(contract_db: Path) -> None:
    """Regression for issue #120: SQL fragment parameters are bounded on both surfaces."""
    params = {"order_by": "(SELECT 1)", "order_dir": "ASC"}
    cli_result = runner.invoke(
        app,
        ["query", str(contract_db), "--template-use", "allocation", "--params", json.dumps(params)],
    )
    assert cli_result.exit_code == 1

    analyzer = _focused_analyzer(contract_db)
    with pytest.raises(TemplateRenderError) as exc_info:
        analyzer.execute_query("allocation", params=params)

    assert "Parameter 'order_by' must be one of: id, allocated, active, reserved" in str(
        exc_info.value
    )
    assert str(exc_info.value) in cli_result.stdout


def test_missing_template_error_contract_matches_cli_and_api_semantics(
    analyzer: SnapshotAnalyzer,
) -> None:
    template_name = "does_not_exist"
    cli_result = runner.invoke(app, ["query", "--template-info", template_name])
    assert cli_result.exit_code == 1
    assert f"Template '{template_name}' not found" in cli_result.stdout
    assert analyzer.get_template_info(template_name) is None


def test_metadata_contract_matches_cli_and_api_semantics(contract_db: Path) -> None:
    cli_result = runner.invoke(app, ["metadata", str(contract_db), "--json"])
    assert cli_result.exit_code == 0

    assert json.loads(cli_result.stdout) == _focused_analyzer(contract_db).get_database_metadata()
