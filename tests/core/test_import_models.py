"""Tests for ImportOptions / ImportResult dataclasses."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from pt_snap_cli.core.models import ImportOptions, ImportResult


def test_import_options_defaults() -> None:
    options = ImportOptions(snapshot_file=Path("sample.pkl"))
    assert options.output_dir is None
    assert options.device is None
    assert options.set_focus is True


def test_import_options_is_frozen() -> None:
    options = ImportOptions(snapshot_file=Path("sample.pkl"))
    try:
        options.set_focus = False  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("ImportOptions should be frozen")


def test_import_result_construction() -> None:
    result = ImportResult(db_path=Path("sample.pkl.db"), device_id=0, focus_state=None)
    assert result.db_path == Path("sample.pkl.db")
    assert result.device_id == 0
    assert result.focus_state is None


def test_import_result_is_frozen() -> None:
    result = ImportResult(db_path=Path("sample.pkl.db"), device_id=0, focus_state=None)
    try:
        result.db_path = Path("other.db")  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("ImportResult should be frozen")
