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
