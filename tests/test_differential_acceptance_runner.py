"""Nightly differential evidence must prove every seed and both real layouts ran."""

import importlib.util
import json
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/run_differential_acceptance.py"


@pytest.fixture
def runner():
    spec = importlib.util.spec_from_file_location("differential_acceptance", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def evidence(runner, root, count=1):
    report, temp = root / "junit.xml", root / "pytest-temp"
    suite = ET.Element("testsuite")
    for index, ((seed, layout), expected) in enumerate(runner.expected_records(count).items()):
        record = {**expected, "scratch_builds": 8 if expected["shards"] > 10 else 0}
        case = ET.SubElement(
            suite,
            "testcase",
            {
                "file": runner.TEST_FILE,
                "classname": runner.TEST_FILE[:-3].replace("/", "."),
                "name": f"{runner.TEST_NAME}[{layout}-seed-{seed}]",
            },
        )
        props = ET.SubElement(case, "properties")
        for name, value in record.items():
            ET.SubElement(props, "property", {"name": name, "value": str(value)})
        folder = temp / str(index) / f"seed-{seed}-{layout}"
        folder.mkdir(parents=True)
        (folder / "coverage.json").write_text(json.dumps(record))
    ET.ElementTree(suite).write(report)
    return report, temp


def test_exact_200_profile_requires_all_400_identities_and_matching_artifacts(runner, tmp_path):
    report, temp = evidence(runner, tmp_path, 200)
    result = runner.read_evidence(report, temp, 200)
    assert result["seed_format_cases"] == len(result["test_nodes"]) == 400
    assert result["seed_count"] == len(result["seeds"]) == 200
    assert result["comparisons"] == 28_864
    assert result["formats"] == ["v1", "v2"] and result["unexpected_errors"] == 0
    assert result["scratch_builds"] > 0


@pytest.mark.parametrize(
    "corruption",
    [
        "missing_report",
        "missing_case",
        "extra_case",
        "duplicate_case",
        "wrong_seed",
        "wrong_file",
        "wrong_class",
        "skipped",
        "failure",
        "error",
        "missing_property",
        "duplicate_property",
        "wrong_property",
        "missing_artifact",
        "duplicate_artifact",
        "wrong_artifact",
        "error_artifact",
        "failure_artifact",
        "no_scratch",
        "bad_identity",
    ],
)
def test_empty_partial_skipped_duplicate_or_inconsistent_evidence_fails(
    runner, tmp_path, corruption
):
    report, temp = evidence(runner, tmp_path)
    tree = ET.parse(report)
    suite = tree.getroot()
    case = suite.find("testcase")
    props = case.find("properties")
    paths = sorted(temp.rglob("coverage.json"))
    if corruption == "missing_report":
        report.unlink()
    elif corruption == "missing_case":
        suite.remove(case)
    elif corruption in ("extra_case", "duplicate_case"):
        ET.SubElement(suite, "testcase", dict(case.attrib))
    elif corruption == "wrong_seed":
        case.set("name", f"{runner.TEST_NAME}[v1-seed-999]")
    elif corruption == "wrong_file":
        case.set("file", "tests/other.py")
    elif corruption == "wrong_class":
        case.set("classname", "tests.other")
    elif corruption in ("skipped", "failure", "error"):
        ET.SubElement(case, corruption)
    elif corruption == "missing_property":
        props.remove(props.find("property[@name='seed']"))
    elif corruption == "duplicate_property":
        ET.SubElement(props, "property", {"name": "seed", "value": "0"})
    elif corruption == "wrong_property":
        props.find("property[@name='comparisons']").set("value", "1")
    elif corruption == "missing_artifact":
        paths[0].unlink()
    elif corruption == "duplicate_artifact":
        paths[1].write_bytes(paths[0].read_bytes())
    elif corruption in ("wrong_artifact", "error_artifact", "bad_identity"):
        record = json.loads(paths[0].read_text())
        field, value = {
            "wrong_artifact": ("comparisons", 1),
            "error_artifact": ("unexpected_errors", 2),
            "bad_identity": ("seed", []),
        }[corruption]
        record[field] = value
        paths[0].write_text(json.dumps(record))
    elif corruption == "failure_artifact":
        (paths[0].parent / "differential-failure.json").write_text("{}")
    elif corruption == "no_scratch":
        for path in paths:
            record = json.loads(path.read_text())
            record["scratch_builds"] = 0
            path.write_text(json.dumps(record))
        for prop in suite.findall(".//property[@name='scratch_builds']"):
            prop.set("value", "0")
    if corruption != "missing_report":
        tree.write(report)
    with pytest.raises(runner.AcceptanceError):
        runner.read_evidence(report, temp, 1)


def test_runner_requires_success_clears_stale_report_and_removes_seed_override(
    runner, tmp_path, monkeypatch
):
    output = tmp_path / "run"
    output.mkdir()
    (output / "junit.xml").write_text("old success")
    (output / "summary.json").write_text('{"status":"passed"}')
    monkeypatch.setenv("PT_SNAP_DIFFERENTIAL_SEED", "1234")
    monkeypatch.setenv("PT_SNAP_DIFFERENTIAL_SEEDS", "1")
    monkeypatch.setenv("PYTEST_ADDOPTS", "-k nothing")
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command[0] == "git":
            return subprocess.CompletedProcess(command, 0, "a" * 40 + "\n")
        assert not (output / "junit.xml").exists()
        env = kwargs["env"]
        assert env["PT_SNAP_DIFFERENTIAL_SEEDS"] == "200"
        assert "PT_SNAP_DIFFERENTIAL_SEED" not in env and "PYTEST_ADDOPTS" not in env
        assert env["PYTHONPATH"] == str(runner.ROOT / "src")
        assert command[3] == runner.TEST_NODE
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(runner.subprocess, "run", run)
    with pytest.raises(runner.AcceptanceError, match="did not write"):
        runner.run_acceptance(output)
    saved = json.loads((output / "summary.json").read_text())
    assert saved["status"] == "failed" and saved["seed_count"] == 200
    assert saved["source_sha"] == "a" * 40 and len(calls) == 2


@pytest.mark.parametrize("returncode", [1, 5])
def test_failed_or_empty_pytest_never_passes(runner, tmp_path, monkeypatch, returncode):
    def run(command, **kwargs):
        if command[0] == "git":
            return subprocess.CompletedProcess(command, 0, "a" * 40 + "\n")
        return subprocess.CompletedProcess(command, returncode)

    monkeypatch.setattr(runner.subprocess, "run", run)
    with pytest.raises(runner.AcceptanceError, match=f"pytest exited with {returncode}"):
        runner.run_acceptance(tmp_path, 1)
    assert json.loads((tmp_path / "summary.json").read_text())["status"] == "failed"


@pytest.mark.parametrize("count", (0, -1, 10001))
def test_invalid_profile_replaces_old_passed_summary(runner, tmp_path, count):
    (tmp_path / "summary.json").write_text('{"status":"passed"}')
    (tmp_path / "junit.xml").write_text("old success")
    with pytest.raises(ValueError, match="PT_SNAP_DIFFERENTIAL_SEEDS"):
        runner.run_acceptance(tmp_path, count)
    saved = json.loads((tmp_path / "summary.json").read_text())
    assert saved["status"] == "failed" and saved["seed_count"] == count
    assert "PT_SNAP_DIFFERENTIAL_SEEDS" in saved["error"]
    assert not (tmp_path / "junit.xml").exists()


def test_import_setup_failure_replaces_old_passed_summary(runner, tmp_path, monkeypatch):
    (tmp_path / "summary.json").write_text('{"status":"passed"}')

    def broken_setup(count):
        raise ImportError("synthetic setup failure")

    monkeypatch.setattr(runner, "expected_records", broken_setup)
    with pytest.raises(ImportError, match="synthetic setup failure"):
        runner.run_acceptance(tmp_path)
    saved = json.loads((tmp_path / "summary.json").read_text())
    assert saved["status"] == "failed" and saved["error"] == "synthetic setup failure"
