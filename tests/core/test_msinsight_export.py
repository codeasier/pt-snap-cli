"""Fixed interface contracts; GUI remains deferred, no vendor code execution."""

import copy
import dataclasses
import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pt_snap_cli.api import SnapshotAnalyzer
from pt_snap_cli.cli import _safe_call, app
from pt_snap_cli.core.dataset_contract import (
    ACTION_NAMES,
    BLOCK_COLUMNS,
    BLOCK_STATES,
    DICTIONARY_COLUMNS,
    MSINSIGHT_REVISION,
    TRACE_COLUMNS,
    validate_dataset,
)
from pt_snap_cli.core.dataset_resolver import DatasetResolver
from pt_snap_cli.core.errors import ImportExecutionError, SourceChangedError
from pt_snap_cli.core.focus_service import FocusService
from pt_snap_cli.core.import_service import ImportService
from pt_snap_cli.core.models import ImportOptions
from tests.core.test_dataset_import import hashes
from tests.snapshot.test_sharded_replay import lifecycle_data, write_source


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("PT_SNAP_DB_PATH", raising=False)


def options(tmp_path, *, multiple=False, capacity=2, focus=True):
    data = lifecycle_data()
    data["device_traces"][0] = [e for e in data["device_traces"][0] if e["action"] != "oom"]
    if multiple:
        data["device_traces"] += [copy.deepcopy(data["device_traces"][0]), []]
        data["segments"] += [{**copy.deepcopy(s), "device": 1} for s in data["segments"]]
    return ImportOptions(
        write_source(tmp_path, data),
        tmp_path / "output",
        set_focus=focus,
        events_per_slice=capacity,
        format="msinsight",
    )


def rows(path, sql):
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro&immutable=1", uri=True)) as conn:
        return conn.execute(sql).fetchall()


@pytest.mark.parametrize("capacity", [1, 2, 100, None])
@pytest.mark.parametrize("fmt", ["msinsight", "compatibility-v1"])
def test_physical_schema_inline_events_streams_stable_references_and_native_parity(
    tmp_path, capacity, fmt
):
    request = dataclasses.replace(options(tmp_path, multiple=True, capacity=capacity), format=fmt)
    service = ImportService()
    result = service.import_snapshot(request)
    assert result.format == "compatibility-v1" and result.metadata.import_format_version == 1
    assert result.devices == (0, 1) and result.omitted_devices == (2,)
    assert result.focus_state.callstack_layout == "v1"
    manifest = json.loads((result.db_path / "manifest.json").read_text())
    assert manifest["sourceFile"] == str(request.snapshot_file.resolve())
    assert manifest["eventsPerSlice"] == (capacity or 500000)
    raw = request.snapshot_file.read_bytes()
    assert manifest["cacheHash"] == hashlib.sha256(b"mem_snapshot_parser_v2" + raw).hexdigest()
    assert result.metadata.source_sha256 == hashlib.sha256(raw).hexdigest() != manifest["cacheHash"]
    assert manifest["ptSnap"]["identity"]["targetRevision"] == MSINSIGHT_REVISION
    native = service.import_snapshot(
        dataclasses.replace(
            request, format=None, events_per_slice=capacity or 500000, set_focus=False
        )
    )
    compatible = DatasetResolver().inspect(result.db_path)
    native_dataset = DatasetResolver().inspect(native.db_path)
    assert validate_dataset(result.db_path).real_event_count == 10
    for device in (0, 1):
        lifetimes = {}
        for shard, native_shard in zip(
            compatible.device(device).slices, native_dataset.device(device).slices, strict=True
        ):
            path = result.db_path / shard.file
            for table, columns in (
                (f"trace_entry_{device}", TRACE_COLUMNS),
                (f"block_{device}", BLOCK_COLUMNS),
                ("dictionary", DICTIONARY_COLUMNS),
            ):
                schema = rows(path, f"PRAGMA table_info({table})")
                assert tuple((r[1], r[2]) for r in schema) == columns
                assert rows(path, f"SELECT type FROM sqlite_master WHERE name='{table}'") == [
                    ("table",)
                ]
            assert not rows(path, "SELECT name FROM sqlite_master WHERE lower(name)='callstack'")
            assert rows(path, "SELECT import_format_version FROM pt_snap_metadata") == [(1,)]
            actual = rows(path, f"SELECT * FROM trace_entry_{device} ORDER BY id")
            expected = rows(
                native.db_path / native_shard.file,
                f"SELECT t.id,t.action,t.address,t.size,t.stream,t.allocated,t.active,t.reserved,c.callstack FROM trace_entry_{device} t JOIN callstack c ON c.id=t.callstackId ORDER BY t.id",
            )
            assert actual == expected
            assert [r[0] for r in actual if r[0] >= 0] == list(
                range(shard.start_event_id, shard.end_event_id + 1)
            )
            assert set(
                rows(path, 'SELECT "key","value" FROM dictionary WHERE "column"=\'action\'')
            ) == {(str(k), v) for k, v in enumerate(ACTION_NAMES)}
            assert set(
                rows(path, 'SELECT "key","value" FROM dictionary WHERE "column"=\'state\'')
            ) == {(str(k), v) for k, v in BLOCK_STATES}
            references = {r[0]: r[1:] for r in rows(path, "SELECT * FROM pt_snap_block_reference")}
            for block in rows(path, f"SELECT * FROM block_{device}"):
                signature = block[1:4] + block[5:]
                assert block[0] not in lifetimes or lifetimes[block[0]] == signature
                lifetimes[block[0]] = signature
                if block[6] >= 0:
                    assert block[6] == 3  # free_completed, NOT free_requested=2
                    assert references[block[0]][2] == "source.py:4 free_completed"
    before = hashes(result.db_path)
    with (
        SnapshotAnalyzer(result.db_path) as analyzer,
        SnapshotAnalyzer(native.db_path) as native_analyzer,
    ):
        assert analyzer.get_focus().callstack_layout == "v1"
        for device in (0, 1):
            for event in range(5):
                assert (
                    analyzer.execute_query("event", {"id": event}, device_id=device)["rows"]
                    == native_analyzer.execute_query("event", {"id": event}, device_id=device)[
                        "rows"
                    ]
                )
        assert not hasattr(analyzer, "import_snapshot")
    assert hashes(result.db_path) == before


def test_identical_complete_cache_reuses_without_loading_even_force(tmp_path, monkeypatch):
    request = options(tmp_path, focus=False)
    service = ImportService()
    first = service.import_snapshot(request)
    before = hashes(first.db_path)
    monkeypatch.setattr(
        service._msinsight_backend.replay,
        "stage",
        lambda *a, **k: pytest.fail("reused cache loaded pickle"),
    )
    for force in (False, True):
        reused = service.import_snapshot(dataclasses.replace(request, force=force))
        assert reused.reused and reused.metadata == first.metadata
    assert hashes(first.db_path) == before
    assert not (tmp_path / ".pt-snap").exists()


@pytest.mark.parametrize(
    "axis",
    [
        "source",
        "capacity",
        "device",
        "sourceFile",
        "hash",
        "version",
        "metadata",
        "last-member",
        "extra",
        "missing",
    ],
)
@pytest.mark.parametrize("force", [False, True])
def test_nonidentical_existing_output_never_replaced(tmp_path, axis, force):
    service = ImportService()
    request = options(tmp_path)
    first = service.import_snapshot(request)
    focus = (tmp_path / ".pt-snap/focus.json").read_bytes()
    manifest_path = first.db_path / "manifest.json"
    data = json.loads(manifest_path.read_text())
    if axis == "source":
        request.snapshot_file.write_bytes(
            request.snapshot_file.read_bytes() + b"trailing-source-bytes"
        )
    elif axis == "capacity":
        request = dataclasses.replace(request, events_per_slice=3)
    elif axis == "device":
        request = dataclasses.replace(request, device=0)
    elif axis == "sourceFile":
        data["sourceFile"] = "/different/input.pkl"
    elif axis == "hash":
        data["cacheHash"] = "f" * 64
    elif axis == "version":
        data["ptSnap"]["identity"]["exportContractVersion"] += 1
    elif axis == "metadata":
        data["ptSnap"]["metadata"]["import_format_version"] = 2
    elif axis == "last-member":
        (first.db_path / "device_0/slice_00002.db").write_bytes(b"broken")
    elif axis == "extra":
        (first.db_path / "user-notes").write_text("preserve")
    else:
        # Test-owned member removal, never an external artifact.
        (first.db_path / "device_0/slice_00002.db").unlink()
    if axis in ("sourceFile", "hash", "version", "metadata"):
        manifest_path.write_text(json.dumps(data))
    before = hashes(first.db_path)
    with pytest.raises(ImportExecutionError, match="preserved even under --force"):
        service.import_snapshot(dataclasses.replace(request, force=force))
    assert hashes(first.db_path) == before
    assert (tmp_path / ".pt-snap/focus.json").read_bytes() == focus


@pytest.mark.parametrize("kind", ["empty", "unknown", "external", "file", "symlink", "dangling"])
def test_original_external_user_targets_preserved_under_force(tmp_path, kind):
    request = options(tmp_path)
    target = request.output_dir / "input.pkl.msinsight"
    target.parent.mkdir()
    if kind in ("symlink", "dangling"):
        victim = tmp_path / "victim"
        if kind == "symlink":
            victim.mkdir()
            (victim / "owner").write_text("safe")
        target.symlink_to(victim, target_is_directory=True)
    elif kind == "file":
        target.write_bytes(b"user bytes")
    else:
        target.mkdir()
        if kind == "external":
            # A genuine valid base artifact still lacks pt-snap ownership.
            from tests.test_dataset_focus import make_dataset

            external = make_dataset(tmp_path / "external", devices=(0,), slices=1)
            import shutil

            shutil.copytree(external, target, dirs_exist_ok=True)
        if kind != "empty":
            (target / "owner").write_text("safe")
    before = (
        hashes(target) if target.is_dir() else target.read_bytes() if target.is_file() else None
    )
    with pytest.raises(ImportExecutionError):
        ImportService().import_snapshot(dataclasses.replace(request, force=True))
    assert target.exists() or target.is_symlink()
    if target.is_dir():
        assert hashes(target) == before
    if kind == "file":
        assert target.read_bytes() == before
    if kind == "symlink":
        assert (victim / "owner").read_text() == "safe"
    assert not (tmp_path / ".pt-snap").exists()


@pytest.mark.parametrize(
    "kind", ["nonzero", "sparse", "oom", "unknown", "empty", "static-only", "empty-selection"]
)
def test_unsupported_input_fails_without_publication_or_focus(tmp_path, kind):
    request = options(tmp_path)
    data = lifecycle_data()
    data["device_traces"][0] = [e for e in data["device_traces"][0] if e["action"] != "oom"]
    if kind in ("nonzero", "sparse"):
        for index, event in enumerate(data["device_traces"][0]):
            event["id"] = index + 1 if kind == "nonzero" else index * 2
    elif kind in ("oom", "unknown"):
        data["device_traces"][0][0]["action"] = "oom" if kind == "oom" else "unknown"
    elif kind == "empty":
        data = {"segments": [], "device_traces": [[]]}
    elif kind == "static-only":
        data["device_traces"] = [[]]
    else:
        data["device_traces"].append([])
        request = dataclasses.replace(request, device=1)
    write_source(tmp_path, data)
    with pytest.raises(ImportExecutionError):
        ImportService().import_snapshot(request)
    assert not list(request.output_dir.iterdir())
    assert not (tmp_path / ".pt-snap").exists()


@pytest.mark.parametrize(
    "phase", ["conversion", "metadata", "validation", "source", "focus", "rename", "race"]
)
def test_failures_preserve_old_focus_and_unknown_owner(tmp_path, monkeypatch, phase):
    request = options(tmp_path)
    old = tmp_path / ".pt-snap/focus.json"
    old.parent.mkdir()
    old.write_bytes(b'{"db_path":"/old/path","device_id":0}')
    before = old.read_bytes()
    service = ImportService()
    target = request.output_dir / "input.pkl.msinsight"

    def fail(*a, **k):
        raise OSError("injected " + phase)

    if phase == "conversion":
        monkeypatch.setattr("pt_snap_cli.core.import_service.convert_shards", fail)
    elif phase == "metadata":
        monkeypatch.setattr(service._metadata_service, "write", fail)
    elif phase == "validation":
        monkeypatch.setattr("pt_snap_cli.core.import_service.inspect_owned_cache", fail)
    elif phase == "source":
        monkeypatch.setattr(
            service,
            "_recheck_source",
            lambda *a: (_ for _ in ()).throw(SourceChangedError("source changed")),
        )
    elif phase == "focus":
        fs = FocusService()
        service._focus_service = fs

        def mutate(*a, **k):
            old.write_bytes(b"changed")
            fail()

        monkeypatch.setattr(fs._config, "write_project_focus", mutate)
    else:
        move = service._msinsight_backend._move

        def fault(source, destination, identity):
            if phase == "race":
                destination.mkdir()
                (destination / "owner").write_text("safe")
            else:
                move(source, destination, identity)
                fail()
            move(source, destination, identity)

        monkeypatch.setattr(service._msinsight_backend, "_move", fault)
    with pytest.raises(ImportExecutionError):
        service.import_snapshot(request)
    assert old.read_bytes() == before
    if phase == "race":
        assert (target / "owner").read_text() == "safe"
    else:
        assert not target.exists()


def test_cli_json_explicit_mode_default_adjacency_and_api_focus_parity(
    tmp_path, monkeypatch, capsys
):
    request = options(tmp_path, capacity=None)
    args = ["import", str(request.snapshot_file), "--format", "msinsight", "--json"]
    runner = CliRunner()
    result = runner.invoke(app, args)
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["format"] == "compatibility-v1" and data["slice_count"] == 1
    assert data["db_path"] == str(request.snapshot_file) + ".msinsight"
    with SnapshotAnalyzer(data["db_path"]) as analyzer:
        assert (
            analyzer.get_focus().callstack_layout == data["focus_state"]["callstack_layout"] == "v1"
        )
        cli = runner.invoke(
            app,
            ["query", data["db_path"], "--template-use", "event", "--params", '{"id":3}', "--json"],
        )
        assert cli.exit_code == 0
        assert json.loads(cli.output)["rows"] == analyzer.execute_query("event", {"id": 3})["rows"]
    reused = runner.invoke(app, [*args, "--force", "--no-focus"])
    assert reused.exit_code == 0 and json.loads(reused.output)["reused"]
    monkeypatch.setattr("sys.argv", ["pt-snap", *args, "--events-per-slice", "0"])
    assert _safe_call() != 0
    assert json.loads(capsys.readouterr().err)["error"]["code"] == "INVALID_PARAMETER"
