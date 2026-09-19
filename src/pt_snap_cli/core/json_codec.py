"""Shared JSON serialization for CLI result models."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any

JSON_SCHEMA_VERSION = 1

JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]


def to_jsonable(value: object) -> JsonValue:
    """Convert service models into JSON-safe values.

    ``Path`` becomes a string, bytes-like values decode as UTF-8 with
    replacement, nested dataclasses and mappings are walked, sequences
    become lists, and ``None`` stays ``null``. Numbers and booleans keep
    their JSON types.
    """
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (str, int, float)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, memoryview):
        value = value.tobytes()
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", "replace")
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: to_jsonable(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [to_jsonable(item) for item in value]
    raise TypeError(f"Cannot serialize {type(value)!r} to JSON")


def dumps_json(value: object) -> str:
    """Serialize ``value`` as indented UTF-8 JSON."""
    return json.dumps(to_jsonable(value), indent=2, ensure_ascii=False)


def json_success(**fields: Any) -> dict[str, JsonValue]:
    """Build a success envelope. Extra fields are serialized in place."""
    converted = to_jsonable(fields)
    if not isinstance(converted, dict):
        raise TypeError("json_success fields must serialize to an object")
    payload: dict[str, JsonValue] = {
        "schema_version": JSON_SCHEMA_VERSION,
        "ok": True,
    }
    payload.update(converted)
    return payload


def json_error(code: str, message: str, hint: str | None = None) -> dict[str, JsonValue]:
    """Build a structured error envelope for stderr."""
    return {
        "schema_version": JSON_SCHEMA_VERSION,
        "ok": False,
        "error": {
            "code": code,
            "message": message,
            "hint": hint,
        },
    }
