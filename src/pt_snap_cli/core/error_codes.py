"""Stable CLI error codes for JSON-mode failures."""

from __future__ import annotations

import json

from pt_snap_cli.core.errors import (
    DatabaseMissingError,
    DatabaseSchemaError,
    FocusFileInvalidError,
    FocusNotConfiguredError,
    ImportExecutionError,
    ImportToolMissingError,
    InvalidCategoryError,
    InvalidDeviceError,
    InvalidParameterError,
    QueryExecutionError,
    QueryTimeoutError,
    SkillError,
    SnapshotFileInvalidError,
    SplitError,
    TemplateNotFoundError,
    TemplateRenderError,
)

TEMPLATE_NOT_FOUND = "TEMPLATE_NOT_FOUND"
INVALID_PARAMETER = "INVALID_PARAMETER"
DATABASE_NOT_FOUND = "DATABASE_NOT_FOUND"
DEVICE_NOT_FOUND = "DEVICE_NOT_FOUND"
FOCUS_NOT_CONFIGURED = "FOCUS_NOT_CONFIGURED"
FOCUS_FILE_INVALID = "FOCUS_FILE_INVALID"
DATABASE_SCHEMA_INVALID = "DATABASE_SCHEMA_INVALID"
QUERY_FAILED = "QUERY_FAILED"
QUERY_TIMEOUT = "QUERY_TIMEOUT"
IMPORT_FAILED = "IMPORT_FAILED"
IMPORT_BACKEND_MISSING = "IMPORT_BACKEND_MISSING"
SNAPSHOT_INVALID = "SNAPSHOT_INVALID"
SPLIT_FAILED = "SPLIT_FAILED"
SKILL_ERROR = "SKILL_ERROR"
ERROR = "ERROR"


def classify_error(exc: BaseException) -> tuple[str, str | None]:
    """Return a stable error code and an actionable hint for ``exc``."""
    if isinstance(exc, TemplateNotFoundError):
        return (
            TEMPLATE_NOT_FOUND,
            "Use 'pt-snap query --list --json' to list available templates.",
        )
    if isinstance(exc, (TemplateRenderError, json.JSONDecodeError)):
        return (
            INVALID_PARAMETER,
            "Check --params against 'pt-snap query --template-info <name> --json'.",
        )
    if isinstance(exc, InvalidCategoryError):
        return (
            INVALID_PARAMETER,
            "Use 'pt-snap query --list --json' to see valid categories.",
        )
    if isinstance(exc, InvalidDeviceError):
        return (
            DEVICE_NOT_FOUND,
            "Pass --device with an id present in the database, or omit it to use the first device.",
        )
    if isinstance(exc, FocusNotConfiguredError):
        return (
            FOCUS_NOT_CONFIGURED,
            "Use 'pt-snap focus <database_path>' or pass a database path argument.",
        )
    if isinstance(exc, DatabaseMissingError):
        return (
            DATABASE_NOT_FOUND,
            "Use 'pt-snap focus <database_path>' or pass a database path that exists.",
        )
    if isinstance(exc, FocusFileInvalidError):
        return (
            FOCUS_FILE_INVALID,
            "Fix or remove the invalid .pt-snap/focus.json and set focus again.",
        )
    if isinstance(exc, DatabaseSchemaError):
        return (
            DATABASE_SCHEMA_INVALID,
            "Confirm the file is a SnapshotDB with a dictionary table.",
        )
    if isinstance(exc, InvalidParameterError):
        return (
            INVALID_PARAMETER,
            "Use a numeric --timeout, or set PT_SNAP_QUERY_TIMEOUT to a number of seconds.",
        )
    if isinstance(exc, QueryTimeoutError):
        return (
            QUERY_TIMEOUT,
            "Retry with a higher --timeout, or tighten -n / filters so the query does less work.",
        )
    if isinstance(exc, QueryExecutionError):
        return (
            QUERY_FAILED,
            "Inspect the template SQL and database layout, then retry with --template-info --json.",
        )
    if isinstance(exc, ImportToolMissingError):
        return (
            IMPORT_BACKEND_MISSING,
            "Reinstall pt-snap-cli so the first-party import backend is available.",
        )
    if isinstance(exc, SnapshotFileInvalidError):
        return (
            SNAPSHOT_INVALID,
            "Provide a trusted existing .pkl or .pickle snapshot file.",
        )
    if isinstance(exc, ImportExecutionError):
        return (
            IMPORT_FAILED,
            "Confirm the pickle is trusted and replayable, then retry with --force if needed.",
        )
    if isinstance(exc, SplitError):
        return (
            SPLIT_FAILED,
            "Check the split arguments, source pickle, and destination path.",
        )
    if isinstance(exc, SkillError):
        return (
            SKILL_ERROR,
            "Use 'pt-snap skill list --json' and check --target / --dir options.",
        )
    return ERROR, None
