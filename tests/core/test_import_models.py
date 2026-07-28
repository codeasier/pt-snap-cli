"""Tests for ImportOptions / ImportResult dataclasses."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from pt_snap_cli.core.import_metadata import IMPORT_FORMAT_VERSION, METADATA_SCHEMA_VERSION
from pt_snap_cli.core.models import ImportMetadata, ImportOptions, ImportResult


def _metadata() -> ImportMetadata:
    return ImportMetadata(
        metadata_schema_version=METADATA_SCHEMA_VERSION,
        import_format_version=IMPORT_FORMAT_VERSION,
        source_sha256="a" * 64,
        source_size=123,
        source_name="sample.pkl",
        requested_device=0,
        importer_name="pt-snap-cli",
        importer_version="1.2.3",
        completed_at="2026-07-18T10:00:00+00:00",
    )


def test_import_options_defaults() -> None:
    options = ImportOptions(snapshot_file=Path("sample.pkl"))
    assert options.output_dir is None
    assert options.device is None
    assert options.set_focus is True
    assert options.force is False


def test_import_options_is_frozen() -> None:
    options = ImportOptions(snapshot_file=Path("sample.pkl"))
    try:
        options.set_focus = False  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("ImportOptions should be frozen")


def test_import_result_construction() -> None:
    result = ImportResult(
        db_path=Path("sample.pkl.db"),
        device_id=0,
        focus_state=None,
        reused=False,
        metadata=_metadata(),
        cache_miss_reason="database_missing",
    )
    assert result.db_path == Path("sample.pkl.db")
    assert result.device_id == 0
    assert result.focus_state is None
    assert result.reused is False


def test_import_result_is_frozen() -> None:
    result = ImportResult(
        db_path=Path("sample.pkl.db"),
        device_id=0,
        focus_state=None,
        reused=False,
        metadata=_metadata(),
        cache_miss_reason="database_missing",
    )
    try:
        result.db_path = Path("other.db")  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("ImportResult should be frozen")
