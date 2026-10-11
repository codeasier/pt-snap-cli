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
BOUNDARY_NAME = "test_installed_default_export_short_final_shard_boundary"


@pytest.fixture
def runner():
    spec = importlib.util.spec_from_file_location("dataset_acceptance_runner", RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_report(path, name, evidence, outcome=None, *, include_boundary=True):
    suite = ET.Element("testsuite")
    case = ET.SubElement(
        suite,
        "testcase",
        name=name,
        file="tests/core/test_dataset_scale_acceptance.py",
        classname="tests.core.test_dataset_scale_acceptance",
    )
    if outcome:
        ET.SubElement(case, outcome)
    if evidence is not None:
        properties = ET.SubElement(case, "properties")
        ET.SubElement(properties, "property", name="dataset_acceptance", value=json.dumps(evidence))
    if include_boundary:
        ET.SubElement(
            suite,
            "testcase",
            name=BOUNDARY_NAME,
            file="tests/core/test_dataset_scale_acceptance.py",
            classname="tests.core.test_dataset_scale_acceptance",
        )
    ET.ElementTree(suite).write(path)


def test_runner_accepts_matching_wheel_evidence(runner, tmp_path):
    report = tmp_path / "junit.xml"
    evidence = {"wheel_sha256": "abc", "events": 1_000_000}
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
        ET.SubElement(
            suite,
            "testcase",
            name=runner.TEST_NAME,
            file="tests/core/test_dataset_scale_acceptance.py",
            classname="tests.core.test_dataset_scale_acceptance",
        )
    ET.ElementTree(suite).write(report)
    with pytest.raises(runner.AcceptanceError, match="exactly one"):
        runner.read_evidence(report, "abc")


def test_runner_rejects_wrong_test_even_if_it_passes(runner, tmp_path):
    report = tmp_path / "junit.xml"
    write_report(report, "unrelated_test", {"wheel_sha256": "abc"})
    with pytest.raises(runner.AcceptanceError, match="exactly one"):
        runner.read_evidence(report, "abc")


def add_case(
    report,
    *,
    name="test_extra",
    file="tests/test_extra.py",
    classname="tests.test_extra",
    outcome=None,
):
    tree = ET.parse(report)
    case = ET.SubElement(tree.getroot(), "testcase", name=name, file=file, classname=classname)
    if outcome:
        ET.SubElement(case, outcome)
    tree.write(report)


def test_runner_accepts_additional_nightly_cases_and_records_complete_identities(runner, tmp_path):
    report = tmp_path / "junit.xml"
    evidence = {"wheel_sha256": "abc"}
    write_report(report, runner.TEST_NAME, evidence)
    add_case(report, name="test_extra[v2]", classname="tests.test_extra.TestRoutes")
    assert runner.read_evidence(report, "abc") == evidence
    assert [runner.test_node_id(case) for case in runner.read_cases(report)] == [
        runner.TEST_NODE,
        runner.BOUNDARY_TEST_NODE,
        "tests/test_extra.py::TestRoutes::test_extra[v2]",
    ]


def test_runner_rejects_missing_configured_gate(runner, tmp_path, monkeypatch):
    report = tmp_path / "junit.xml"
    write_report(report, runner.TEST_NAME, {"wheel_sha256": "abc"})
    required = "tests/test_extra.py::test_extra"
    monkeypatch.setattr(runner, "REQUIRED_TEST_NODES", (runner.TEST_NODE, required))
    with pytest.raises(runner.AcceptanceError, match="Missing required nightly test nodes"):
        runner.read_evidence(report, "abc")
    add_case(report)
    assert runner.read_evidence(report, "abc") == {"wheel_sha256": "abc"}


def test_runner_rejects_duplicate_additional_cases(runner, tmp_path):
    report = tmp_path / "junit.xml"
    write_report(report, runner.TEST_NAME, {"wheel_sha256": "abc"})
    add_case(report)
    add_case(report)
    with pytest.raises(runner.AcceptanceError, match="Duplicate nightly"):
        runner.read_evidence(report, "abc")


@pytest.mark.parametrize("outcome", ["skipped", "failure", "error"])
def test_runner_rejects_any_nonpassing_additional_case(runner, tmp_path, outcome):
    report = tmp_path / "junit.xml"
    write_report(report, runner.TEST_NAME, {"wheel_sha256": "abc"})
    add_case(report, outcome=outcome)
    with pytest.raises(
        runner.AcceptanceError, match="without skips: tests/test_extra.py::test_extra"
    ):
        runner.read_evidence(report, "abc")


def test_same_function_name_in_another_file_cannot_replace_required_wheel_case(runner, tmp_path):
    report = tmp_path / "junit.xml"
    ET.ElementTree(ET.Element("testsuite")).write(report)
    add_case(report, name=runner.TEST_NAME)
    with pytest.raises(runner.AcceptanceError, match="exactly one"):
        runner.read_evidence(report, "abc")


@pytest.mark.parametrize(
    "attributes", [{"file": ""}, {"file": "../tests/test_extra.py"}, {"classname": "wrong"}]
)
def test_runner_rejects_incomplete_or_inconsistent_junit_identity(runner, attributes):
    case = ET.Element(
        "testcase", file="tests/test_extra.py", classname="tests.test_extra", name="test_extra"
    )
    case.attrib.update(attributes)
    with pytest.raises(runner.AcceptanceError, match="identity"):
        runner.test_node_id(case)


def test_nightly_marker_selection_collects_every_configured_gate(runner):
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "--collect-only",
            "--strict-markers",
            "-q",
            "-o",
            "addopts=",
            "-m",
            "nightly",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    collected = {line for line in result.stdout.splitlines() if "::" in line}
    assert set(runner.REQUIRED_TEST_NODES) <= collected


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
        assert command[3:5] == ["-m", "nightly"]
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
    assert summary["required_test_nodes"] == list(runner.REQUIRED_TEST_NODES)
    assert summary["test_nodes"] == (list(runner.REQUIRED_TEST_NODES) if write_junit else [])
    assert summary["status"] == ("passed" if exit_code == 0 and write_junit else "failed")
    assert (output / "pytest.log").read_text() == "captured pytest output\n"


def test_runner_requires_original_short_final_shard_case(runner, tmp_path):
    report = tmp_path / "junit.xml"
    assert runner.BOUNDARY_TEST_NODE in runner.REQUIRED_TEST_NODES
    write_report(report, runner.TEST_NAME, {"wheel_sha256": "abc"}, include_boundary=False)
    with pytest.raises(runner.AcceptanceError, match="Missing required nightly test nodes"):
        runner.read_evidence(report, "abc")


@pytest.mark.parametrize("outcome", ["skipped", "failure", "error"])
def test_runner_rejects_nonpassing_short_final_shard_case(runner, tmp_path, outcome):
    report = tmp_path / "junit.xml"
    write_report(report, runner.TEST_NAME, {"wheel_sha256": "abc"}, include_boundary=False)
    add_case(
        report,
        name=BOUNDARY_NAME,
        file="tests/core/test_dataset_scale_acceptance.py",
        classname="tests.core.test_dataset_scale_acceptance",
        outcome=outcome,
    )
    with pytest.raises(runner.AcceptanceError, match="without skips"):
        runner.read_evidence(report, "abc")
