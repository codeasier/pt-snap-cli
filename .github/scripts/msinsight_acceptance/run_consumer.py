"""Optional actual GUI consumer runner. Draft: requires hosted execution before any PASS claim.
Raw evidence stays inside --output/private. Publish only summary.json after review.
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import traceback
import urllib.request
from pathlib import Path

REV = "101f65b877a267ffd5f66ea3834706057ba243e5"
FIXTURE_SHA = "3afc9d1c5ef4ca4b417e58c0830e9eb8a913eb9459f4088b8c66c22325c68c40"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_env(home):
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("PT_SNAP_", "PYTHON", "SETUPTOOLS_SCM"))
    }
    env.update(
        HOME=str(home),
        XDG_CONFIG_HOME=str(home / ".config"),
        XDG_CACHE_HOME=str(home / ".cache"),
        PYTHONDONTWRITEBYTECODE="1",
    )
    return env


GUI_PHASES = (
    "browser_launch",
    "page_open",
    "import_open",
    "fixture_input",
    "import_search",
    "confirm_ready",
    "import_confirm",
    "overview_visible",
    "window_count",
    "window_click",
    "window_selected",
    "window_ready",
    "peak_visible",
    "peak_event",
    "browser_close",
    "page_errors",
    "complete",
)
GUI_ERRORS = ("none", "timeout", "assertion", "runtime", "other")


def read_gui_diagnostics(path):
    """Public output uses only fixed tokens and bounded numeric data, never raw input."""
    invalid = {"phase": "unavailable", "error_kind": "unavailable"}
    try:
        if path.stat().st_size > 4096:
            return invalid
        raw = json.loads(path.read_text())
        if not isinstance(raw, dict):
            return invalid
        phase, error = raw.get("phase"), raw.get("error_kind")
        transition = raw.get("transition")
        windows, count = raw.get("completed_windows"), raw.get("page_error_count")
        if phase not in GUI_PHASES or error not in GUI_ERRORS:
            return invalid
        if type(transition) is not int or not 0 <= transition <= 3:
            return invalid
        if not isinstance(windows, list) or len(windows) > 4:
            return invalid
        if any(type(value) is not int for value in windows):
            return invalid
        if windows != [1, 2, 1, 4][: len(windows)]:
            return invalid
        if type(count) is not int or not 0 <= count <= 1000000:
            return invalid
        return {
            "phase": phase,
            "error_kind": error,
            "transition": transition,
            "completed_windows": windows,
            "page_error_count": count,
        }
    except (OSError, ValueError, TypeError, RecursionError):
        return invalid


def finalize_summary(output, private, summary, process):
    try:
        if process is not None and process.poll() is None:
            (private / "stop-gui").touch(exist_ok=True)
            process.wait(timeout=30)
    except Exception as exc:
        summary["status"] = "failed"
        summary["cleanup_failure_type"] = type(exc).__name__
    finally:
        (output / "summary.json").write_text(json.dumps(summary, indent=2))


def reuse_logs_valid(logs):
    return "is up-to-date" in logs and re.search(r"parse state changed:\s*4\b", logs) is not None


def discover_snapshot_parser(source):
    """Locate the sole pinned external parser by entrypoint, without brand aliases."""
    scripts = source / "scripts"
    if not scripts.is_dir() or scripts.is_symlink():
        raise ValueError("Require a regular consumer scripts directory")
    candidates = list(scripts.glob("*/tools/dump2db.py"))
    if len(candidates) != 1:
        raise ValueError("Require exactly one snapshot parser entrypoint")
    entry = candidates[0]
    parser = entry.parent.parent
    if not entry.is_file() or parser.parent != scripts:
        raise ValueError("Invalid parser entrypoint layout")
    if any(path.is_symlink() for path in (source, scripts, parser, entry.parent, entry)):
        raise ValueError("Parser entrypoint must not traverse symlinks")
    if any(path.is_symlink() for path in parser.rglob("*")):
        raise ValueError("Parser payload must not contain symlinks")
    for name in ("base", "simulate", "tools", "util"):
        if not (parser / name).is_dir():
            raise ValueError("Incomplete snapshot parser module layout")
    if entry.resolve().parent.parent != parser.resolve():
        raise ValueError("Parser entrypoint escapes its module root")
    return parser


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", type=Path, required=True, help="Completed restore_msinsight.sh root")
    p.add_argument("--wheel", type=Path, required=True)
    p.add_argument("--wheelhouse", type=Path, required=True)
    p.add_argument("--wheel-sha256", required=True)
    p.add_argument("--fixture", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True, help="Fresh private work directory")
    a = p.parse_args()
    if a.output.exists():
        print(json.dumps({"status": "failed", "failure_type": "ExistingOutput"}))
        return 1
    a.output.mkdir()
    e = a.output / "private"
    e.mkdir()
    helpers = Path(__file__).resolve().parent
    py = a.root / "venv/bin/python"
    cli = a.root / "venv/bin/pt-snap"
    (e / "home").mkdir()
    env = clean_env(e / "home")
    calls = []

    def run(args, label):
        with (e / (label + ".stdout")).open("x") as out, (e / (label + ".stderr")).open("x") as err:
            result = subprocess.run(
                list(map(str, args)),
                cwd=e,
                env=env,
                stdout=out,
                stderr=err,
                timeout=600,
                check=False,
            )
        calls.append({"gate": label, "exit_code": result.returncode})
        if result.returncode:
            raise RuntimeError(label + " failed; private diagnostics retained")

    process = None
    summary = {
        "status": "failed",
        "consumer_revision": REV,
        "wheel_sha256": (
            a.wheel_sha256
            if len(a.wheel_sha256) == 64 and all(c in "0123456789abcdef" for c in a.wheel_sha256)
            else None
        ),
        "fixture_sha256": FIXTURE_SHA,
        "gates": calls,
        "GUI": "NOT_RUN",
    }
    try:
        assert a.root.is_absolute() and a.output.is_absolute()
        assert digest(a.wheel) == a.wheel_sha256
        assert a.fixture.stat().st_size == 581140 and digest(a.fixture) == FIXTURE_SHA
        assert (
            subprocess.check_output(
                ["git", "-C", str(a.root / "source"), "rev-parse", "HEAD"],
                text=True,
                stderr=subprocess.PIPE,
                env=env,
            ).strip()
            == REV
        )
        run(
            [
                py,
                "-m",
                "pip",
                "install",
                "--no-index",
                "--find-links",
                a.wheelhouse,
                a.wheel,
            ],
            "wheel-install",
        )
        run(
            [
                py,
                helpers / "verify_installed_wheel.py",
                "--wheel",
                a.wheel,
                "--expected-sha256",
                a.wheel_sha256,
                "--output",
                e / "installed-wheel.json",
            ],
            "installed-wheel-byte-audit",
        )
        (e / "input").mkdir()
        original = e / "input/snapshot_expandable.pkl"
        shutil.copy2(a.fixture, original)
        run(
            [
                cli,
                "import",
                original,
                "--format",
                "msinsight",
                "--events-per-slice",
                "2000",
                "--device",
                "0",
                "--no-focus",
                "--json",
            ],
            "export",
        )
        exported = json.loads((e / "export.stdout").read_text())
        assert exported["ok"] and exported["slice_count"] == 5
        shutil.copytree(e / "input", e / "runtime-input")
        runtime = e / "runtime-input/snapshot_expandable.pkl"
        artifact = original.with_name(original.name + ".msinsight")
        runtime_artifact = runtime.with_name(runtime.name + ".msinsight")
        original_hashes = {
            str(p.relative_to(artifact)): digest(p) for p in artifact.rglob("*") if p.is_file()
        }
        run(
            [
                py,
                helpers / "evidence_inventory.py",
                "--artifact",
                artifact,
                "--compare",
                runtime_artifact,
                "--mode",
                "exact",
                "--output",
                e / "pre-gui-exact.json",
            ],
            "pre-gui-exact",
        )
        stage = e / "server"
        stage.mkdir()
        binary_root = a.root / "source/server/output/linux-x86_64/bin"
        for name in ("profiler_server", "libmsinsight.so", "libsqlite.so"):
            shutil.copy2(binary_root / name, stage / name)
        shutil.copytree(
            discover_snapshot_parser(a.root / "source"),
            stage / "mem_snap_dump",
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        shutil.copytree(a.root / "source/modules/framework/build", e / "gui-root")
        shutil.copytree(a.root / "source/modules/leaks/build", e / "gui-root/plugins/Leaks")
        with (e / "supervisor.stdout").open("x") as log:
            process = subprocess.Popen(
                [str(py), str(helpers / "gui_supervisor.py"), "--evidence", str(e)],
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            deadline = time.monotonic() + 60
            while True:
                if process.poll() is not None:
                    raise RuntimeError("Loopback supervisor exited")
                try:
                    with urllib.request.urlopen("http://127.0.0.1:5174/", timeout=1) as response:
                        assert response.status == 200
                    # HTTP binds before the C++ server; a TCP-only readiness probe
                    # must succeed too, without taking the sole WebSocket session.
                    with socket.create_connection(("127.0.0.1", 9000), timeout=1):
                        pass
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise RuntimeError("Loopback readiness timeout") from None
                    time.sleep(0.25)
            summary["GUI"] = "FAILED"
            run(
                [
                    py,
                    helpers / "gui_navigation.py",
                    "--fixture",
                    runtime,
                    "--output",
                    e / "gui-summary.json",
                ],
                "GUI-navigation",
            )
            summary["GUI"] = "PASS import/windows 1-2-1-4 only"
            run(
                [
                    py,
                    helpers / "protocol_acceptance.py",
                    "--skip-import",
                    "--project",
                    runtime,
                    "--fixture",
                    runtime,
                    "--output",
                    e / "protocol",
                ],
                "protocol",
            )
            protocol_result = json.loads((e / "protocol/checks.json").read_text())
            assert protocol_result["failedChecks"] == 0 and protocol_result["passedChecks"] == 167
            summary["protocol_assertions"] = 167
            (e / "stop-gui").touch(exist_ok=False)
            process.wait(timeout=30)
        trace = (e / "server-process.trace").read_text()
        execs = [line for line in trace.splitlines() if "execve(" in line or "execveat(" in line]
        assert len(execs) == 1 and "./profiler_server" in execs[0]
        logs = "\n".join(p.read_text(errors="replace") for p in stage.glob("*.log"))
        assert reuse_logs_valid(logs)
        run(
            [
                py,
                helpers / "evidence_inventory.py",
                "--artifact",
                artifact,
                "--compare",
                runtime_artifact,
                "--mode",
                "logical",
                "--output",
                e / "post-gui-logical.json",
            ],
            "post-gui-logical",
        )
        assert digest(original) == digest(runtime) == FIXTURE_SHA
        assert original_hashes == {
            str(p.relative_to(artifact)): digest(p) for p in artifact.rglob("*") if p.is_file()
        }
        summary.update(
            status="passed",
            producer_reuse="UP_TO_DATE/state4 and one server exec",
            preserved_original=True,
            runtime_cache_mutation="allowed derived table only; runtime attestation not repaired",
        )
    except Exception as exc:
        summary["failure_type"] = type(exc).__name__
        (e / "failure.txt").write_text(traceback.format_exc())
    finally:
        if summary["GUI"] != "NOT_RUN":
            summary["gui_diagnostics"] = read_gui_diagnostics(e / "gui-summary.json")
        finalize_summary(a.output, e, summary, process)
    print(json.dumps({"status": summary["status"], "failure_type": summary.get("failure_type")}))
    return 0 if summary["status"] == "passed" else 1


if __name__ == "__main__":
    sys.exit(main())
