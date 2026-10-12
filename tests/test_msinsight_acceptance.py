"""Fail-closed contracts; these tests do not run a producer, browser or server."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

CANDIDATE = (
    Path(__file__).resolve().parents[1] / ".github/scripts/msinsight_acceptance/run_consumer.py"
)
SCRIPT = CANDIDATE if CANDIDATE.exists() else Path(__file__).with_name("run_consumer.py")
spec = importlib.util.spec_from_file_location("ms_consumer_acceptance", SCRIPT)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def arguments(tmp_path, monkeypatch):
    wheel = tmp_path / "candidate.whl"
    wheel.write_bytes(b"wheel")
    fixture = tmp_path / "fixture.pkl"
    fixture.write_bytes(b"x" * 581140)
    out = tmp_path / "evidence"
    argv = [
        "run_consumer",
        "--root",
        str(tmp_path / "restore"),
        "--wheel",
        str(wheel),
        "--wheelhouse",
        str(tmp_path / "wheelhouse"),
        "--wheel-sha256",
        "a" * 64,
        "--fixture",
        str(fixture),
        "--output",
        str(out),
    ]
    monkeypatch.setattr(sys, "argv", argv)
    return wheel, fixture, out


def test_host_environment_is_scrubbed(monkeypatch, tmp_path):
    for name in (
        "PT_SNAP_DB_PATH",
        "PT_SNAP_QUERY_TIMEOUT",
        "PYTHONPATH",
        "PYTHONOPTIMIZE",
        "SETUPTOOLS_SCM_PRETEND_VERSION",
    ):
        monkeypatch.setenv(name, "private-value")
    env = module.clean_env(tmp_path)
    assert not any(k.startswith(("PT_SNAP_", "SETUPTOOLS_SCM")) for k in env)
    assert {k for k in env if k.startswith("PYTHON")} == {"PYTHONDONTWRITEBYTECODE"}
    assert env["HOME"] == str(tmp_path)
    assert env["XDG_CONFIG_HOME"] == str(tmp_path / ".config")


def test_wrong_wheel_fails_before_subprocess_and_records_safe_summary(
    tmp_path, monkeypatch, capsys
):
    _, _, out = arguments(tmp_path, monkeypatch)
    monkeypatch.setattr(
        module.subprocess, "check_output", lambda *a, **k: pytest.fail("Must not execute git")
    )
    monkeypatch.setattr(
        module.subprocess, "run", lambda *a, **k: pytest.fail("Must not install/load")
    )
    assert module.main() == 1
    summary = json.loads((out / "summary.json").read_text())
    assert summary["status"] == "failed"
    assert summary["failure_type"] == "AssertionError"
    assert str(tmp_path) not in capsys.readouterr().out
    assert str(tmp_path) not in json.dumps(summary)


def test_wrong_fixture_fails_before_any_executable_step(tmp_path, monkeypatch):
    wheel, _, out = arguments(tmp_path, monkeypatch)
    monkeypatch.setattr(module, "digest", lambda p: "a" * 64 if p == wheel else "b" * 64)
    monkeypatch.setattr(
        module.subprocess,
        "check_output",
        lambda *a, **k: pytest.fail("No process before exact fixture verification"),
    )
    monkeypatch.setattr(module.subprocess, "run", lambda *a, **k: pytest.fail("No pickle consumer"))
    assert module.main() == 1
    assert json.loads((out / "summary.json").read_text())["failure_type"] == "AssertionError"


def test_external_runtime_error_is_private_and_fail_closed(tmp_path, monkeypatch, capsys):
    wheel, _, out = arguments(tmp_path, monkeypatch)
    monkeypatch.setattr(module, "digest", lambda p: "a" * 64 if p == wheel else module.FIXTURE_SHA)
    monkeypatch.setattr(module.subprocess, "check_output", lambda *a, **k: module.REV)

    class PlaywrightError(Exception):
        pass

    def fail(*args, **kwargs):
        raise PlaywrightError("/private/user/source.py secret-callstack")

    monkeypatch.setattr(module.subprocess, "run", fail)
    assert module.main() == 1
    summary = json.loads((out / "summary.json").read_text())
    assert summary["status"] == "failed"
    assert summary["failure_type"] == "PlaywrightError"
    assert "secret-callstack" not in json.dumps(summary)
    assert "/private/user" not in capsys.readouterr().out
    assert "secret-callstack" in (out / "private/failure.txt").read_text()


def test_cleanup_timeout_cannot_mask_summary(tmp_path):
    private = tmp_path / "private"
    private.mkdir()

    class Process:
        def poll(self):
            return None

        def wait(self, timeout):
            raise subprocess.TimeoutExpired("/private/server", timeout)

    summary = {"status": "passed"}
    module.finalize_summary(tmp_path, private, summary, Process())
    result = json.loads((tmp_path / "summary.json").read_text())
    assert result == {"status": "failed", "cleanup_failure_type": "TimeoutExpired"}
    assert (private / "stop-gui").exists()


def test_workflow_uploads_only_safe_summary():
    workflow = SCRIPT.parents[2] / "workflows/msinsight-acceptance.yml"
    if not workflow.exists():
        workflow = Path(__file__).with_name("msinsight-acceptance.yml")
    text = workflow.read_text()
    assert "contents: read" in text and "persist-credentials: false" in text
    assert "audit_wheel.py" in text and "07bdf660f10f03a9c13ab313fae149adf62355f8" in text
    upload = text.split("name: Upload sanitized numeric result only")[1]
    assert "ms-evidence/summary.json" in upload
    assert "*.png" not in upload and "private" not in upload


@pytest.mark.parametrize(
    "line", ["parse state changed:4", "parse state changed: 4", "parse state changed:   4"]
)
def test_reuse_state_accepts_real_log_spacing(line):
    assert module.reuse_logs_valid("artifact is up-to-date.\n" + line)


@pytest.mark.parametrize(
    "line", ["parse state changed:40", "parse state changed: 3", "no parser state"]
)
def test_reuse_state_rejects_wrong_or_missing_state(line):
    assert not module.reuse_logs_valid("artifact is up-to-date.\n" + line)


def test_browser_cache_uses_runner_context_only_at_step_scope():
    workflow = SCRIPT.parents[2] / "workflows/msinsight-acceptance.yml"
    import yaml

    job = yaml.safe_load(workflow.read_text())["jobs"]["pinned-consumer"]
    assert "runner." not in json.dumps(job.get("env", {}))
    needed = {
        "Restore pinned original consumer, sequential minimal builds",
        "Real GUI, protocol, reuse and preservation gates",
    }
    steps = [s for s in job["steps"] if s.get("name") in needed]
    assert len(steps) == 2
    assert all(
        s["env"]["PLAYWRIGHT_BROWSERS_PATH"] == "${{ runner.temp }}/ms-playwright-browsers"
        for s in steps
    )


def parser_tree(source, name="snapshot_parser"):
    root = source / "scripts" / name
    for directory in ("base", "simulate", "tools", "util"):
        (root / directory).mkdir(parents=True, exist_ok=True)
    (root / "tools/dump2db.py").write_text("# synthetic parser entrypoint\n")
    return root


def test_parser_discovery_uses_unique_entrypoint_and_module_layout(tmp_path):
    root = parser_tree(tmp_path)
    assert module.discover_snapshot_parser(tmp_path) == root


def test_parser_discovery_rejects_missing_entrypoint(tmp_path):
    (tmp_path / "scripts").mkdir()
    with pytest.raises(ValueError, match="exactly one"):
        module.discover_snapshot_parser(tmp_path)


def test_parser_discovery_rejects_ambiguous_entrypoints(tmp_path):
    parser_tree(tmp_path, "first")
    parser_tree(tmp_path, "second")
    with pytest.raises(ValueError, match="exactly one"):
        module.discover_snapshot_parser(tmp_path)


def test_parser_discovery_rejects_symlinked_entrypoint(tmp_path, monkeypatch):
    root = parser_tree(tmp_path)
    entry = root / "tools/dump2db.py"
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == entry or original(path))
    with pytest.raises(ValueError, match="symlinks"):
        module.discover_snapshot_parser(tmp_path)


def test_parser_discovery_rejects_symlinked_payload(tmp_path, monkeypatch):
    root = parser_tree(tmp_path)
    link = root / "util/escape.py"
    link.write_text("# simulated link entry for a platform-independent guard check\n")
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == link or original(path))
    with pytest.raises(ValueError, match="symlinks"):
        module.discover_snapshot_parser(tmp_path)


def test_parser_discovery_rejects_incomplete_module(tmp_path):
    root = parser_tree(tmp_path)
    (root / "simulate").rmdir()
    with pytest.raises(ValueError, match="Incomplete"):
        module.discover_snapshot_parser(tmp_path)
