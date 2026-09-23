import stat
from pathlib import Path

import pytest

from pt_snap_cli.context import Context
from pt_snap_cli.query.executor import QueryExecutor
from pt_snap_cli.query.registry import QueryRegistry, _load_all_templates
from tests.skills.harness.descriptors import load_suite
from tests.skills.harness.fixtures import build_snapshotdb, load_fixture_definition

FIXTURE_DIRECTORY = Path("tests/skills/suites/pt-snap-memory-leak/fixtures")
E2E_FIXTURE_DIRECTORY = Path("tests/skills/suites/pt-snap-agent-e2e/fixtures")


@pytest.fixture(autouse=True)
def _reload_query_templates():
    QueryRegistry.reset()
    _load_all_templates()


@pytest.mark.parametrize(
    "definition_name",
    ["allocator-cache.yaml", "pending-free.yaml", "address-reuse.yaml"],
)
def test_synthetic_definitions_build_read_only_snapshotdbs(
    tmp_path: Path, definition_name: str
) -> None:
    definition_path = FIXTURE_DIRECTORY / definition_name
    output_path = tmp_path / definition_name.replace(".yaml", ".db")

    load_fixture_definition(definition_path)
    build_snapshotdb(definition_path, output_path)

    assert not output_path.stat().st_mode & stat.S_IWUSR
    assert Context(output_path).device_ids == [0]


def test_allocator_cache_fixture_matches_its_product_oracle(tmp_path: Path) -> None:
    output_path = tmp_path / "cache.db"
    build_snapshotdb(FIXTURE_DIRECTORY / "allocator-cache.yaml", output_path)
    executor = QueryExecutor(Context(output_path))

    peak = executor.execute_template("memory_peak", params={}, device_id=0)[0]
    gap = executor.execute_template("allocator_gap", params={}, device_id=0)[0]
    candidates = executor.execute_template("leak_detection", params={"min_size": 0}, device_id=0)

    assert peak["peak_reserved"] == 8192
    assert gap["active_at_reserved_peak"] == 1024
    assert gap["reserved_active_gap_at_reserved_peak"] == 7168
    assert candidates == []


def test_pending_free_fixture_exposes_requested_but_incomplete_release(tmp_path: Path) -> None:
    output_path = tmp_path / "pending-free.db"
    build_snapshotdb(FIXTURE_DIRECTORY / "pending-free.yaml", output_path)
    executor = QueryExecutor(Context(output_path))

    candidates = executor.execute_template("leak_detection", params={"min_size": 0}, device_id=0)
    events = executor.execute_template("event", params={"address": 8192}, device_id=0)

    assert [(row["size"], row["allocEventId"]) for row in candidates] == [(4096, 1)]
    assert [(row["id"], row["action"]) for row in events] == [(1, 4), (2, 5)]


@pytest.mark.parametrize(
    "definition_name",
    ["events.yaml", "multi-device.yaml", "live-blocks.yaml"],
)
def test_agent_e2e_definitions_build_read_only_snapshotdbs(
    tmp_path: Path, definition_name: str
) -> None:
    definition_path = E2E_FIXTURE_DIRECTORY / definition_name
    output_path = tmp_path / definition_name.replace(".yaml", ".db")

    load_fixture_definition(definition_path)
    build_snapshotdb(definition_path, output_path)

    assert not output_path.stat().st_mode & stat.S_IWUSR
    assert Context(output_path).device_ids[0] == 0


def test_multi_target_case_materializes_competing_databases(tmp_path: Path) -> None:
    suite = load_suite(Path("tests/skills/suites/pt-snap-agent-e2e/suite.yaml"))
    case = suite.case("explicit-multi-target")
    assert case.fixture is not None
    fixtures = (case.fixture, *case.additional_fixtures)

    outputs = [
        build_snapshotdb(fixture["definition_path"], tmp_path / Path(fixture["mount_path"]).name)
        for fixture in fixtures
    ]

    assert [output.name for output in outputs] == ["target.db", "other.db"]
    assert [Context(output).device_ids for output in outputs] == [[0, 1], [0]]


def test_no_device_fixture_builds_a_valid_read_only_snapshotdb(tmp_path: Path) -> None:
    output_path = tmp_path / "no-devices.db"

    build_snapshotdb(E2E_FIXTURE_DIRECTORY / "no-devices.yaml", output_path)

    assert not output_path.stat().st_mode & stat.S_IWUSR
    assert Context(output_path).device_ids == []


def test_events_fixture_has_four_trace_rows(tmp_path: Path) -> None:
    output_path = tmp_path / "events.db"
    build_snapshotdb(E2E_FIXTURE_DIRECTORY / "events.yaml", output_path)
    executor = QueryExecutor(Context(output_path))

    events = executor.execute_template("event", params={}, device_id=0)
    candidates = executor.execute_template("leak_detection", params={"min_size": 0}, device_id=0)

    assert [row["id"] for row in events] == [1, 2, 3, 4]
    assert [row["size"] for row in candidates] == [64, 48, 32, 16]


def test_multi_device_fixture_keeps_device_evidence_distinct(tmp_path: Path) -> None:
    output_path = tmp_path / "target.db"
    build_snapshotdb(E2E_FIXTURE_DIRECTORY / "multi-device.yaml", output_path)
    context = Context(output_path)
    executor = QueryExecutor(context)

    assert context.device_ids == [0, 1]
    device_0 = executor.execute_template("leak_detection", params={"min_size": 0}, device_id=0)
    device_1 = executor.execute_template("leak_detection", params={"min_size": 0}, device_id=1)

    assert [row["size"] for row in device_0] == [1024]
    assert [row["size"] for row in device_1] == [4096]


def test_live_blocks_fixture_exposes_end_of_trace_retention(tmp_path: Path) -> None:
    output_path = tmp_path / "live-blocks.db"
    build_snapshotdb(E2E_FIXTURE_DIRECTORY / "live-blocks.yaml", output_path)
    executor = QueryExecutor(Context(output_path))

    candidates = executor.execute_template("leak_detection", params={"min_size": 0}, device_id=0)

    assert [(row["size"], row["allocEventId"]) for row in candidates] == [(4096, 1)]


def test_address_reuse_fixture_keeps_allocation_identities_separate(tmp_path: Path) -> None:
    output_path = tmp_path / "address-reuse.db"
    build_snapshotdb(FIXTURE_DIRECTORY / "address-reuse.yaml", output_path)
    executor = QueryExecutor(Context(output_path))

    candidates = executor.execute_template("leak_detection", params={"min_size": 0}, device_id=0)
    blocks = executor.execute_template("block", params={"address": 12288}, device_id=0)
    events = executor.execute_template("event", params={"address": 12288}, device_id=0)

    assert [(row["id"], row["size"]) for row in candidates] == [(2, 4096)]
    assert {row["allocEventId"] for row in blocks} == {1, 3}
    assert [row["action"] for row in events] == [4, 6, 4]
