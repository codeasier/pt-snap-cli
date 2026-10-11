"""Fail-closed CI wrapper contracts without repeating the expensive scale test."""

import hashlib
import importlib.util
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

RUNNER = Path(".github/scripts/run_dataset_acceptance.py")


@pytest.fixture
def runner():
    spec = importlib.util.spec_from_file_location("dataset_acceptance_runner", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_report(path, name, evidence, outcome=None):
    suite = ET.Element("testsuite")
    case = ET.SubElement(suite, "testcase", name=name)
    if outcome:
        ET.SubElement(case, outcome)
    if evidence is not None:
        properties = ET.SubElement(case, "properties")
        ET.SubElement(properties, "property", name="dataset_acceptance", value=json.dumps(evidence))
    ET.ElementTree(suite).write(path)


def test_runner_accepts_matching_wheel_evidence(runner, tmp_path):
    report = tmp_path / "junit.xml"
    evidence = {"wheel_sha256": "abc", "events": 500_002}
    write_report(report, runner.TEST_NAME, evidence)
    assert runner.read_evidence(report, "abc") == evidence


@pytest.mark.parametrize("outcome", ["skipped", "failure", "error"])
def test_runner_rejects_nonpassing_acceptance(runner, tmp_path, outcome):
    report = tmp_path / "junit.xml"
    write_report(report, runner.TEST_NAME, {"wheel_sha256": "abc"}, outcome)
    with pytest.raises(runner.AcceptanceError, match="without skips"):
        runner.read_evidence(report, "abc")


@pytest.mark.parametrize("evidence", [None, {}, {"wheel_sha256": "other"}, []])
def test_runner_rejects_missing_or_wrong_artifact_evidence(runner, tmp_path, evidence):
    report = tmp_path / "junit.xml"
    write_report(report, runner.TEST_NAME, evidence)
    with pytest.raises(runner.AcceptanceError):
        runner.read_evidence(report, "abc")


@pytest.mark.parametrize("count", [0, 2])
def test_runner_rejects_empty_or_extra_collection(runner, tmp_path, count):
    report = tmp_path / "junit.xml"
    suite = ET.Element("testsuite")
    for _ in range(count):
        ET.SubElement(suite, "testcase", name=runner.TEST_NAME)
    ET.ElementTree(suite).write(report)
    with pytest.raises(runner.AcceptanceError, match="exactly one"):
        runner.read_evidence(report, "abc")


def test_runner_rejects_wrong_test_even_if_it_passes(runner, tmp_path):
    report = tmp_path / "junit.xml"
    write_report(report, "unrelated_test", {"wheel_sha256": "abc"})
    with pytest.raises(runner.AcceptanceError, match="exactly one"):
        runner.read_evidence(report, "abc")


def test_runner_rejects_duplicate_evidence(runner, tmp_path):
    report = tmp_path / "junit.xml"
    write_report(report, runner.TEST_NAME, {"wheel_sha256": "abc"})
    tree = ET.parse(report)
    properties = tree.find(".//properties")
    assert properties is not None
    ET.SubElement(properties, "property", name="dataset_acceptance", value="{}")
    tree.write(report)
    with pytest.raises(runner.AcceptanceError, match="exactly one dataset_acceptance"):
        runner.read_evidence(report, "abc")


def test_missing_wheel_fails_before_pytest(tmp_path):
    output = tmp_path / "results"
    output.mkdir()
    (output / "summary.json").write_text('{"status": "passed"}')
    (output / "junit.xml").write_text("old passing report")
    (output / "pytest.log").write_text("old passing output")
    result = subprocess.run(
        [
            sys.executable,
            str(RUNNER),
            "--wheel",
            str(tmp_path / "missing.whl"),
            "--output-dir",
            str(tmp_path / "results"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "A built wheel is required" in result.stderr
    assert not (output / "junit.xml").exists()
    assert not (output / "pytest.log").exists()
    summary = json.loads((output / "summary.json").read_text())
    assert summary["status"] == "failed"
    assert "A built wheel is required" in summary["error"]


@pytest.mark.parametrize("exit_code,write_junit", [(0, True), (0, False), (1, True), (5, False)])
def test_runner_records_checkout_and_artifact_with_fail_closed_results(
    runner, tmp_path, monkeypatch, exit_code, write_junit
):
    wheel = tmp_path / "built.whl"
    wheel.write_bytes(b"test artifact")
    wheel_hash = hashlib.sha256(wheel.read_bytes()).hexdigest()
    output = tmp_path / "results"
    output.mkdir()
    report = output / "junit.xml"
    write_report(report, runner.TEST_NAME, {"wheel_sha256": wheel_hash})
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert kwargs["cwd"] == runner.ROOT
        if command[0] == "git":
            return subprocess.CompletedProcess(command, 0, stdout="checkout-sha\n")
        assert command[:3] == [sys.executable, "-m", "pytest"]
        assert runner.TEST_NODE in command
        assert "junit_family=xunit1" in command
        assert kwargs["env"]["PT_SNAP_ACCEPTANCE_WHEEL"] == str(wheel)
        assert kwargs["env"]["PT_SNAP_ACCEPTANCE_EVIDENCE_DIR"] == str(output)
        assert not report.exists(), "stale JUnit must be removed before this run"
        kwargs["stdout"].write("captured pytest output\n")
        if write_junit:
            write_report(report, runner.TEST_NAME, {"wheel_sha256": wheel_hash})
        return subprocess.CompletedProcess(command, exit_code)

    monkeypatch.setattr(runner.subprocess, "run", run)
    if exit_code or not write_junit:
        with pytest.raises(runner.AcceptanceError):
            runner.run_acceptance(wheel, output)
    else:
        runner.run_acceptance(wheel, output)
    assert len(calls) == 2
    summary = json.loads((output / "summary.json").read_text())
    assert summary["source_sha"] == "checkout-sha"
    assert summary["wheel_sha256"] == wheel_hash
    assert summary["pytest_exit_code"] == exit_code
    assert summary["status"] == ("passed" if exit_code == 0 and write_junit else "failed")
    assert (output / "pytest.log").read_text() == "captured pytest output\n"
