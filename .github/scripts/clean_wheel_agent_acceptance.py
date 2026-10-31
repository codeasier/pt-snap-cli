"""Offline installed-CLI/skill acceptance, never a live agent/model evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path
from typing import Any

from click import unstyle


class AcceptanceError(RuntimeError):
    pass


CLEARED_ENV = (
    "PYTHONPATH",
    "PT_SNAP_SKILLS_DIR",
    "PT_SNAP_DB_PATH",
    "CLAUDE_CONFIG_DIR",
    "CODEX_HOME",
)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise AcceptanceError(message)


def _run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    label: str,
    clean_stderr: bool = False,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        raise AcceptanceError(f"Unable to run {label}: {exc}") from exc
    if result.returncode != 0:
        raise AcceptanceError(
            f"{label} exited with {result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    if clean_stderr and result.stderr:
        raise AcceptanceError(f"{label} wrote to stderr: {result.stderr}")
    return result


def _run_json(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    label: str,
) -> dict[str, Any]:
    result = _run(command, cwd=cwd, env=env, label=label, clean_stderr=True)
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise AcceptanceError(f"{label} did not return complete JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise AcceptanceError(f"{label} returned a non-object JSON value")
    # Skill/catalog payloads predate the common ok envelope. If one is present,
    # never accept a structured failure just because the process exited zero.
    _require("ok" not in payload or payload["ok"] is True, f"{label} did not report JSON success")
    return payload


def _skill_entry(payload: dict[str, Any], name: str, label: str) -> dict[str, Any]:
    skills = payload.get("skills")
    _require(isinstance(skills, list), f"{label} did not return a skills list")
    for item in skills:
        if isinstance(item, dict) and item.get("name") == name:
            return item
    raise AcceptanceError(f"{label} did not include {name}")


def _path_value(payload: dict[str, Any], key: str, label: str) -> Path:
    value = payload.get(key)
    _require(isinstance(value, str) and bool(value), f"{label} has no {key} path")
    return Path(value).resolve()


def _is_inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _venv_paths(venv_dir: Path) -> tuple[Path, Path]:
    if os.name == "nt":
        bin_dir = venv_dir / "Scripts"
        return bin_dir / "python.exe", bin_dir / "pt-snap.exe"
    bin_dir = venv_dir / "bin"
    return bin_dir / "python", bin_dir / "pt-snap"


def _isolated_environment(home: Path, cwd: Path, venv_dir: Path, bin_dir: Path) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("PYTHON", "PT_SNAP_", "PIP_"))
    }
    for name in CLEARED_ENV:
        env.pop(name, None)
    env.pop("PYTHONHOME", None)
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")
    env["XDG_CACHE_HOME"] = str(home / ".cache")
    env["PYTHONNOUSERSITE"] = "1"
    env["PIP_CONFIG_FILE"] = os.devnull
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["VIRTUAL_ENV"] = str(venv_dir)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    env["PWD"] = str(cwd)
    env["COLUMNS"] = "100"
    env["LINES"] = "50"
    return env


def _check_dataset_skill(text: str, name: str) -> None:
    """Check the installed instructions, not an authored checkout substitute."""
    for required in (
        "pt-snap-native-v2 dataset directory or `manifest.json`",
        "overview.dataset.status",
        "manifest_path",
        "fingerprint",
        "dataset_support.supported",
        "scope.source_coverage.range_complete",
        "scope.range_complete",
        "has_more",
        "truncated",
        "pt-snap capabilities --json",
    ):
        _require(required in text, f"Installed {name} omits dataset guidance: {required}")


def _dataset_overview(
    overview: dict[str, Any], target: Path, dataset: Path, expected_format: str
) -> dict[str, Any]:
    _require(
        _path_value(overview, "db_path", "dataset overview") == target, "Wrong overview target"
    )
    _require(
        overview.get("focus_source") == "explicit", "Dataset discovery did not use explicit target"
    )
    metadata = overview.get("import_metadata", {})
    _require(metadata.get("status") == "available", "Dataset import provenance is not available")
    details = overview.get("dataset", {})
    _require(details.get("status") == "complete", "Dataset is not complete")
    _require(details.get("format") == expected_format, "Wrong dataset format")
    _require(
        _path_value(details, "manifest_path", "dataset overview") == dataset / "manifest.json",
        "Wrong dataset manifest",
    )
    fingerprint = details.get("fingerprint")
    _require(isinstance(fingerprint, str) and bool(fingerprint), "Dataset has no fingerprint")
    _require(details.get("cross_slice_queries") is True, "Cross-slice queries are unavailable")
    return details


def _dataset_query(
    query: dict[str, Any], target: Path, dataset: Path, fingerprint: str, device: int
) -> dict[str, Any]:
    _require(_path_value(query, "db_path", "dataset query") == target, "Wrong query target")
    _require(query.get("focus_source") == "explicit", "Dataset query did not use explicit target")
    _require(query.get("device_id") == device, "Dataset query changed device")
    rows = query.get("rows")
    _require(isinstance(rows, list) and query.get("returned") == len(rows), "Invalid query rows")
    _require(
        query.get("has_more") is False and query.get("truncated") is False, "Incomplete query rows"
    )
    scope = query.get("scope", {})
    _require(_path_value(scope, "dataset_path", "query scope") == dataset, "Wrong query dataset")
    _require(scope.get("fingerprint") == fingerprint, "Query changed dataset generation")
    _require(scope.get("range_complete") is True, "Incomplete query source range")
    _require(scope.get("boundary_events_included") is False, "Query included synthetic boundaries")
    return scope


EVENT_FIELDS = (
    "id",
    "action",
    "address",
    "size",
    "stream",
    "allocated",
    "active",
    "reserved",
    "callstack",
)
EVENT_SOURCE_FIELDS = (
    "source_stack_id",
    "stack_id",
    "stack_kind",
    "text_kind",
    "stack_event_id",
    "frames",
    "frames_status",
)
FRAME_FIELDS = ("filename", "line", "name")


def _standalone_rows(
    query: dict[str, Any], standalone: Path, device: int, template: str
) -> list[dict[str, Any]]:
    label = f"Standalone {template} reference"
    _require(_path_value(query, "db_path", label) == standalone, f"{label} changed target")
    _require(query.get("focus_source") == "explicit", f"{label} did not use explicit target")
    _require(
        type(query.get("device_id")) is int and query["device_id"] == device,
        f"{label} changed device",
    )
    _require(query.get("template") == template, f"{label} changed template")
    rows = query.get("rows")
    _require(
        isinstance(rows, list) and all(isinstance(row, dict) for row in rows),
        f"{label} has invalid rows",
    )
    _require(
        type(query.get("returned")) is int
        and query["returned"] == len(rows)
        and type(query.get("total")) is int
        and query["total"] == len(rows)
        and query.get("total_is_exact") is True
        and query.get("has_more") is False
        and query.get("truncated") is False,
        f"{label} is incomplete",
    )
    return rows


def _event_parity(
    crossing: dict[str, Any],
    reference: dict[str, Any],
    frame_references: dict[int, dict[str, Any]],
    *,
    standalone: Path,
    fingerprint: str,
    device: int,
    event_ids: list[int],
) -> int:
    """Check base events and ordered public frame fields, not local stack IDs.

    Standalone event_frames exposes filename/line/name, not arbitrary raw extras.
    The full raw-array digest below attests internal identity consistency only;
    independent extra-field preservation remains covered by the core tests.
    """
    expected = _standalone_rows(reference, standalone, device, "event")
    rows = crossing.get("rows")
    _require(
        crossing.get("template") == "event"
        and isinstance(rows, list)
        and len(rows) == len(expected) == len(event_ids)
        and set(frame_references) == set(event_ids),
        "Cross-shard event/reference counts or template differ",
    )
    _require(
        type(crossing.get("returned")) is int
        and crossing["returned"] == len(rows)
        and type(crossing.get("total")) is int
        and crossing["total"] == len(rows)
        and crossing.get("total_is_exact") is True
        and crossing.get("has_more") is False
        and crossing.get("truncated") is False,
        "Cross-shard event rows are incomplete",
    )
    coverage = crossing.get("scope", {}).get("source_coverage", {})
    _require(isinstance(coverage, dict), "Cross-shard source coverage is invalid")
    for field, value in {
        "range_complete": True,
        "event_position": "after",
        "coverage_scope": "returned_events",
        "events_resolved": len(event_ids),
        "ordered_frame_events": len(event_ids),
    }.items():
        _require(
            type(coverage.get(field)) is type(value) and coverage[field] == value,
            f"Cross-shard source coverage differs: {field}",
        )
    _require(
        type(coverage.get("source_queries")) is int and coverage["source_queries"] > 0,
        "Cross-shard source coverage differs: source_queries",
    )
    frame_count = 0
    for row, original, event_id in zip(rows, expected, event_ids, strict=True):
        label = f"Event {event_id}"
        _require(set(original) == set(EVENT_FIELDS), f"{label} standalone base fields differ")
        _require(
            isinstance(row, dict) and set(row) == set(EVENT_FIELDS + EVENT_SOURCE_FIELDS),
            f"{label} dataset event fields differ",
        )
        _require(
            type(original["id"]) is int and original["id"] == event_id,
            f"{label} standalone event order differs",
        )
        for field in EVENT_FIELDS:
            _require(
                type(row[field]) is type(original[field]) and row[field] == original[field],
                f"{label} base field differs: {field}",
            )
        frames = row["frames"]
        _require(
            isinstance(frames, list)
            and all(isinstance(frame, dict) for frame in frames)
            and row["frames_status"] == "ordered"
            and row["stack_kind"] == "captured",
            f"{label} lost ordered frame evidence",
        )
        _require(
            row["text_kind"] == ("captured" if original["callstack"] else "missing")
            and type(row["stack_event_id"]) is int
            and row["stack_event_id"] == event_id,
            f"{label} source attribution differs",
        )
        try:
            canonical = json.dumps(
                frames, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False
            )
        except (TypeError, ValueError, RecursionError, OverflowError) as exc:
            raise AcceptanceError(f"{label} has invalid raw frame JSON") from exc
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        identity = f"dataset:{fingerprint}:device:{device}:frames:sha256:{digest}"
        _require(
            row["source_stack_id"] == row["stack_id"] == identity,
            f"{label} ordered frame identity/namespace differs",
        )
        frame_rows = _standalone_rows(
            frame_references[event_id], standalone, device, "event_frames"
        )
        _require(len(frames) == len(frame_rows), f"{label} ordered frame count differs")
        local_stack_id = None
        for position, (frame, original_frame) in enumerate(zip(frames, frame_rows, strict=True)):
            _require(
                set(original_frame)
                == set(FRAME_FIELDS + ("event_id", "stack_id", "position", "frame_id")),
                f"{label} standalone frame fields differ",
            )
            _require(
                type(original_frame["event_id"]) is int
                and original_frame["event_id"] == event_id
                and type(original_frame["position"]) is int
                and original_frame["position"] == position,
                f"{label} standalone frame event/order differs at position {position}",
            )
            _require(
                all(
                    type(original_frame[key]) is int and original_frame[key] >= 0
                    for key in ("stack_id", "frame_id")
                )
                and local_stack_id in (None, original_frame["stack_id"]),
                f"{label} standalone frame local identity differs at position {position}",
            )
            local_stack_id = original_frame["stack_id"]
            for field, field_type in (("filename", str), ("line", int), ("name", str)):
                _require(
                    type(frame.get(field)) is type(original_frame[field]) is field_type
                    and frame[field] == original_frame[field],
                    f"{label} ordered frame field differs at position {position}: {field}",
                )
        frame_count += len(frames)
    return frame_count


def _sharded_acceptance(
    pt_snap: Path,
    fixture: Path,
    output_dir: Path,
    events_per_slice: int,
    standalone: Path,
    standalone_overview: dict[str, Any],
    standalone_peak: dict[str, Any],
    focus_file: Path,
    *,
    cwd: Path,
    env: dict[str, str],
) -> list[dict[str, Any]]:
    """Execute both complete-dataset forms through the installed public CLI."""

    def cli(label: str, *args: object) -> dict[str, Any]:
        return _run_json([str(pt_snap), *map(str, args), "--json"], cwd=cwd, env=env, label=label)

    device = standalone_peak["device_id"]
    focus_before = focus_file.read_bytes()
    evidence = []
    for format_name in ("pt-snap-native-v2", "compatibility-v1"):
        import_args = (
            "import",
            fixture,
            "--output-dir",
            output_dir / format_name,
            "--events-per-slice",
            events_per_slice,
            "--format",
            format_name,
            "--no-focus",
        )
        imported = cli(f"{format_name} import", *import_args)
        dataset = _path_value(imported, "dataset_path", "sharded import")
        _require(
            dataset.is_dir() and dataset.is_relative_to(output_dir),
            "Dataset was not published inside the isolated output",
        )
        _require(
            _path_value(imported, "db_path", "sharded import") == dataset,
            "Import target is not the dataset",
        )
        _require(imported.get("format") == format_name, "Import returned the wrong format")
        _require(
            imported.get("rebuilt") is True and imported.get("reused") is False,
            "Initial dataset import was not built",
        )
        _require(imported.get("focus_state") is None, "No-focus import returned persisted focus")
        reused = cli(f"{format_name} reuse", *import_args)
        _require(reused.get("reused") is True, "Dataset import did not reuse its cache")
        _require(
            _path_value(reused, "dataset_path", "sharded reuse") == dataset,
            "Reused dataset changed target",
        )
        _require(reused.get("focus_state") is None, "No-focus reuse returned persisted focus")

        fingerprint = None
        selected = None
        for target in (dataset, dataset / "manifest.json"):
            overview = cli(f"{format_name} overview {target.name}", "overview", target)
            details = _dataset_overview(overview, target, dataset, format_name)
            _require(
                overview["devices"] == standalone_overview["devices"],
                "Dataset discovery changed real device bounds",
            )
            selected = next(
                (d for d in details.get("devices", []) if d.get("device_id") == device), None
            )
            _require(selected is not None, "Dataset discovery lost the selected device")
            slices = selected.get("slices", [])
            _require(
                len(slices) >= 2,
                "Sharded acceptance needs at least two slices on the selected device; lower --events-per-slice",
            )
            _require(
                all(Path(s["db_path"]).is_file() for s in slices), "Discovered shard is absent"
            )
            _require(
                imported.get("slice_count") == sum(len(d["slices"]) for d in details["devices"]),
                "Import/discovery slice counts disagree",
            )
            _require(
                fingerprint in (None, details["fingerprint"]),
                "Directory and manifest identify different generations",
            )
            fingerprint = details["fingerprint"]
            peak = cli(
                f"{format_name} peak {target.name}",
                "query",
                target,
                "--device",
                device,
                "--template-use",
                "memory_peak",
            )
            scope = _dataset_query(peak, target, dataset, fingerprint, device)
            _require(peak.get("template") == "memory_peak", "Wrong peak template")
            _require(
                peak["rows"] == standalone_peak["rows"],
                "Dataset peaks differ from standalone CLI results",
            )
            _require(
                scope.get("slice_indices") == [s["index"] for s in slices],
                "Peak query did not span every shard",
            )
            _require(
                scope.get("actual_range", {}).get("real_event_count") == selected["event_count"],
                "Peak query omitted real events",
            )

        # Inspect actual events at opposite ends, then a range crossing a shard
        # boundary. Never count synthetic boundary rows as real capture events.
        assert selected is not None and fingerprint is not None
        slices = selected["slices"]
        for owner in (slices[0], slices[-1]):
            event_id = owner["first_event_id"]
            point = cli(
                f"{format_name} point {owner['index']}",
                "query",
                dataset,
                "--device",
                device,
                "--template-use",
                "event",
                "--params",
                json.dumps({"id": event_id}),
            )
            scope = _dataset_query(point, dataset, dataset, fingerprint, device)
            _require(
                scope.get("slice_indices") == [owner["index"]],
                "Point query used the wrong owning shard",
            )
            _require(
                scope.get("source_coverage", {}).get("range_complete") is True,
                "Point query source coverage is incomplete",
            )
            _require(
                [row.get("id") for row in point["rows"]] == [event_id],
                "Point query returned the wrong real event",
            )

        params = json.dumps(
            {"min_id": slices[0]["last_event_id"], "max_id": slices[1]["first_event_id"]}
        )
        arguments = (
            "--device",
            device,
            "--template-use",
            "event",
            "--params",
            params,
            "--exact-total",
        )
        crossing = cli(f"{format_name} cross-shard events", "query", dataset, *arguments)
        reference = cli(f"{format_name} standalone events", "query", standalone, *arguments)
        scope = _dataset_query(crossing, dataset, dataset, fingerprint, device)
        _require(
            scope.get("slice_indices") == [slices[0]["index"], slices[1]["index"]],
            "Event range did not cross shards",
        )

        def check_events(actual, original, event_ids, *, name=format_name, generation=fingerprint):
            frame_references = {
                event_id: cli(
                    f"{name} standalone frames {event_id}",
                    "query",
                    standalone,
                    "--device",
                    device,
                    "--template-use",
                    "event_frames",
                    "--params",
                    json.dumps({"event_id": event_id, "frame_order": "original"}),
                    "--exact-total",
                )
                for event_id in event_ids
            }
            return _event_parity(
                actual,
                original,
                frame_references,
                standalone=standalone,
                fingerprint=generation,
                device=device,
                event_ids=event_ids,
            )

        frame_count = check_events(
            crossing, reference, [slices[0]["last_event_id"], slices[1]["first_event_id"]]
        )
        if frame_count == 0:
            # A shard boundary can legitimately fall between two empty stacks.
            # Select one real captured event, then prove its frames independently;
            # formatted text is only a locator, never reconstructed frame evidence.
            candidate = cli(
                f"{format_name} captured event locator",
                "query",
                standalone,
                "--device",
                device,
                "--template-use",
                "event",
                "--params",
                json.dumps({"min_id": 0, "order_by": "callstack", "order_dir": "DESC", "limit": 1}),
            )
            candidates = candidate.get("rows")
            _require(
                _path_value(candidate, "db_path", "captured event locator") == standalone
                and candidate.get("focus_source") == "explicit"
                and type(candidate.get("device_id")) is int
                and candidate["device_id"] == device
                and candidate.get("template") == "event"
                and type(candidate.get("returned")) is int
                and candidate["returned"] == 1
                and isinstance(candidates, list)
                and len(candidates) == 1
                and isinstance(candidates[0], dict),
                "Invalid captured event locator",
            )
            event_id = candidates[0].get("id")
            _require(
                type(event_id) is int
                and slices[0]["first_event_id"] <= event_id <= slices[-1]["last_event_id"]
                and isinstance(candidates[0].get("callstack"), str)
                and bool(candidates[0]["callstack"]),
                "Fixture has no real captured event for nonempty frame acceptance",
            )
            point_args = (
                "--device",
                device,
                "--template-use",
                "event",
                "--params",
                json.dumps({"id": event_id}),
                "--exact-total",
            )
            captured = cli(f"{format_name} captured event", "query", dataset, *point_args)
            original = cli(
                f"{format_name} standalone captured event", "query", standalone, *point_args
            )
            _dataset_query(captured, dataset, dataset, fingerprint, device)
            frame_count = check_events(captured, original, [event_id])
        _require(frame_count > 0, "Ordered frame acceptance has no nonempty frame evidence")
        _require(
            crossing.get("total_is_exact") is True and crossing.get("total") == 2,
            "Cross-shard exact total is invalid",
        )
        _require(
            focus_file.read_bytes() == focus_before,
            "Dataset discovery/query/import changed project focus",
        )
        evidence.append(
            {
                "format": format_name,
                "slice_count": imported["slice_count"],
                "real_event_count": selected["event_count"],
                "device_id": device,
                "addressing": ["directory", "manifest.json"],
                "reused": True,
                "standalone_peak_parity": True,
                "cross_shard_event_parity": True,
                "ordered_frame_field_parity": True,
                "ordered_frame_identity_checked": True,
                "nonempty_ordered_frames_checked": True,
                "focus_unchanged": True,
            }
        )
    return evidence


def _run_acceptance(
    wheel: Path, fixture: Path, events_per_slice: int | None = None, wheelhouse: Path | None = None
) -> dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[2]
    expected_fixture = repo_root / "tests/fixtures/snapshots/snapshot_with_empty_cache.pkl"
    wheel = wheel.resolve()
    fixture = fixture.resolve()
    expected_fixture = expected_fixture.resolve()
    _require(wheel.is_file(), f"Wheel does not exist: {wheel}")
    _require(wheel.suffix == ".whl", f"Expected a wheel path: {wheel}")
    _require(fixture == expected_fixture, f"Unexpected snapshot fixture: {fixture}")
    _require(fixture.is_file(), f"Snapshot fixture does not exist: {fixture}")
    _require(
        events_per_slice is None or type(events_per_slice) is int and events_per_slice > 0,
        "--events-per-slice must be positive",
    )
    if wheelhouse is not None:
        wheelhouse = wheelhouse.resolve()
        _require(wheelhouse.is_dir(), f"Wheelhouse does not exist: {wheelhouse}")

    with tempfile.TemporaryDirectory(prefix="pt-snap-agent-wheel-") as temporary:
        root = Path(temporary).resolve()
        home = root / "home"
        cwd = root / "project"
        venv_dir = root / "venv"
        output_dir = root / "database"
        home.mkdir()
        cwd.mkdir()
        output_dir.mkdir()
        venv_python, pt_snap = _venv_paths(venv_dir)
        env = _isolated_environment(home, cwd, venv_dir, pt_snap.parent)
        _run(
            [
                sys.executable,
                str(repo_root / ".github/scripts/audit_wheel.py"),
                "--wheel",
                str(wheel),
            ],
            cwd=cwd,
            env=env,
            label="wheel/source audit",
        )
        _run(
            [
                sys.executable,
                "-c",
                "import runpy, sys; from pathlib import Path; "
                "root = Path(sys.argv[1]).parent / 'fixtures/snapshots'; "
                "runpy.run_path(sys.argv[1])['verify_snapshot_fixtures'](root, root / 'SHA256SUMS')",
                str(repo_root / "tests/_fixture_provenance.py"),
            ],
            cwd=cwd,
            env=env,
            label="fixture provenance gate",
        )
        with fixture.open("rb") as stream:
            _require(
                not stream.read(128).startswith(b"version https://git-lfs.github.com/spec/"),
                "Snapshot fixture is an unhydrated LFS pointer",
            )
        venv.EnvBuilder(with_pip=True, system_site_packages=wheelhouse is None, clear=True).create(
            venv_dir
        )
        _require(venv_python.is_file(), f"Venv Python was not created: {venv_python}")

        _run(
            [
                str(venv_python),
                "-m",
                "pip",
                "install",
                *(["--no-deps"] if wheelhouse is None else ["--find-links", str(wheelhouse)]),
                "--no-index",
                "--force-reinstall",
                str(wheel),
            ],
            cwd=cwd,
            env=env,
            label="wheel installation",
        )
        _require(pt_snap.is_file(), f"Venv pt-snap was not created: {pt_snap}")

        module_result = _run(
            [
                str(venv_python),
                "-c",
                "import pt_snap_cli; print(pt_snap_cli.__file__)",
            ],
            cwd=cwd,
            env=env,
            label="installed package probe",
            clean_stderr=True,
        )
        module_path = Path(module_result.stdout.strip()).resolve()
        _require(
            _is_inside(module_path, venv_dir),
            f"pt_snap_cli resolved outside the venv: {module_path}",
        )
        if wheelhouse is not None:
            identity = _run_json(
                [
                    str(venv_python),
                    "-I",
                    "-c",
                    "import json, site, sys, typer, yaml, jinja2; "
                    "print(json.dumps({'prefix': sys.prefix, 'user_site': site.ENABLE_USER_SITE, "
                    "'modules': {m.__name__: m.__file__ for m in (typer, yaml, jinja2)}}))",
                ],
                cwd=cwd,
                env=env,
                label="offline dependency identity",
            )
            _require(
                Path(identity["prefix"]).resolve() == venv_dir, "Wrong installed runtime prefix"
            )
            _require(identity["user_site"] is False, "User site packages were enabled")
            _require(
                all(
                    _is_inside(Path(path).resolve(), venv_dir)
                    for path in identity["modules"].values()
                ),
                "Offline dependencies resolved outside the venv",
            )
        bundled_root = module_path.parent / "bundled_skills"
        bundled_helper = bundled_root / "pt-snap-helper" / "SKILL.md"
        _require(bundled_helper.is_file(), f"Bundled helper is missing: {bundled_helper}")
        _require(
            _is_inside(bundled_helper, venv_dir),
            f"Bundled helper is outside the venv: {bundled_helper}",
        )
        help_contract_result = _run(
            [
                str(venv_python),
                "-c",
                "from pt_snap_cli.cli import AGENT_HELP_EPILOG; print(AGENT_HELP_EPILOG)",
            ],
            cwd=cwd,
            env=env,
            label="packaged help contract",
            clean_stderr=True,
        )
        help_contract = " ".join(help_contract_result.stdout.split())
        _require(
            "pt-snap skill install pt-snap-helper --json" in help_contract,
            f"Packaged help contract omits the helper install command: {help_contract!r}",
        )

        help_result = _run(
            [str(pt_snap), "--help"],
            cwd=cwd,
            env=env,
            label="root help",
            clean_stderr=True,
        )
        normalized_help = " ".join(unstyle(help_result.stdout).split())
        _require(
            "pt-snap-helper" in normalized_help and "restart the agent" in normalized_help.lower(),
            f"Root help lost helper onboarding: {normalized_help[-1000:]!r}",
        )
        _require(
            "pt-snap capabilities --json" in normalized_help
            and "pt-snap overview --json" in normalized_help
            and "prefer --json" in normalized_help,
            f"Root help lost its JSON capability guidance: {normalized_help[-1000:]!r}",
        )

        listed = _run_json(
            [str(pt_snap), "skill", "list", "--user", "--target", "agents", "--json"],
            cwd=cwd,
            env=env,
            label="initial skill list",
        )
        helper = _skill_entry(listed, "pt-snap-helper", "initial skill list")
        _require(helper.get("status") == "missing", "Bundled helper was not initially missing")
        source_dir = _path_value(helper, "source_dir", "initial skill list")
        _require(
            _is_inside(source_dir, venv_dir), f"Skill source is outside the venv: {source_dir}"
        )
        _require(
            source_dir == bundled_root / "pt-snap-helper",
            f"Skill source is not the wheel's bundled helper: {source_dir}",
        )
        _require((source_dir / "SKILL.md").is_file(), "Bundled helper source has no SKILL.md")

        installed = _run_json(
            [
                str(pt_snap),
                "skill",
                "install",
                "pt-snap-helper",
                "--target",
                "agents",
                "--json",
            ],
            cwd=cwd,
            env=env,
            label="helper install",
        )
        results = installed.get("results")
        _require(
            isinstance(results, list) and len(results) == 1, "Helper install report is invalid"
        )
        install_result = results[0]
        _require(isinstance(install_result, dict), "Helper install result is invalid")
        _require(install_result.get("action") == "installed", "Helper was not newly installed")
        _require(install_result.get("host") == "agents", "Helper was not installed for agents")
        _require(install_result.get("scope") == "user", "Helper was not installed at user scope")
        installed_path = _path_value(install_result, "path", "helper install")
        expected_installed = home / ".agents" / "skills" / "pt-snap-helper"
        _require(
            installed_path == expected_installed.resolve(),
            f"Unexpected helper destination: {installed_path}",
        )
        _require((installed_path / "SKILL.md").is_file(), "Installed helper has no SKILL.md")
        _require(
            installed.get("restart_required") is True, "Helper install did not require a restart"
        )
        _require(
            "restart" in str(installed.get("restart_hint")).lower(),
            "Helper install has no restart hint",
        )

        installed_listing = _run_json(
            [str(pt_snap), "skill", "list", "--user", "--target", "agents", "--json"],
            cwd=cwd,
            env=env,
            label="installed skill list",
        )
        installed_helper = _skill_entry(installed_listing, "pt-snap-helper", "installed skill list")
        _require(
            installed_helper.get("status") == "installed",
            "Installed helper was not reported installed",
        )
        installed_source = _path_value(installed_helper, "source_dir", "installed skill list")
        _require(
            installed_source == source_dir, "Installed helper source changed after installation"
        )
        installed_text = (installed_path / "SKILL.md").read_text(encoding="utf-8")
        _require(
            installed_text == bundled_helper.read_text(encoding="utf-8"),
            "Installed helper differs from wheel source",
        )
        _require(
            "name: pt-snap-helper" in installed_text, "Installed helper content is not readable"
        )
        for command in (
            "pt-snap capabilities --json",
            "pt-snap overview '<db_path>' --json",
            "pt-snap query --template-use <name> --json",
        ):
            _require(command in installed_text, f"Installed helper omits {command}")

        if events_per_slice is not None:
            _check_dataset_skill(installed_text, "pt-snap-helper")
            diagnostic = "pt-snap-memory-peak-breakdown"
            installed_diagnostic = _run_json(
                [str(pt_snap), "skill", "install", diagnostic, "--target", "agents", "--json"],
                cwd=cwd,
                env=env,
                label="diagnostic skill install",
            )
            diagnostic_result = installed_diagnostic.get("results", [])
            _require(len(diagnostic_result) == 1, "Invalid diagnostic skill installation")
            diagnostic_path = _path_value(diagnostic_result[0], "path", "diagnostic skill install")
            _require(
                diagnostic_result[0].get("action") == "installed",
                "Diagnostic skill was not installed",
            )
            _require(
                diagnostic_path == home / ".agents/skills" / diagnostic,
                "Diagnostic skill escaped isolated HOME",
            )
            diagnostic_text = (diagnostic_path / "SKILL.md").read_text(encoding="utf-8")
            _require(
                diagnostic_text
                == (bundled_root / diagnostic / "SKILL.md").read_text(encoding="utf-8"),
                "Installed diagnostic differs from wheel source",
            )
            _check_dataset_skill(diagnostic_text, diagnostic)
            for command in (
                'pt-snap overview "<DB>" --json',
                "--template-use memory_peak",
                "pt-snap report peak-memory --help",
            ):
                _require(command in diagnostic_text, f"Installed diagnostic omits {command}")
            _run(
                [str(pt_snap), "report", "peak-memory", "--help"],
                cwd=cwd,
                env=env,
                label="diagnostic report help",
                clean_stderr=True,
            )

        capabilities = _run_json(
            [str(pt_snap), "capabilities", "--json"],
            cwd=cwd,
            env=env,
            label="capabilities",
        )
        template_names = {
            item.get("name") for item in capabilities.get("templates", []) if isinstance(item, dict)
        }
        _require("memory_peak" in template_names, "Capabilities did not include memory_peak")
        if events_per_slice is not None:
            for name in ("event", "memory_peak"):
                template = next((t for t in capabilities["templates"] if t.get("name") == name), {})
                _require(
                    template.get("dataset_support", {}).get("supported") is True,
                    f"Catalog does not support dataset {name}",
                )
            diagnostic_entry = _skill_entry(capabilities, diagnostic, "capabilities")
            _require(
                diagnostic_entry.get("status") == "installed",
                "Capabilities did not see the installed diagnostic",
            )
            _require(
                _path_value(diagnostic_entry, "source_dir", "capabilities")
                == bundled_root / diagnostic,
                "Diagnostic catalog source escaped wheel",
            )
        capability_helper = _skill_entry(capabilities, "pt-snap-helper", "capabilities")
        _require(
            capability_helper.get("status") == "installed",
            "Capabilities did not see installed helper",
        )
        capability_source = _path_value(capability_helper, "source_dir", "capabilities")
        _require(
            _is_inside(capability_source, venv_dir),
            f"Capability source is outside the venv: {capability_source}",
        )

        import_command = [
            str(pt_snap),
            "import",
            str(fixture),
            "--output-dir",
            str(output_dir),
            "--json",
        ]
        imported = _run_json(import_command, cwd=cwd, env=env, label="snapshot import")
        database = _path_value(imported, "db_path", "snapshot import")
        _require(database.is_file(), f"Imported database was not published: {database}")
        _require(
            imported.get("focus_state") is not None, "Snapshot import did not return focus_state"
        )
        _require(
            imported.get("focus_source") == "project",
            "Snapshot import did not report project focus",
        )
        focus_state = imported.get("focus_state")
        _require(isinstance(focus_state, dict), "Snapshot import focus_state is invalid")
        _require(
            _path_value(focus_state, "db_path", "snapshot import focus_state") == database,
            "Snapshot import focus database does not match the published database",
        )
        _require(
            focus_state.get("focus_source") == "project",
            "Snapshot import focus_state source is invalid",
        )
        focus_file = _path_value(focus_state, "focus_file", "snapshot import focus_state")
        _require(focus_file.is_file(), f"Project focus file was not written: {focus_file}")
        _require(
            focus_file.is_relative_to(cwd), f"Project focus escaped isolated CWD: {focus_file}"
        )

        reused = _run_json(import_command, cwd=cwd, env=env, label="snapshot import reuse")
        _require(reused.get("reused") is True, "Repeated snapshot import was not reused")
        _require(
            _path_value(reused, "db_path", "snapshot import reuse") == database,
            "Reused import changed database path",
        )
        _require(reused.get("focus_state") is not None, "Reused import did not return focus_state")
        _require(
            reused.get("focus_source") == "project", "Reused import did not retain project focus"
        )

        overview = _run_json(
            [str(pt_snap), "overview", "--json"],
            cwd=cwd,
            env=env,
            label="overview",
        )
        _require(
            _path_value(overview, "db_path", "overview") == database,
            "Overview used a different database",
        )
        _require(overview.get("focus_source") == "project", "Overview did not use project focus")
        devices = overview.get("devices")
        _require(isinstance(devices, list) and devices, "Overview returned no devices")
        device_ids: set[int] = set()
        for device in devices:
            _require(isinstance(device, dict), "Overview returned an invalid device")
            device_id = device.get("device_id")
            _require(
                isinstance(device_id, int) and not isinstance(device_id, bool),
                "Overview device has no id",
            )
            device_ids.add(device_id)

        query = _run_json(
            [str(pt_snap), "query", "--template-use", "memory_peak", "--json"],
            cwd=cwd,
            env=env,
            label="memory peak query",
        )
        _require(
            _path_value(query, "db_path", "memory peak query") == database,
            "Query used a different database",
        )
        _require(query.get("focus_source") == "project", "Query did not report project focus")
        selected_device = query.get("device_id")
        _require(
            isinstance(selected_device, int) and not isinstance(selected_device, bool),
            "Query did not select a device",
        )
        _require(selected_device in device_ids, "Query selected a device absent from overview")
        _require(query.get("template") == "memory_peak", "Query used the wrong template")
        rows = query.get("rows")
        _require(isinstance(rows, list) and rows, "Memory peak query returned no rows")
        _require(
            query.get("returned") == len(rows), "Memory peak query returned count is inconsistent"
        )
        _require(
            any(
                isinstance(row, dict)
                and any(
                    row.get(field) is not None
                    for field in (
                        "peak_allocated",
                        "peak_active",
                        "peak_reserved",
                    )
                )
                for row in rows
            ),
            "Memory peak query returned rows without peak values",
        )

        sharded = []
        if events_per_slice is not None:
            sharded = _sharded_acceptance(
                pt_snap,
                fixture,
                output_dir,
                events_per_slice,
                database,
                overview,
                query,
                focus_file,
                cwd=cwd,
                env=env,
            )
        return {
            "acceptance_kind": "offline-installed-cli-and-skills",
            "live_agent_execution": "not-run; requires separate approval",
            "stored_baseline_scoring": "not-run; separate recorded-run grading only",
            "wheel_source_audit": "passed",
            "fixture_provenance": "passed",
            "dependency_mode": (
                "isolated-offline-wheelhouse" if wheelhouse else "system-site-packages"
            ),
            "installed_package_in_venv": True,
            "standalone_import_reuse_discovery_query": "passed",
            "events_per_slice": events_per_slice,
            "datasets": sharded,
        }


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a positive integer") from exc
    if number <= 0:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def _parse_args(arguments: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--fixture", required=True, type=Path)
    parser.add_argument(
        "--events-per-slice",
        type=_positive_int,
        help="Also test both sharded formats; use a capacity producing at least two slices (reviewed fixture: 4096)",
    )
    parser.add_argument(
        "--wheelhouse",
        type=Path,
        help="Install dependencies offline from this directory in a venv without system packages; default reuses system dependencies",
    )
    return parser.parse_args(arguments)


def main() -> int:
    args = _parse_args()
    try:
        evidence = _run_acceptance(args.wheel, args.fixture, args.events_per_slice, args.wheelhouse)
    except AcceptanceError as exc:
        print(f"clean-wheel Agent acceptance failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(evidence, indent=2))
    print("clean-wheel offline CLI/skills acceptance passed (live agent not run)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
