"""Tests for snapshot import error types."""

from __future__ import annotations

from pt_snap_cli.core.errors import (
    ImportExecutionError,
    ImportToolMissingError,
    PtSnapCoreError,
    SnapshotFileInvalidError,
)


def test_import_tool_missing_error_is_pt_snap_core() -> None:
    assert issubclass(ImportToolMissingError, PtSnapCoreError)


def test_snapshot_file_invalid_error_is_pt_snap_core() -> None:
    assert issubclass(SnapshotFileInvalidError, PtSnapCoreError)


def test_import_execution_error_is_pt_snap_core() -> None:
    assert issubclass(ImportExecutionError, PtSnapCoreError)


def test_unsafe_pickle_error_is_unpickling_error() -> None:
    from pickle import UnpicklingError

    from pt_snap_cli.snapshot.representation import UnsafePickleError

    assert issubclass(UnsafePickleError, UnpicklingError)
