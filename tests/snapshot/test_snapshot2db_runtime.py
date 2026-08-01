import sqlite3
from pathlib import Path

import pytest

from pt_snap_cli.snapshot.tools.adaptors import snapshot2db
from pt_snap_cli.snapshot.tools.adaptors.database import (
    BLOCK_STATE_VALUE_MAP as RUNTIME_BLOCK_STATE_VALUE_MAP,
)
from pt_snap_cli.snapshot.tools.adaptors.database import (
    TRACE_ENTRY_ACTION_VALUE_MAP as RUNTIME_ACTION_VALUE_MAP,
)
from pt_snap_cli.snapshot.util.logger import restore_logs, suppress_logs

from .golden_observations import (
    ACTION_VALUE_MAP,
    BLOCK_SCHEMA,
    BLOCK_STATE_VALUE_MAP,
    DATABASE_GOLDEN,
    TRACE_SCHEMA,
)
from .helpers import FIXTURE_DIR


@pytest.fixture(scope="module")
def dump_database(tmp_path_factory):
    output_dir = tmp_path_factory.mktemp("snapshot-runtime-db")
    cache = {}

    def dump(fixture_name, device=None):
        key = (fixture_name, device)
        if key not in cache:
            suffix = "all" if device is None else str(device)
            output = output_dir / f"{fixture_name}.{suffix}.db"
            suppress_logs()
            try:
                result = snapshot2db.dump(FIXTURE_DIR / fixture_name, output, device)
            finally:
                restore_logs()
            cache[key] = (result, output)
        return cache[key]

    return dump


def test_snapshot2db(dump_database):
    result, database = dump_database("snapshot_with_empty_cache.pkl", 0)

    assert result is True
    assert database.exists()
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM trace_entry_0").fetchone()[0] == 8189
        assert connection.execute("SELECT COUNT(*) FROM block_0").fetchone()[0] == 3219


def test_snapshot2db_uses_shared_load_and_replay_entrypoints(monkeypatch, tmp_path):
    database = tmp_path / "shared-entrypoints.db"
    original_load = snapshot2db.load_snapshot_representation
    original_replay = snapshot2db.replay_snapshot
    calls = {"load": 0, "replay": 0}

    def load(snapshot_file):
        calls["load"] += 1
        return original_load(snapshot_file)

    def replay(representation, device, **kwargs):
        calls["replay"] += 1
        return original_replay(representation, device, **kwargs)

    monkeypatch.setattr(snapshot2db, "load_snapshot_representation", load)
    monkeypatch.setattr(snapshot2db, "replay_snapshot", replay)

    assert snapshot2db.dump(FIXTURE_DIR / "snapshot_with_empty_cache.pkl", database, 0)
    assert calls == {"load": 1, "replay": 1}


def test_expandable_snapshot2db(dump_database):
    result, database = dump_database("snapshot_with_empty_cache_expandable.pkl", 0)

    assert result is True
    assert database.exists()
    with sqlite3.connect(database) as connection:
        assert connection.execute("SELECT COUNT(*) FROM trace_entry_0").fetchone()[0] == 8134
        assert connection.execute("SELECT COUNT(*) FROM block_0").fetchone()[0] == 3219


def test_empty_device_snapshot(tmp_path: Path):
    database = tmp_path / "empty.db"

    assert snapshot2db.dump(FIXTURE_DIR / "snapshot_with_empty_cache.pkl", database, 1) is False
    assert not database.exists()


def test_dump_all_multiple_device_snapshot(dump_database):
    result, database = dump_database("snapshot_with_multi_devices.pkl")

    assert result is True
    assert database.exists()
    with sqlite3.connect(database) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
    assert tables == {"dictionary", "trace_entry_0", "block_0", "trace_entry_1", "block_1"}


def negative_id_observation(connection, table):
    count, minimum, maximum = connection.execute(
        f"SELECT COUNT(*), MIN(id), MAX(id) FROM {table} WHERE id < 0"
    ).fetchone()
    contiguous = count == 0 or maximum - minimum + 1 == count
    return count, contiguous


@pytest.mark.parametrize(("fixture_name", "device"), DATABASE_GOLDEN)
def test_database_matches_pre_relocation_golden(dump_database, fixture_name, device):
    requested_device = None if fixture_name == "snapshot_with_multi_devices.pkl" else device
    result, database = dump_database(fixture_name, requested_device)
    golden = DATABASE_GOLDEN[(fixture_name, device)]
    trace_table = f"trace_entry_{device}"
    block_table = f"block_{device}"

    assert result is True
    with sqlite3.connect(database) as connection:
        rows = (
            connection.execute(f"SELECT COUNT(*) FROM {trace_table}").fetchone()[0],
            connection.execute(f"SELECT COUNT(*) FROM {block_table}").fetchone()[0],
        )
        actions = dict(
            connection.execute(
                f"SELECT action, COUNT(*) FROM {trace_table} GROUP BY action ORDER BY action"
            ).fetchall()
        )
        first_totals = connection.execute(
            f"SELECT allocated, active, reserved FROM {trace_table} ORDER BY id LIMIT 1"
        ).fetchone()
        last_positive_totals = connection.execute(
            f"SELECT allocated, active, reserved FROM {trace_table} "
            "WHERE id >= 0 ORDER BY id DESC LIMIT 1"
        ).fetchone()
        callstacks = connection.execute(
            f"SELECT COUNT(*) FROM {trace_table} WHERE callstack != ''"
        ).fetchone()[0]

        assert rows == golden["rows"]
        assert actions == golden["actions"]
        assert negative_id_observation(connection, trace_table) == (
            golden["synthetic"][0],
            True,
        )
        assert negative_id_observation(connection, block_table) == (
            golden["synthetic"][1],
            True,
        )
        assert first_totals == golden["first_totals"]
        assert last_positive_totals == golden["last_positive_totals"]
        assert callstacks == golden["nonempty_callstacks"]


def test_database_schema_and_action_state_mapping_are_exact(dump_database):
    _, database = dump_database("snapshot_with_multi_devices.pkl")

    assert RUNTIME_ACTION_VALUE_MAP == ACTION_VALUE_MAP
    assert RUNTIME_BLOCK_STATE_VALUE_MAP == BLOCK_STATE_VALUE_MAP
    with sqlite3.connect(database) as connection:
        for device in (0, 1):
            assert (
                connection.execute(f"PRAGMA table_info(trace_entry_{device})").fetchall()
                == TRACE_SCHEMA
            )
            assert (
                connection.execute(f"PRAGMA table_info(block_{device})").fetchall() == BLOCK_SCHEMA
            )
            dictionary = connection.execute(
                "SELECT `table`, `column`, `key`, `value` FROM dictionary "
                "WHERE `table` IN (?, ?) ORDER BY `table`, `column`, CAST(`key` AS INTEGER)",
                (f"block_{device}", f"trace_entry_{device}"),
            ).fetchall()
            assert dictionary == [
                (f"block_{device}", "state", "-1", "inactive"),
                (f"block_{device}", "state", "0", "active_pending_free"),
                (f"block_{device}", "state", "1", "active_allocated"),
                *[
                    (f"trace_entry_{device}", "action", str(value), action)
                    for action, value in ACTION_VALUE_MAP.items()
                ],
            ]


def test_multi_device_database_rows_are_isolated(dump_database):
    _, database = dump_database("snapshot_with_multi_devices.pkl")
    with sqlite3.connect(database) as connection:
        device_zero = connection.execute(
            "SELECT COUNT(*), SUM(size), MAX(reserved) FROM trace_entry_0"
        ).fetchone()
        device_one = connection.execute(
            "SELECT COUNT(*), SUM(size), MAX(reserved) FROM trace_entry_1"
        ).fetchone()

    assert device_zero != device_one
    assert device_zero[0] == DATABASE_GOLDEN[("snapshot_with_multi_devices.pkl", 0)]["rows"][0]
    assert device_one[0] == DATABASE_GOLDEN[("snapshot_with_multi_devices.pkl", 1)]["rows"][0]


def test_callstack_serialization_preserves_frame_order(dump_database):
    _, database = dump_database("snapshot_1768383987920985470.pkl", 0)
    with sqlite3.connect(database) as connection:
        callstack = connection.execute(
            "SELECT callstack FROM trace_entry_0 WHERE callstack LIKE '%\n%' LIMIT 1"
        ).fetchone()[0]

    lines = callstack.splitlines()
    assert len(lines) >= 2
    assert all(":" in line and " " in line for line in lines)
