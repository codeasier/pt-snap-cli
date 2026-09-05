from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from typing import Any

import yaml

from .descriptors import DescriptorError

# Fixture YAML keeps authoring the callstack as text per trace row; the builder
# interns it into the shared `callstack` table that SnapshotDB now emits.
TRACE_COLUMNS = (
    "id",
    "action",
    "address",
    "size",
    "stream",
    "allocated",
    "active",
    "reserved",
    "callstack",
)
_TRACE_TABLE_COLUMNS = (*TRACE_COLUMNS[:-1], "callstackId")
_CALLSTACK_INDEX = TRACE_COLUMNS.index("callstack")
BLOCK_COLUMNS = (
    "id",
    "address",
    "size",
    "requestedSize",
    "state",
    "allocEventId",
    "freeEventId",
)


def _rows(value: Any, columns: tuple[str, ...], context: str) -> list[tuple[Any, ...]]:
    if not isinstance(value, list):
        raise DescriptorError(f"{context} must be a list")
    rows: list[tuple[Any, ...]] = []
    for index, row in enumerate(value):
        if not isinstance(row, dict) or set(row) != set(columns):
            raise DescriptorError(f"{context}[{index}] must define exactly {columns}")
        rows.append(tuple(row[column] for column in columns))
    return rows


def load_fixture_definition(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text())
    except (OSError, yaml.YAMLError) as exc:
        raise DescriptorError(f"Cannot load fixture {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise DescriptorError(f"{path} must contain a mapping")
    if set(data) != {"schema_version", "kind", "devices"}:
        raise DescriptorError(f"{path} has invalid fixture fields")
    if data["schema_version"] != 1 or data["kind"] != "synthetic-snapshotdb":
        raise DescriptorError(f"{path} must declare synthetic-snapshotdb schema version 1")
    if not isinstance(data["devices"], dict) or not data["devices"]:
        raise DescriptorError(f"{path}: devices must be a non-empty mapping")
    for device_id, device in data["devices"].items():
        if not str(device_id).isdigit() or not isinstance(device, dict):
            raise DescriptorError(f"{path}: device IDs must be non-negative integers")
        if set(device) != {"trace", "blocks"}:
            raise DescriptorError(f"{path}: device {device_id} must define trace and blocks")
        _rows(device["trace"], TRACE_COLUMNS, f"{path}: device {device_id}.trace")
        _rows(device["blocks"], BLOCK_COLUMNS, f"{path}: device {device_id}.blocks")
    return data


def build_snapshotdb(definition_path: Path, output_path: Path, *, read_only: bool = True) -> Path:
    definition = load_fixture_definition(definition_path)
    if output_path.exists():
        raise FileExistsError(output_path)
    if not output_path.parent.is_dir():
        raise FileNotFoundError(output_path.parent)

    connection = sqlite3.connect(str(output_path))
    try:
        connection.execute(
            "CREATE TABLE dictionary (`table` TEXT, `column` TEXT, `key` TEXT, `value` TEXT)"
        )
        connection.execute("CREATE TABLE callstack (id INTEGER PRIMARY KEY, callstack TEXT)")
        callstack_ids: dict[str, int] = {}
        for raw_device_id, device in definition["devices"].items():
            device_id = int(raw_device_id)
            connection.execute(f"""
                CREATE TABLE trace_entry_{device_id} (
                    id INTEGER PRIMARY KEY,
                    action INTEGER,
                    address INTEGER,
                    size INTEGER,
                    stream INTEGER,
                    allocated INTEGER,
                    active INTEGER,
                    reserved INTEGER,
                    callstackId INTEGER
                )
                """)
            connection.execute(f"""
                CREATE TABLE block_{device_id} (
                    id INTEGER PRIMARY KEY,
                    address INTEGER,
                    size INTEGER,
                    requestedSize INTEGER,
                    state INTEGER,
                    allocEventId INTEGER,
                    freeEventId INTEGER
                )
                """)
            trace_rows = _rows(device["trace"], TRACE_COLUMNS, f"device {device_id}.trace")
            block_rows = _rows(device["blocks"], BLOCK_COLUMNS, f"device {device_id}.blocks")
            interned_rows: list[tuple[Any, ...]] = []
            for row in trace_rows:
                callstack = row[_CALLSTACK_INDEX]
                if callstack is None:
                    callstack_id = None
                else:
                    callstack_id = callstack_ids.get(callstack)
                    if callstack_id is None:
                        callstack_id = len(callstack_ids)
                        callstack_ids[callstack] = callstack_id
                        connection.execute(
                            "INSERT INTO callstack (id, callstack) VALUES (?, ?)",
                            (callstack_id, callstack),
                        )
                interned_rows.append((*row[:_CALLSTACK_INDEX], callstack_id))
            placeholders = ", ".join("?" for _ in _TRACE_TABLE_COLUMNS)
            connection.executemany(
                f"INSERT INTO trace_entry_{device_id} VALUES ({placeholders})", interned_rows
            )
            placeholders = ", ".join("?" for _ in BLOCK_COLUMNS)
            connection.executemany(
                f"INSERT INTO block_{device_id} VALUES ({placeholders})", block_rows
            )
        connection.commit()
    except Exception:
        connection.close()
        output_path.unlink(missing_ok=True)
        raise
    finally:
        connection.close()

    if read_only:
        os.chmod(output_path, 0o444)
    return output_path
