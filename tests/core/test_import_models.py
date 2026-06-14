from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from pt_snap_cli.core.models import ImportOptions, ImportResult


def test_import_options_defaults() -> None:
    options = ImportOptions(snapshot_file=Path("x.pkl"))

    assert options.snapshot_file == Path("x.pkl")
    assert options.output_dir is None
    assert options.device is None
    assert options.set_focus is True


def test_import_options_is_frozen() -> None:
    options = ImportOptions(snapshot_file=Path("x.pkl"))

    with pytest.raises(dataclasses.FrozenInstanceError):
        options.device = 0  # type: ignore[misc]


def test_import_result_construction() -> None:
    result = ImportResult(db_path=Path("x.db"), device_id=0, focus_state=None)

    assert result.db_path == Path("x.db")
    assert result.device_id == 0
    assert result.focus_state is None


def test_import_result_is_frozen() -> None:
    result = ImportResult(db_path=Path("x.db"), device_id=0, focus_state=None)

    with pytest.raises(dataclasses.FrozenInstanceError):
        result.device_id = 1  # type: ignore[misc]
