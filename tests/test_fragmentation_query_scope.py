"""Issue #180: execute the skill's peak/attribution commands on distinct scopes."""

import json
import shlex
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pt_snap_cli.cli import app

SKILL_PATH = Path(__file__).resolve().parents[1] / "skills/pt-snap-memory-fragmentation/SKILL.md"


@pytest.fixture
def scope_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("PT_SNAP_DB_PATH", raising=False)
    monkeypatch.delenv("PT_SNAP_QUERY_TIMEOUT", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    path = tmp_path / "scopes.db"
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.executescript("""
            CREATE TABLE dictionary (`table` TEXT, `column` TEXT, `key` TEXT, `value` TEXT);
            CREATE TABLE trace_entry_0 (
                id INTEGER PRIMARY KEY, allocated INTEGER, active INTEGER,
                reserved INTEGER, callstack TEXT
            );
            CREATE TABLE block_0 (
                id INTEGER PRIMARY KEY, size INTEGER, requestedSize INTEGER,
                allocEventId INTEGER, freeEventId INTEGER
            );
            INSERT INTO trace_entry_0 VALUES
                (-2, 1000, 1000, 2000, 'synthetic'),
                (2, 10, 10, 100, 'before-window'),
                (12, 30, 30, 100, 'bounded-peak'),
                (20, 10, 10, 100, ''),
                (25, 90, 90, 100, 'runtime-peak'),
                (30, 10, 10, 100, ''),
                (35, 50, 50, 100, 'late-peak'),
                (40, 0, 0, 100, ''),
                (45, NULL, NULL, NULL, 'unknown-counters');
            INSERT INTO block_0 VALUES
                (2, 10, 10, 2, 40),
                (12, 20, 20, 12, 20),
                (25, 80, 80, 25, 30),
                (35, 40, 40, 35, 40);
        """)
    return path


def skill_commands(section):
    return [line for line in section.splitlines() if line.startswith("pt-snap ")]


def run_skill_command(command, db_path, **values):
    command = command.replace("<db_path>", str(db_path)).replace("<device_id>", "0")
    for key, value in values.items():
        command = command.replace(f"<{key}>", str(value))
    args = shlex.split(command)[1:]
    if "--json" not in args:
        args.append("--json")
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 0, result.output
    return json.loads(result.stdout)


def range_peak_command(start_id, end_id):
    step = SKILL_PATH.read_text().split("### 1. Establish", 1)[1].split("### 2.", 1)[0]
    command = skill_commands(step)[0].replace("<range_start>", str(start_id))
    if end_id is not None:
        # Step 1 explicitly instructs adding this key for two-sided ranges.
        command = command.replace("}'", f',"end_id":{end_id}}}' + "'")
    return command


@pytest.mark.parametrize(
    "start_id,end_id,event_id,active_bytes,callstack",
    [
        (10, 20, 12, 30, "bounded-peak"),
        (30, None, 35, 50, "late-peak"),
        (0, None, 25, 90, "runtime-peak"),
    ],
    ids=["two-sided", "lower-bound-only", "default-runtime"],
)
def test_range_peak_drives_actual_attribution(
    scope_db, start_id, end_id, event_id, active_bytes, callstack
):
    peak = run_skill_command(range_peak_command(start_id, end_id), scope_db)["rows"][0]
    assert peak["peak_active_event_id"] == event_id
    assert peak["peak_active"] == active_bytes
    section = SKILL_PATH.read_text().split("#### Range-scoped attribution", 1)[1]
    commands = skill_commands(section.split("#### Separate full-trace comparison", 1)[0])
    assert len(commands) == 1
    attribution = run_skill_command(commands[0], scope_db, **peak)

    # Check the event actually passed through the CLI, not just peak selection.
    assert attribution["effective_params"]["event_id"] == event_id
    assert event_id >= start_id
    assert end_id is None or event_id <= end_id
    assert attribution["has_more"] is attribution["truncated"] is False
    assert sum(row["size_bytes"] for row in attribution["rows"]) == active_bytes
    assert {row["callstack"] for row in attribution["rows"]} == {"before-window", callstack}


@pytest.mark.parametrize("start_id,end_id", [(100, 110), (45, 45)], ids=["empty", "null"])
def test_range_without_usable_peak_cannot_supply_attribution_event(scope_db, start_id, end_id):
    peak = run_skill_command(range_peak_command(start_id, end_id), scope_db)["rows"][0]
    assert peak["peak_active"] is None
    assert peak["peak_active_event_id"] is None
    # Stop here per the skill; a report would select a different scope.


def test_explicit_full_trace_comparison_uses_its_own_peak(scope_db):
    with closing(sqlite3.connect(scope_db)) as conn, conn:
        conn.execute("DELETE FROM trace_entry_0 WHERE id < 0")
    section = SKILL_PATH.read_text().split("#### Separate full-trace comparison", 1)[1]
    commands = skill_commands(section.split("### 6.", 1)[0])
    assert len(commands) == 2
    peak = run_skill_command(commands[0], scope_db)["rows"][0]
    assert peak["peak_active_event_id"] == 25
    report = run_skill_command(commands[1], scope_db)
    assert report["event_id"] == peak["peak_active_event_id"]
    assert sum(row["size_bytes"] for row in report["callstack_groups"]) == peak["peak_active"]


def test_full_trace_real_peak_excludes_synthetic_boundary_and_drives_report(scope_db):
    section = SKILL_PATH.read_text().split("#### Separate full-trace comparison", 1)[1]
    commands = skill_commands(section.split("### 6.", 1)[0])
    peak = run_skill_command(commands[0], scope_db)["rows"][0]
    assert peak["peak_active_event_id"] == 25
    assert peak["peak_active"] == 90  # never the synthetic id=-2/value=1000
    report = run_skill_command(commands[1], scope_db)
    assert report["event_id"] == 25
    assert report["active_bytes_at_event"] == 90
    assert report["included_bytes"] == 90 and report["coverage_percent"] == 100
