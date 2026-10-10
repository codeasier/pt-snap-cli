"""Default-budget scale gates, separated from the small differential suite.

Synthetic SQL tests do not claim producer coverage. The final test imports a
trusted test-owned snapshot through a non-editable installed CLI/exporter, then
uses that installation's CLI and Python API. Supply PT_SNAP_ACCEPTANCE_WHEEL to
run it; this is not live PyTorch/NPU capture or upstream msinsight GUI acceptance.
"""

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path

import pytest

from pt_snap_cli.api import SnapshotAnalyzer
from pt_snap_cli.core.dataset_contract import ACTION_NAMES, BLOCK_STATES
from pt_snap_cli.core.dataset_sources import QueryBudget
from pt_snap_cli.core.errors import QueryExecutionError
from pt_snap_cli.core.msinsight_export import DEFAULT_CAPACITY
from tests.core.dataset_lifecycle_fixtures import SCHEMA
from tests.snapshot.test_sharded_replay import block, event, segment, write_source
from tests.test_dataset_focus import hashes

pytestmark = pytest.mark.slow


@pytest.fixture(autouse=True)
def isolate(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("PT_SNAP_DB_PATH", raising=False)
    monkeypatch.delenv("PT_SNAP_QUERY_TIMEOUT", raising=False)


def scale_dataset(root, count, capacity, stack):
    """Bounded occupancy, repeated addresses, real lifecycle-window membership."""
    (root / "device_0").mkdir(parents=True)
    slices = []
    for index, lo in enumerate(range(0, count, capacity)):
        hi = min(count, lo + capacity) - 1
        file = f"device_0/slice_{index:05d}.db"
        with closing(sqlite3.connect(root / file)) as conn, conn:
            conn.executescript(SCHEMA)
            conn.executemany(
                "INSERT INTO dictionary VALUES (?,?,?,?)",
                [("trace_entry_0", "action", str(i), name) for i, name in enumerate(ACTION_NAMES)]
                + [("block_0", "state", str(i), name) for i, name in BLOCK_STATES],
            )
            conn.executemany(
                "INSERT INTO trace_entry_0 VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    (
                        at,
                        (4, 5, 6, 7)[at % 4],
                        1000 if at % 4 < 3 else 0,
                        16 if at % 4 < 3 else 0,
                        0,
                        16 if at % 4 == 0 else 0,
                        16 if at % 4 < 2 else 0,
                        4096,
                        stack,
                    )
                    for at in range(lo, hi + 1)
                ),
            )
            # Include a crossing lifecycle even when capacity is not a multiple of four.
            conn.executemany(
                "INSERT INTO block_0 VALUES (?,?,?,?,?,?,?)",
                (
                    (
                        alloc,
                        1000,
                        16,
                        16,
                        0 if alloc + 1 < lo else 1,
                        alloc,
                        alloc + 2 if alloc + 2 < count else -1,
                    )
                    for alloc in range(lo - lo % 4, hi + 1, 4)
                    if alloc + 2 >= lo
                ),
            )
            conn.execute(
                "INSERT INTO trace_entry_0 VALUES (-1,2,1000,4096,0,999999,999999,999999,'boundary')"
            )
            for metric in ("allocated", "active", "reserved"):
                conn.execute(f"CREATE INDEX trace_{metric} ON trace_entry_0 ({metric})")
        slices.append(
            {"index": index, "startEventId": lo, "endEventId": hi, "file": file, "ready": True}
        )
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "status": "complete",
                "sourceFile": "/synthetic/no-pickle",
                "cacheHash": "",
                "eventsPerSlice": capacity,
                "devices": {
                    "0": {
                        "eventCount": count,
                        "sliceCount": len(slices),
                        "readySlices": list(range(len(slices))),
                        "slices": slices,
                    }
                },
            }
        )
    )
    return root


@pytest.fixture(scope="module")
def default_scale(tmp_path_factory):
    assert DEFAULT_CAPACITY == 500_000
    budget = QueryBudget(None, time.monotonic())
    assert budget.max_work_rows == 100_000 and budget.max_work_bytes == 64 * 1024 * 1024
    return scale_dataset(
        tmp_path_factory.mktemp("default-scale") / "dataset",
        2 * DEFAULT_CAPACITY,
        DEFAULT_CAPACITY,
        "short",
    )


@pytest.mark.parametrize(
    "template,params,total",
    [
        ("memory_peak", {}, 1),
        ("allocator_gap", {}, 1),
        ("event", {"min_id": 0, "limit": 5}, 1_000_000),
        ("allocation", {"min_id": 0, "limit": 5}, 1_000_000),
        ("block", {"limit": 5}, 250_000),
        ("leak_detection", {"limit": 5}, 0),
        ("callstack_analysis", {"min_count": 1}, 1),
    ],
)
def test_two_default_shards_return_global_results_with_real_budgets(
    default_scale, template, params, total
):
    before = hashes(default_scale)
    with SnapshotAnalyzer(default_scale) as analyzer:
        result = analyzer.execute_query(template, params, exact_total=True)
    assert result["total"] == total and result["total_is_exact"]
    assert result["returned"] == min(total, 5)
    if template == "memory_peak":
        assert result["rows"][0]["peak_active"] == 16
        assert result["rows"][0]["peak_active_event_id"] == 0
    elif template == "callstack_analysis":
        assert result["rows"][0]["alloc_count"] == 1_000_000
        assert result["rows"][0]["total_size"] == 12_000_000
    assert hashes(default_scale) == before


def test_real_default_row_budget_still_rejects_unbounded_materialization(default_scale):
    with (
        SnapshotAnalyzer(default_scale) as analyzer,
        pytest.raises(QueryExecutionError, match="budget"),
    ):
        analyzer.execute_query("event", {"min_id": 0, "limit": 100_001})


def test_long_stack_aggregate_and_small_page_succeed_but_full_output_is_byte_bounded(tmp_path):
    root = scale_dataset(tmp_path / "long-stacks", 10_000, 5_000, "x" * 8192)
    before = hashes(root)
    with SnapshotAnalyzer(root) as analyzer:
        peak = analyzer.execute_query("memory_peak")["rows"][0]
        assert peak["peak_active"] == 16
        grouped = analyzer.execute_query("callstack_analysis", {"min_count": 1})
        assert grouped["rows"][0]["alloc_count"] == 10_000
        page = analyzer.execute_query("event", {"min_id": 0, "limit": 5}, exact_total=True)
        assert page["returned"] == 5 and page["total"] == 10_000
        with pytest.raises(QueryExecutionError, match="budget"):
            analyzer.execute_query("event", {"min_id": 0, "limit": -1})
    assert hashes(root) == before


def run(command, root, env):
    result = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"{command}\n{result.stdout}\n{result.stderr}"
    return result


@pytest.fixture
def installed_runtime(tmp_path):
    wheel_value = os.environ.get("PT_SNAP_ACCEPTANCE_WHEEL")
    if not wheel_value:
        pytest.skip("Set PT_SNAP_ACCEPTANCE_WHEEL to test a non-editable installed artifact")
    wheel = Path(wheel_value).resolve()
    assert wheel.is_file() and wheel.suffix == ".whl"
    target = tmp_path / "installed"
    env = os.environ.copy()
    env.pop("PYTHONHOME", None)
    env.pop("PT_SNAP_DB_PATH", None)
    env.pop("PT_SNAP_QUERY_TIMEOUT", None)
    env["PYTHONPATH"] = str(target)
    run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-index",
            "--target",
            str(target),
            str(wheel),
        ],
        tmp_path,
        env,
    )
    probe = run(
        [sys.executable, "-c", "import pt_snap_cli; print(pt_snap_cli.__file__)"], tmp_path, env
    )
    module = Path(probe.stdout.strip()).resolve()
    assert module.is_relative_to(target)
    cli = target / "bin" / "pt-snap"
    assert cli.is_file()
    return cli, env, module, hashlib.sha256(wheel.read_bytes()).hexdigest()


def test_installed_trusted_producer_default_export_cli_and_api(
    tmp_path, installed_runtime, record_property
):
    cli, env, module, wheel_hash = installed_runtime
    # Original, inspectable test-owned data. No committed or external pickle is loaded.
    # 500000 ends after free_requested; free_completed is in the next shard.
    count = DEFAULT_CAPACITY + 2
    traces = [event(("alloc", "free_requested", "free_completed")[i % 3]) for i in range(count)]
    data = {"segments": [segment(0, 64, [block(1000, 16, 16)])], "device_traces": [traces]}
    source = write_source(tmp_path, data)
    # The installed importer owns its own full input load; do not retain a second
    # 500002-event graph in the test process while it runs.
    del traces, data
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    started = time.perf_counter()
    imported = json.loads(
        run(
            [
                sys.executable,
                str(cli),
                "import",
                str(source),
                "--format",
                "msinsight",
                "--output-dir",
                str(tmp_path / "exported"),
                "--no-focus",
                "--json",
            ],
            tmp_path,
            env,
        ).stdout
    )
    import_seconds = time.perf_counter() - started
    root = Path(imported["db_path"])
    manifest = json.loads((root / "manifest.json").read_text())
    assert manifest["eventsPerSlice"] == DEFAULT_CAPACITY
    assert manifest["devices"]["0"]["eventCount"] == count
    slices = manifest["devices"]["0"]["slices"]
    assert [(s["startEventId"], s["endEventId"]) for s in slices] == [
        (0, 499_999),
        (500_000, 500_001),
    ]
    before = hashes(root)
    # Inspect actual producer membership before running any query.
    for item in slices:
        with closing(sqlite3.connect(root / item["file"])) as conn:
            assert (
                conn.execute(
                    "SELECT COUNT(*) FROM block_0 WHERE allocEventId>?", (item["endEventId"],)
                ).fetchone()[0]
                == 0
            )
            assert (
                conn.execute(
                    "SELECT COUNT(*) FROM block_0 WHERE freeEventId>=0 AND freeEventId<?",
                    (item["startEventId"],),
                ).fetchone()[0]
                == 0
            )
    with closing(sqlite3.connect(root / slices[1]["file"])) as conn:
        assert conn.execute(
            "SELECT allocEventId,freeEventId FROM block_0 ORDER BY id"
        ).fetchall() == [(499_998, 500_000), (500_001, -1)]
    peak = json.loads(
        run(
            [
                sys.executable,
                str(cli),
                "query",
                str(root),
                "--template-use",
                "memory_peak",
                "--json",
            ],
            tmp_path,
            env,
        ).stdout
    )
    assert peak["rows"][0]["peak_active"] == 16 and peak["rows"][0]["peak_active_event_id"] == 0
    api_script = """
import json, sys
from pt_snap_cli.api import SnapshotAnalyzer
from pt_snap_cli.core.report_service import ReportService
with SnapshotAnalyzer(sys.argv[1]) as analyzer:
    rows = analyzer.execute_query("event", {"min_id": 0, "limit": 5}, exact_total=True)
    assert rows["returned"] == 5 and rows["total"] == 500002
    peak = analyzer.execute_query("memory_peak")["rows"][0]
    assert peak["peak_active"] == 16 and peak["peak_active_event_id"] == 0
    before = analyzer.execute_query("active_blocks_at_event", {"event_id": 499999})
    after = analyzer.execute_query("active_blocks_at_event", {"event_id": 500000})
    assert [r["allocEventId"] for r in before["rows"]] == [499998]
    assert after["rows"] == []
    live = analyzer.execute_query("leak_detection", {"limit": 5})
    assert [r["allocEventId"] for r in live["rows"]] == [500001]
service = ReportService()
try:
    report = service.peak_memory_report(sys.argv[1], limit=-1)
    assert report.event_id == 0 and report.included_bytes == 16
    assert report.active_bytes_at_event == 16 and report.coverage_percent == 100
finally:
    service.close()
print(json.dumps({"query_total": rows["total"], "peak": peak, "report_bytes": report.included_bytes}))
"""
    result = json.loads(run([sys.executable, "-c", api_script, str(root)], tmp_path, env).stdout)
    assert result["query_total"] == count
    assert hashes(root) == before
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    evidence = {
        "scope": "test-owned snapshot producer -> installed pt-snap replay/export -> installed CLI/API; no live collector or upstream GUI",
        "module": str(module),
        "wheel_sha256": wheel_hash,
        "source_sha256": source_hash,
        "events": count,
        "events_per_slice": DEFAULT_CAPACITY,
        "slices": 2,
        "import_seconds": import_seconds,
        "result": result,
    }
    record_property("dataset_acceptance", json.dumps(evidence))
    (tmp_path / "acceptance.json").write_text(json.dumps(evidence, indent=2))
