"""Static agent policy plus real CLI payloads; no live model execution."""

import json
import re
import shlex
import sqlite3
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pt_snap_cli.cli import app
from pt_snap_cli.core.import_metadata import ImportMetadataService
from pt_snap_cli.query import registry

ROOT = Path(__file__).resolve().parents[2]
DIAGNOSTICS = (
    "pt-snap-memory-leak",
    "pt-snap-memory-peak-breakdown",
    "pt-snap-memory-fragmentation",
)
runner = CliRunner()


def _skill(name: str) -> str:
    return (ROOT / "skills" / name / "SKILL.md").read_text()


def _preflight(name: str) -> str:
    return _skill(name).split("### 3. Verify capabilities", 1)[1].split("\n## ", 1)[0]


def _required(name: str) -> set[str]:
    sentence = (
        _preflight(name)
        .split("Confirm these templates exist in the capabilities catalog before diagnosis:", 1)[1]
        .split(".", 1)[0]
    )
    return set(re.findall(r"`(\w+)`", sentence))


@pytest.mark.parametrize("name", ("pt-snap-helper", *DIAGNOSTICS))
def test_shared_preflight_checks_nested_metadata_and_reuse_identity(name: str) -> None:
    text = " ".join(_skill(name).split())
    for instruction in (
        "`overview.import_metadata.status`",
        "not just exit code 0 or outer `ok: true`",
        "Stop on `invalid` metadata or schema errors",
        "`unavailable` and reason `metadata_missing`",
        "recording unknown import provenance",
        "Stop on any other status/reason or incomplete result",
        "CLI/Python environment and unchanged database target",
        "CLI version",
        "resolved absolute database path",
        "truncated output",
        "unknown result identity",
        "metadata-first exception",
        "Metadata alone does not replace overview",
        "tool-call count and output bytes",
    ):
        assert instruction in text


@pytest.mark.parametrize("name", DIAGNOSTICS)
def test_direct_invocation_validates_even_reused_results_without_extra_probes(name: str) -> None:
    text = " ".join(_preflight(name).split())
    assert "even on direct invocation" in text
    assert "Run only the probes whose complete results are not reusable" in text
    assert "Revalidate the contents even when reusing results" in text
    assert "2 calls from cold, 1 with one reusable result, 0 with both" in text
    assert "re-emit a reused catalog" in text
    assert "never reuse the missing target's overview or device" in text
    assert "missing" in text and "template" in text and "Stop" in text
    commands = [
        shlex.split(line)
        for block in re.findall(r"```bash\n(.*?)```", _preflight(name), re.S)
        for line in block.strip().splitlines()
    ]
    discovery = [cmd for cmd in commands if cmd[1] != "report"]
    assert discovery == [
        ["pt-snap", "capabilities", "--json"],
        ["pt-snap", "overview", "<DB>" if "peak" in name else "<db_path>", "--json"],
    ]
    if name != "pt-snap-memory-leak":
        assert commands.count(["pt-snap", "report", "peak-memory", "--help"]) == 1
        assert "Capabilities does not describe report command options" in text
    if name == "pt-snap-memory-fragmentation":
        assert "If using the report" in text
        assert "stop that phase and report the missing template if absent" in text


@pytest.fixture
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("PT_SNAP_DB_PATH", raising=False)
    monkeypatch.delenv("PT_SNAP_SKILLS_DIR", raising=False)
    path = tmp_path / "preflight.db"
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE dictionary (`table` TEXT, `column` TEXT, `key` TEXT, `value` TEXT)"
        )
        conn.execute("CREATE TABLE trace_entry_0 (id INTEGER PRIMARY KEY)")
        conn.execute("INSERT INTO trace_entry_0 VALUES (7)")
    return path


@pytest.mark.parametrize("name", DIAGNOSTICS)
def test_documented_discovery_commands_supply_contracts_and_measure_output(
    name: str, db: Path, record_property
) -> None:
    # Execute the actual fenced discovery block, not a separately invented plan.
    block = re.findall(r"```bash\n(.*?)```", _preflight(name), re.S)[0]
    commands = [
        shlex.split(line.replace("<db_path>", str(db)).replace("<DB>", str(db)))[1:]
        for line in block.strip().splitlines()
    ]
    results = [runner.invoke(app, args) for args in commands]
    assert len(results) == 2
    assert all(result.exit_code == 0 and not result.stderr for result in results)
    catalog, overview = [json.loads(result.stdout) for result in results]
    entries = {entry["name"]: entry for entry in catalog["templates"]}
    assert _required(name) <= entries.keys()
    assert overview["db_path"] == str(db.resolve())
    assert overview["devices"] == [{"device_id": 0, "first_event_id": 7, "last_event_id": 7}]

    # Equivalence justifies omitting these calls in the agent workflow. Count
    # their bytes separately: fewer calls does not imply a smaller cold catalog.
    redundant = [runner.invoke(app, ["metadata", str(db), "--json"])]
    for template in sorted(_required(name)):
        result = runner.invoke(app, ["query", "--template-info", template, "--json"])
        assert result.exit_code == 0
        info = json.loads(result.stdout)
        assert entries[template] == {key: info[key] for key in entries[template]}
        redundant.append(result)
    metadata = json.loads(redundant[0].stdout)
    assert overview["import_metadata"]["status"] == metadata["status"] == "unavailable"
    assert overview["import_metadata"]["reason"] == metadata["reason"] == "metadata_missing"
    discovery_bytes = sum(len(result.stdout.encode()) for result in results)
    redundant_bytes = sum(len(result.stdout.encode()) for result in redundant)
    assert discovery_bytes > 0 and redundant_bytes > 0
    record_property("discovery_calls", len(results))
    record_property("discovery_output_bytes", discovery_bytes)
    record_property("avoided_redundant_calls", len(redundant))
    record_property("avoided_redundant_output_bytes", redundant_bytes)


@pytest.mark.parametrize("name", DIAGNOSTICS)
def test_successful_catalog_can_be_missing_a_required_template(
    name: str, db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Simulate an installed catalog without a required core template. Outer
    # success is not sufficient; the skill's named-entry check must reject it.
    monkeypatch.delitem(registry._registry._queries, "memory_peak")
    result = runner.invoke(app, ["capabilities", "--json"])
    assert result.exit_code == 0
    catalog = json.loads(result.stdout)
    assert catalog["ok"] is True
    names = {entry["name"] for entry in catalog["templates"]}
    assert _required(name) - names == {"memory_peak"}


@pytest.mark.parametrize("state", ("legacy", "available", "invalid", "schema-error"))
def test_overview_status_drives_preflight_even_with_outer_success(db: Path, state: str) -> None:
    if state == "available":
        # Metadata construction does not deserialize any input.
        source = db.parent / "source.bin"
        source.write_bytes(b"metadata-only test input")
        service = ImportMetadataService()
        service.write(db, service.build_metadata(source, service.calculate_sha256(source), None))
    elif state == "invalid":
        with sqlite3.connect(db) as conn:
            conn.execute("CREATE TABLE pt_snap_metadata (id INTEGER)")
            conn.execute("INSERT INTO pt_snap_metadata VALUES (1)")
    elif state == "schema-error":
        with sqlite3.connect(db) as conn:
            conn.execute("DROP TABLE dictionary")
    result = runner.invoke(app, ["overview", str(db), "--json"])
    if state == "schema-error":
        assert result.exit_code != 0 and result.stdout == ""
        assert json.loads(result.stderr)["error"]["code"] == "DATABASE_SCHEMA_INVALID"
        return
    assert result.exit_code == 0
    overview = json.loads(result.stdout)
    assert overview["ok"] is True  # Keep the existing CLI success semantics.
    expected = "unavailable" if state == "legacy" else state
    assert overview["import_metadata"]["status"] == expected
    if state in {"legacy", "invalid"}:
        assert overview["import_metadata"]["reason"] == (
            "metadata_missing" if state == "legacy" else "metadata_invalid"
        )
