"""Offline harness guard regressions; real installed runs remain a separate gate."""

from __future__ import annotations

import importlib.util
import json
import os
import shlex
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github/scripts/clean_wheel_agent_acceptance.py"


@pytest.fixture
def acceptance():
    spec = importlib.util.spec_from_file_location("clean_wheel_agent_acceptance", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sharded_mode_is_explicit_and_requires_positive_capacity(acceptance):
    required = ["--wheel", "current.whl", "--fixture", "reviewed.pkl"]
    args = acceptance._parse_args(required)
    assert args.events_per_slice is None and args.wheelhouse is None
    args = acceptance._parse_args(
        [*required, "--events-per-slice", "4096", "--wheelhouse", "wheels"]
    )
    assert args.events_per_slice == 4096 and args.wheelhouse == Path("wheels")
    for value in ("0", "-1", "2.5", "false"):
        with pytest.raises(SystemExit) as exc:
            acceptance._parse_args([*required, "--events-per-slice", value])
        assert exc.value.code == 2


def test_environment_clears_source_focus_hosts_and_resource_overrides(
    acceptance, tmp_path, monkeypatch
):
    inherited = (
        *acceptance.CLEARED_ENV,
        "PYTHONHOME",
        "PYTHONUSERBASE",
        "PT_SNAP_QUERY_TIMEOUT",
        "PT_SNAP_MAX_WORK_ROWS",
        "PT_SNAP_MAX_WORK_BYTES",
        "PT_SNAP_MAX_SCRATCH_DB_BYTES",
        "PIP_FIND_LINKS",
        "PIP_TARGET",
        "PIP_REQUIREMENT",
    )
    for key in inherited:
        monkeypatch.setenv(key, "must-not-leak")
    env = acceptance._isolated_environment(
        tmp_path / "home", tmp_path / "cwd", tmp_path / "venv", tmp_path / "venv/bin"
    )
    assert not set(inherited) & env.keys()
    assert env["HOME"] == env["USERPROFILE"] == str(tmp_path / "home")
    assert env["XDG_CONFIG_HOME"] == str(tmp_path / "home/.config")
    assert env["PYTHONNOUSERSITE"] == "1"
    assert env["PIP_CONFIG_FILE"] == os.devnull
    assert env["PATH"].split(os.pathsep)[0] == str(tmp_path / "venv/bin")
    assert os.environ["PT_SNAP_DB_PATH"] == "must-not-leak"


def test_ci_runs_audited_wheel_with_explicit_sharded_capacity():
    workflow = yaml.load((ROOT / ".github/workflows/test.yml").read_text(), Loader=yaml.BaseLoader)
    steps = workflow["jobs"]["test"]["steps"]
    by_name = {step.get("name"): step for step in steps}
    step = by_name["Clean-wheel Agent acceptance"]
    assert step["if"] == "matrix.python-version == '3.13'"
    assert "continue-on-error" not in step
    command = step["run"].split("python .github/scripts/clean_wheel_agent_acceptance.py", 1)[1]
    assert shlex.split(command.replace("\\\n", " ")) == [
        "--wheel",
        "$WHEEL",
        "--fixture",
        "tests/fixtures/snapshots/snapshot_with_empty_cache.pkl",
        "--events-per-slice",
        "4096",
    ]
    names = list(by_name)
    assert (
        names.index("Build wheel")
        < names.index("Audit wheel contents against source")
        < names.index("Clean-wheel Agent acceptance")
    )


@pytest.mark.parametrize("payload", [{"ok": True, "rows": []}, {"skills": []}])
def test_json_accepts_public_envelope_and_legacy_catalog(acceptance, tmp_path, payload):
    result = acceptance._run_json(
        [sys.executable, "-c", f"print({json.dumps(payload)!r})"],
        cwd=tmp_path,
        env=os.environ.copy(),
        label="public JSON",
    )
    assert result == payload


@pytest.mark.parametrize(
    ("script", "error"),
    [
        ("print('[]')", "non-object"),
        ("print('log noise\\n{}')", "complete JSON"),
        ("print('{')", "complete JSON"),
        ("print('{\"ok\": false}')", "JSON success"),
        ("import sys; print('{}'); print('warning', file=sys.stderr)", "wrote to stderr"),
        ("import sys; print('{}'); sys.exit(2)", "exited with 2"),
    ],
)
def test_json_rejects_hollow_success(acceptance, tmp_path, script, error):
    with pytest.raises(acceptance.AcceptanceError, match=error):
        acceptance._run_json(
            [sys.executable, "-c", script], cwd=tmp_path, env=os.environ.copy(), label="bad JSON"
        )


def test_unapproved_fixture_is_rejected_before_any_execution(acceptance, tmp_path, monkeypatch):
    wheel = tmp_path / "standin.whl"
    wheel.write_bytes(b"not installed")
    fixture = tmp_path / "arbitrary.pkl"
    fixture.write_bytes(b"never loaded")
    monkeypatch.setattr(
        acceptance, "_run", lambda *_a, **_k: pytest.fail("executed before trust check")
    )
    with pytest.raises(acceptance.AcceptanceError, match="Unexpected snapshot fixture"):
        acceptance._run_acceptance(wheel, fixture, 4096)


@pytest.mark.parametrize("failure", ["wheel/source audit", "fixture provenance gate"])
def test_audit_and_provenance_fail_before_install_or_import(
    acceptance, tmp_path, monkeypatch, failure
):
    wheel = tmp_path / "standin.whl"
    wheel.write_bytes(b"guard test, never installed")
    labels = []

    def run(command, *, cwd, env, label, **kwargs):
        labels.append(label)
        assert cwd != ROOT
        assert "PYTHONPATH" not in env
        if label == failure:
            raise acceptance.AcceptanceError(f"{failure} refused")

    monkeypatch.setattr(acceptance, "_run", run)
    monkeypatch.setattr(
        acceptance.venv, "EnvBuilder", lambda **_k: pytest.fail("venv created before guards")
    )
    with pytest.raises(acceptance.AcceptanceError, match="refused"):
        acceptance._run_acceptance(
            wheel, ROOT / "tests/fixtures/snapshots/snapshot_with_empty_cache.pkl", 4096
        )
    assert labels == ["wheel/source audit"] + (
        ["fixture provenance gate"] if failure == "fixture provenance gate" else []
    )


@pytest.mark.parametrize("name", ["pt-snap-helper", "pt-snap-memory-peak-breakdown"])
def test_dataset_skill_guard_rejects_missing_discovery_contract(acceptance, name):
    text = (ROOT / "src/pt_snap_cli/bundled_skills" / name / "SKILL.md").read_text()
    acceptance._check_dataset_skill(text, name)
    for token in (
        "overview.dataset.status",
        "manifest_path",
        "fingerprint",
        "dataset_support.supported",
        "scope.range_complete",
        "scope.source_coverage.range_complete",
    ):
        with pytest.raises(acceptance.AcceptanceError, match="omits dataset guidance"):
            acceptance._check_dataset_skill(text.replace(token, "removed"), name)


def _overview(root, *, manifest=False):
    target = root / "manifest.json" if manifest else root
    return {
        "db_path": str(target),
        "focus_source": "explicit",
        "import_metadata": {"status": "available"},
        "dataset": {
            "status": "complete",
            "format": "pt-snap-native-v2",
            "manifest_path": str(root / "manifest.json"),
            "fingerprint": "generation-1",
            "cross_slice_queries": True,
        },
    }


@pytest.mark.parametrize("manifest", [False, True])
def test_dataset_discovery_accepts_directory_and_manifest(acceptance, tmp_path, manifest):
    overview = _overview(tmp_path, manifest=manifest)
    assert (
        acceptance._dataset_overview(
            overview, Path(overview["db_path"]), tmp_path, "pt-snap-native-v2"
        )
        is overview["dataset"]
    )


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("db_path",), "/wrong"),
        (("focus_source",), "project"),
        (("import_metadata", "status"), "invalid"),
        (("dataset", "status"), "incomplete"),
        (("dataset", "format"), "single-db"),
        (("dataset", "fingerprint"), ""),
        (("dataset", "manifest_path"), "/wrong/manifest.json"),
        (("dataset", "cross_slice_queries"), False),
    ],
)
def test_dataset_discovery_rejects_unsafe_or_incomplete_evidence(acceptance, tmp_path, path, value):
    overview = _overview(tmp_path)
    target = overview if len(path) == 1 else overview[path[0]]
    target[path[-1]] = value
    with pytest.raises(acceptance.AcceptanceError):
        acceptance._dataset_overview(overview, tmp_path, tmp_path, "pt-snap-native-v2")


def _query(root):
    return {
        "db_path": str(root),
        "focus_source": "explicit",
        "device_id": 0,
        "rows": [{"id": 4096}],
        "returned": 1,
        "has_more": False,
        "truncated": False,
        "scope": {
            "dataset_path": str(root),
            "fingerprint": "generation-1",
            "range_complete": True,
            "boundary_events_included": False,
        },
    }


def test_dataset_query_keeps_generation_and_completeness_separate(acceptance, tmp_path):
    query = _query(tmp_path)
    assert acceptance._dataset_query(query, tmp_path, tmp_path, "generation-1", 0) is query["scope"]


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("db_path",), "/wrong"),
        (("focus_source",), "project"),
        (("device_id",), 1),
        (("returned",), 2),
        (("rows",), None),
        (("has_more",), True),
        (("truncated",), True),
        (("scope", "dataset_path"), "/wrong"),
        (("scope", "fingerprint"), "generation-2"),
        (("scope", "range_complete"), False),
        (("scope", "boundary_events_included"), True),
    ],
)
def test_dataset_query_rejects_misleading_success(acceptance, tmp_path, path, value):
    query = _query(tmp_path)
    target = query if len(path) == 1 else query[path[0]]
    target[path[-1]] = value
    with pytest.raises(acceptance.AcceptanceError):
        acceptance._dataset_query(query, tmp_path, tmp_path, "generation-1", 0)


def test_one_physical_shard_cannot_pass_sharded_acceptance(acceptance, tmp_path, monkeypatch):
    dataset = tmp_path / "one-shard"
    dataset.mkdir()
    member = dataset / "slice_00000.db"
    member.write_bytes(b"never opened")
    focus = tmp_path / "focus.json"
    focus.write_text("unchanged")
    overview = _overview(dataset)
    overview["devices"] = [{"device_id": 0, "first_event_id": 0, "last_event_id": 1}]
    overview["dataset"]["devices"] = [
        {
            "device_id": 0,
            "event_count": 2,
            "slices": [
                {"index": 0, "db_path": str(member), "first_event_id": 0, "last_event_id": 1}
            ],
        }
    ]
    commands = []

    def cli(command, **kwargs):
        commands.append(command)
        if command[1] == "overview":
            return overview
        assert command[1] == "import" and "--no-focus" in command
        reused = len(commands) == 2
        return {
            "dataset_path": str(dataset),
            "db_path": str(dataset),
            "format": "pt-snap-native-v2",
            "rebuilt": not reused,
            "reused": reused,
            "focus_state": None,
            "slice_count": 1,
        }

    monkeypatch.setattr(acceptance, "_run_json", cli)
    with pytest.raises(acceptance.AcceptanceError, match="at least two slices"):
        acceptance._sharded_acceptance(
            Path("pt-snap"),
            tmp_path / "fixture.pkl",
            tmp_path,
            10000,
            tmp_path / "standalone.db",
            overview,
            {"device_id": 0},
            focus,
            cwd=tmp_path,
            env={},
        )
    assert [command[1] for command in commands] == ["import", "import", "overview"]
    assert focus.read_text() == "unchanged"
