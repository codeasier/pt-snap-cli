from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import venv
from pathlib import Path
from typing import Any


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
    env = os.environ.copy()
    for name in CLEARED_ENV:
        env.pop(name, None)
    env.pop("PYTHONHOME", None)
    env["HOME"] = str(home)
    env["USERPROFILE"] = str(home)
    env["XDG_CONFIG_HOME"] = str(home / ".config")
    env["VIRTUAL_ENV"] = str(venv_dir)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"
    env["PWD"] = str(cwd)
    return env


def _run_acceptance(wheel: Path, fixture: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    expected_fixture = repo_root / "tests/fixtures/snapshots/snapshot_with_empty_cache.pkl"
    wheel = wheel.resolve()
    fixture = fixture.resolve()
    expected_fixture = expected_fixture.resolve()
    _require(wheel.is_file(), f"Wheel does not exist: {wheel}")
    _require(wheel.suffix == ".whl", f"Expected a wheel path: {wheel}")
    _require(fixture == expected_fixture, f"Unexpected snapshot fixture: {fixture}")
    _require(fixture.is_file(), f"Snapshot fixture does not exist: {fixture}")

    with tempfile.TemporaryDirectory(prefix="pt-snap-agent-wheel-") as temporary:
        root = Path(temporary).resolve()
        home = root / "home"
        cwd = root / "project"
        venv_dir = root / "venv"
        output_dir = root / "database"
        home.mkdir()
        cwd.mkdir()
        output_dir.mkdir()
        venv.EnvBuilder(with_pip=True, system_site_packages=True, clear=True).create(venv_dir)
        venv_python, pt_snap = _venv_paths(venv_dir)
        _require(venv_python.is_file(), f"Venv Python was not created: {venv_python}")
        env = _isolated_environment(home, cwd, venv_dir, pt_snap.parent)

        _run(
            [
                str(venv_python),
                "-m",
                "pip",
                "install",
                "--no-deps",
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
        bundled_root = module_path.parent / "bundled_skills"
        bundled_helper = bundled_root / "pt-snap-helper" / "SKILL.md"
        _require(bundled_helper.is_file(), f"Bundled helper is missing: {bundled_helper}")
        _require(
            _is_inside(bundled_helper, venv_dir),
            f"Bundled helper is outside the venv: {bundled_helper}",
        )

        help_result = _run(
            [str(pt_snap), "--help"],
            cwd=cwd,
            env=env,
            label="root help",
            clean_stderr=True,
        )
        normalized_help = " ".join(help_result.stdout.split())
        _require(
            "pt-snap skill install pt-snap-helper --json" in normalized_help,
            "Root help does not show the supported helper install command",
        )
        _require(
            "restart the agent" in normalized_help.lower(),
            "Root help does not tell the agent to restart after installing the helper",
        )
        _require(
            "pt-snap capabilities --json" in normalized_help
            and "pt-snap overview --json" in normalized_help
            and "prefer --json" in normalized_help,
            "Root help lost its JSON capability guidance",
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
            "name: pt-snap-helper" in installed_text, "Installed helper content is not readable"
        )
        for command in (
            "pt-snap capabilities --json",
            "pt-snap overview '<db_path>' --json",
            "pt-snap query --template-use <name> --json",
        ):
            _require(command in installed_text, f"Installed helper omits {command}")

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


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", required=True, type=Path)
    parser.add_argument("--fixture", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        _run_acceptance(args.wheel, args.fixture)
    except AcceptanceError as exc:
        print(f"clean-wheel Agent acceptance failed: {exc}", file=sys.stderr)
        return 1
    print("clean-wheel Agent acceptance passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
