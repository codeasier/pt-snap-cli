"""Offline harness guard regressions; real installed runs remain a separate gate."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shlex
import sys
from copy import deepcopy
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


def _frame_identity(frames, fingerprint="generation-1", device=0):
    canonical = json.dumps(
        frames, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"dataset:{fingerprint}:device:{device}:frames:sha256:{digest}"


def _standalone_query(root, template, rows):
    return {
        "db_path": str(root / "standalone.db"),
        "focus_source": "explicit",
        "device_id": 0,
        "template": template,
        "rows": rows,
        "returned": len(rows),
        "total": len(rows),
        "total_is_exact": True,
        "has_more": False,
        "truncated": False,
    }


def _event_parity_case(root):
    # Recursive duplicates and distinct neighbors make both deduplication and
    # reordering observable. Raw extras are checked by identity, not falsely
    # presented as fields exposed by standalone event_frames.
    leaf = {"filename": "tensor.py", "line": 1, "name": "leaf", "extra": {"flag": True}}
    frames = [
        leaf,
        {"filename": "model.py", "line": 20, "name": "forward"},
        deepcopy(leaf),
        {"filename": "train.py", "line": 30, "name": "train"},
    ]
    base = [
        {
            "id": 4095,
            "action": 4,
            "address": 4096,
            "size": 1,
            "stream": 0,
            "allocated": 1,
            "active": 1,
            "reserved": 4096,
            "callstack": "full callstack",
        },
        {
            "id": 4096,
            "action": 6,
            "address": 4096,
            "size": 1,
            "stream": 0,
            "allocated": 0,
            "active": 0,
            "reserved": 4096,
            "callstack": "",
        },
    ]
    reference = _standalone_query(root, "event", base)
    crossing = deepcopy(reference)
    crossing["db_path"] = str(root / "dataset")
    crossing["scope"] = {
        "source_coverage": {
            "range_complete": True,
            "event_position": "after",
            "coverage_scope": "returned_events",
            "events_resolved": 2,
            "ordered_frame_events": 2,
            "source_queries": 8,
        }
    }
    frame_references = {}
    for row, raw in zip(crossing["rows"], (frames, []), strict=True):
        identity = _frame_identity(raw)
        row.update(
            source_stack_id=identity,
            stack_id=identity,
            stack_kind="captured",
            text_kind="captured" if row["callstack"] else "missing",
            stack_event_id=row["id"],
            frames=raw,
            frames_status="ordered",
        )
        frame_references[row["id"]] = _standalone_query(
            root,
            "event_frames",
            [
                {
                    "event_id": row["id"],
                    "stack_id": 77,
                    "position": index,
                    "frame_id": (5, 9, 5, 11)[index],
                    **{key: frame[key] for key in ("filename", "line", "name")},
                }
                for index, frame in enumerate(raw)
            ],
        )
    return crossing, reference, frame_references


def _check_event_parity(acceptance, root, case):
    return acceptance._event_parity(
        *case,
        standalone=root / "standalone.db",
        fingerprint="generation-1",
        device=0,
        event_ids=[4095, 4096],
    )


def test_event_parity_accepts_ordered_recursive_and_empty_stacks(acceptance, tmp_path):
    case = _event_parity_case(tmp_path)
    unchanged = deepcopy(case)
    assert _check_event_parity(acceptance, tmp_path, case) == 4
    assert case == unchanged


@pytest.mark.parametrize(
    "field",
    ["id", "action", "address", "size", "stream", "allocated", "active", "reserved", "callstack"],
)
@pytest.mark.parametrize("damage", ["value", "missing", "type"])
def test_event_parity_never_masks_base_event_changes(acceptance, tmp_path, field, damage):
    case = _event_parity_case(tmp_path)
    row = case[0]["rows"][0]
    value = row[field]
    if damage == "missing":
        del row[field]
    elif damage == "value":
        row[field] = value + (" changed" if isinstance(value, str) else 1)
    else:
        row[field] = None if isinstance(value, str) else float(value)
    with pytest.raises(acceptance.AcceptanceError, match="base field|event fields"):
        _check_event_parity(acceptance, tmp_path, case)


@pytest.mark.parametrize(
    "damage", ["event_order", "missing_event", "unknown_field", "missing_detail"]
)
def test_event_parity_rejects_changed_event_shape_or_order(acceptance, tmp_path, damage):
    case = _event_parity_case(tmp_path)
    rows = case[0]["rows"]
    if damage == "event_order":
        rows.reverse()
    elif damage == "missing_event":
        rows.pop()
    elif damage == "unknown_field":
        rows[0]["unrecognized"] = "not silently stripped"
    else:
        del rows[0]["frames_status"]
    with pytest.raises(acceptance.AcceptanceError):
        _check_event_parity(acceptance, tmp_path, case)


@pytest.mark.parametrize(
    "damage",
    [
        "drop",
        "empty",
        "duplicate",
        "reorder",
        "filename",
        "line",
        "name",
        "missing_field",
        "float_line",
        "bool_line",
    ],
)
def test_event_parity_rejects_frame_damage_even_with_updated_identity(acceptance, tmp_path, damage):
    case = _event_parity_case(tmp_path)
    row = case[0]["rows"][0]
    frames = row["frames"]
    if damage == "drop":
        frames.pop(2)
    elif damage == "empty":
        frames.clear()
    elif damage == "duplicate":
        frames.append(deepcopy(frames[0]))
    elif damage == "reorder":
        frames.reverse()
    elif damage == "missing_field":
        del frames[0]["filename"]
    elif damage == "float_line":
        frames[0]["line"] = 1.0
    elif damage == "bool_line":
        frames[0]["line"] = True
    else:
        frames[0][damage] = 999 if damage == "line" else "corrupt"
    row["source_stack_id"] = row["stack_id"] = _frame_identity(frames)
    with pytest.raises(acceptance.AcceptanceError, match="ordered frame count|ordered frame field"):
        _check_event_parity(acceptance, tmp_path, case)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("frames", None),
        ("frames", ["not a frame"]),
        ("frames_status", "text_only"),
        ("stack_kind", "missing"),
        ("text_kind", "missing"),
        ("stack_event_id", 4096),
        ("stack_event_id", 4095.0),
        ("stack_id", "local:77"),
        ("source_stack_id", "local:77"),
    ],
)
def test_event_parity_requires_full_ordered_source_evidence(acceptance, tmp_path, field, value):
    case = _event_parity_case(tmp_path)
    case[0]["rows"][0][field] = value
    with pytest.raises(acceptance.AcceptanceError):
        _check_event_parity(acceptance, tmp_path, case)


@pytest.mark.parametrize("damage", ["fingerprint", "device", "digest", "extra_raw_field"])
def test_event_parity_checks_full_raw_digest_and_namespace(acceptance, tmp_path, damage):
    case = _event_parity_case(tmp_path)
    row = case[0]["rows"][0]
    if damage == "extra_raw_field":
        row["frames"][0]["extra"]["flag"] = False
    else:
        identity = _frame_identity(
            row["frames"],
            "generation-2" if damage == "fingerprint" else "generation-1",
            1 if damage == "device" else 0,
        )
        if damage == "digest":
            identity = identity[:-1] + ("0" if identity[-1] != "0" else "1")
        row["source_stack_id"] = row["stack_id"] = identity
    with pytest.raises(acceptance.AcceptanceError, match="identity/namespace"):
        _check_event_parity(acceptance, tmp_path, case)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("range_complete", False),
        ("event_position", "before"),
        ("coverage_scope", "all_events"),
        ("events_resolved", 1),
        ("events_resolved", 2.0),
        ("ordered_frame_events", 1),
        ("ordered_frame_events", 2.0),
        ("source_queries", 0),
        ("source_queries", True),
    ],
)
def test_event_parity_rejects_incomplete_or_misleading_source_coverage(
    acceptance, tmp_path, field, value
):
    case = _event_parity_case(tmp_path)
    case[0]["scope"]["source_coverage"][field] = value
    with pytest.raises(acceptance.AcceptanceError, match="source coverage"):
        _check_event_parity(acceptance, tmp_path, case)


@pytest.mark.parametrize("template", ["event", "event_frames"])
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("db_path", "/wrong"),
        ("focus_source", "project"),
        ("device_id", 1),
        ("device_id", False),
        ("template", "wrong"),
        ("returned", -1),
        ("total", -1),
        ("total_is_exact", False),
        ("has_more", True),
        ("truncated", True),
    ],
)
def test_event_parity_rejects_incomplete_or_wrong_standalone_reference(
    acceptance, tmp_path, template, field, value
):
    case = _event_parity_case(tmp_path)
    query = case[1] if template == "event" else case[2][4095]
    query[field] = value
    with pytest.raises(acceptance.AcceptanceError, match="Standalone"):
        _check_event_parity(acceptance, tmp_path, case)


@pytest.mark.parametrize(
    ("field", "value"),
    [("event_id", 4096), ("position", 1), ("position", False), ("frame_id", "5"), ("stack_id", -1)],
)
def test_event_parity_validates_frame_reference_locators(acceptance, tmp_path, field, value):
    case = _event_parity_case(tmp_path)
    case[2][4095]["rows"][0][field] = value
    with pytest.raises(acceptance.AcceptanceError, match="standalone frame"):
        _check_event_parity(acceptance, tmp_path, case)


@pytest.mark.parametrize(
    ("empty_boundary", "supplement_empty"), [(False, False), (True, False), (True, True)]
)
def test_sharded_cli_uses_independent_frame_references_for_both_formats(
    acceptance, tmp_path, monkeypatch, empty_boundary, supplement_empty
):
    focus = tmp_path / "focus.json"
    focus.write_text("unchanged")
    standalone = tmp_path / "standalone.db"
    devices = [{"device_id": 0, "first_event_id": 0, "last_event_id": 8191}]
    standalone_peak = {"device_id": 0, "rows": [{"peak_allocated": 1}]}
    payloads = {}
    for format_name in ("pt-snap-native-v2", "compatibility-v1"):
        root = tmp_path / format_name
        root.mkdir()
        members = []
        for index in (0, 1):
            member = root / f"slice_{index:05d}.db"
            member.write_bytes(b"not opened by mocked CLI")
            members.append(
                {
                    "index": index,
                    "db_path": str(member),
                    "first_event_id": index * 4096,
                    "last_event_id": (index + 1) * 4096 - 1,
                }
            )
        overview = _overview(root)
        overview["devices"] = devices
        overview["dataset"]["format"] = format_name
        overview["dataset"]["devices"] = [{"device_id": 0, "event_count": 8192, "slices": members}]
        payloads[format_name] = overview
    imports = {}
    calls = []
    crossing, reference, frame_references = _event_parity_case(tmp_path)
    captured = deepcopy(crossing["rows"][0])
    captured["id"] = captured["stack_event_id"] = 1
    captured_reference = deepcopy(reference["rows"][0])
    captured_reference["id"] = 1
    captured_frames = deepcopy(frame_references[4095])
    for row in captured_frames["rows"]:
        row["event_id"] = 1
    if supplement_empty:
        captured["frames"] = []
        captured["stack_id"] = captured["source_stack_id"] = _frame_identity([])
        captured_frames = _standalone_query(tmp_path, "event_frames", [])
    if empty_boundary:
        crossing["rows"][0]["frames"] = []
        crossing["rows"][0]["callstack"] = reference["rows"][0]["callstack"] = ""
        crossing["rows"][0]["text_kind"] = "missing"
        crossing["rows"][0]["stack_id"] = crossing["rows"][0]["source_stack_id"] = _frame_identity(
            []
        )
        frame_references[4095] = _standalone_query(tmp_path, "event_frames", [])

    def cli(command, **kwargs):
        calls.append(command)
        assert command[0] == "installed-pt-snap" and command[-1] == "--json"
        action = command[1]
        if action == "import":
            assert "--no-focus" in command
            name = command[command.index("--format") + 1]
            imports[name] = imports.get(name, 0) + 1
            return {
                "db_path": str(tmp_path / name),
                "dataset_path": str(tmp_path / name),
                "format": name,
                "rebuilt": imports[name] == 1,
                "reused": imports[name] == 2,
                "focus_state": None,
                "slice_count": 2,
            }
        target = Path(command[2])
        root = target.parent if target.name == "manifest.json" else target
        if action == "overview":
            result = deepcopy(payloads[root.name])
            result["db_path"] = str(target)
            return result
        assert action == "query"
        assert command[command.index("--device") + 1] == "0"
        template = command[command.index("--template-use") + 1]
        params = json.loads(command[command.index("--params") + 1]) if "--params" in command else {}
        if template == "event_frames":
            assert target == standalone and params["frame_order"] == "original"
            assert "--exact-total" in command
            return deepcopy(
                captured_frames if params["event_id"] == 1 else frame_references[params["event_id"]]
            )
        if target == standalone:
            assert template == "event"
            if params.get("limit") == 1:
                assert params == {
                    "min_id": 0,
                    "order_by": "callstack",
                    "order_dir": "DESC",
                    "limit": 1,
                }
                # This locator is deliberately paginated, unlike the proof queries.
                return {
                    **_standalone_query(tmp_path, "event", [captured_reference]),
                    "has_more": True,
                    "truncated": True,
                    "total_is_exact": False,
                }
            assert "--exact-total" in command
            return deepcopy(
                _standalone_query(tmp_path, "event", [captured_reference])
                if params.get("id") == 1
                else reference
            )
        query = _query(root)
        query["db_path"] = str(target)
        query["template"] = template
        query["scope"]["slice_indices"] = [0, 1]
        if template == "memory_peak":
            query["rows"] = standalone_peak["rows"]
            query["scope"]["actual_range"] = {"real_event_count": 8192}
        elif "id" in params:
            event_id = params["id"]
            query["scope"]["slice_indices"] = [event_id // 4096]
            query["scope"]["source_coverage"] = {"range_complete": True}
            query["rows"] = [{"id": event_id}]
            if event_id == 1:
                query["rows"] = [captured]
                query["scope"]["source_coverage"] = {
                    **crossing["scope"]["source_coverage"],
                    "events_resolved": 1,
                    "ordered_frame_events": 1,
                }
        else:
            assert params == {"min_id": 4095, "max_id": 4096}
            assert "--exact-total" in command
            query["rows"] = crossing["rows"]
            query["scope"].update(crossing["scope"])
        query.update(returned=len(query["rows"]), total=len(query["rows"]), total_is_exact=True)
        return deepcopy(query)

    monkeypatch.setattr(acceptance, "_run_json", cli)

    def run():
        return acceptance._sharded_acceptance(
            Path("installed-pt-snap"),
            tmp_path / "unused.pkl",
            tmp_path,
            4096,
            standalone,
            {"devices": devices},
            standalone_peak,
            focus,
            cwd=tmp_path,
            env={},
        )

    if supplement_empty:
        with pytest.raises(acceptance.AcceptanceError, match="no nonempty frame evidence"):
            run()
        assert focus.read_text() == "unchanged"
        return
    evidence = run()
    assert [item["format"] for item in evidence] == ["pt-snap-native-v2", "compatibility-v1"]
    assert all(
        item["ordered_frame_field_parity"] and item["nonempty_ordered_frames_checked"]
        for item in evidence
    )
    frame_calls = [command for command in calls if "event_frames" in command]
    assert len(frame_calls) == (6 if empty_boundary else 4)
    assert focus.read_text() == "unchanged"
