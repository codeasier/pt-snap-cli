from pt_snap_cli.core import (
    ImportExecutionError,
    ImportToolMissingError,
    PtSnapCoreError,
    SnapshotFileInvalidError,
)


def test_import_tool_missing_error_is_pt_snap_core():
    assert issubclass(ImportToolMissingError, PtSnapCoreError)


def test_snapshot_file_invalid_error_is_pt_snap_core():
    assert issubclass(SnapshotFileInvalidError, PtSnapCoreError)


def test_import_execution_error_is_pt_snap_core():
    assert issubclass(ImportExecutionError, PtSnapCoreError)
