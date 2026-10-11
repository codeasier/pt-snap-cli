"""Run the installed-wheel gate and reject empty, skipped or stale evidence.

This selects nightly tests and requires the public CLI/API wheel case. It does
not claim clean dependency isolation or complete default-scale coverage; those
are contracts of the selected test, not of this CI runner.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
TEST_NAME = "test_installed_trusted_producer_default_export_cli_and_api"
TEST_NODE = f"tests/core/test_dataset_scale_acceptance.py::{TEST_NAME}"
# Extend this tuple alongside new mandatory nightly gates. Never list future
# files that have not landed: the runner rejects any missing configured node.
REQUIRED_TEST_NODES = (TEST_NODE,)


class AcceptanceError(RuntimeError):
    pass


def test_node_id(case: ET.Element) -> str:
    """Recover a complete pytest identity from the required xunit1 fields."""
    file = case.get("file", "")
    name = case.get("name", "")
    classname = case.get("classname", "")
    path = PurePosixPath(file)
    if not name or path.is_absolute() or ".." in path.parts or path.suffix != ".py":
        raise AcceptanceError(f"JUnit testcase has no valid source identity: {case.attrib}")
    module = file.removesuffix(".py").replace("/", ".")
    if classname == module:
        classes = ""
    elif classname.startswith(module + "."):
        classes = classname[len(module) + 1 :].replace(".", "::") + "::"
    else:
        raise AcceptanceError(f"JUnit testcase has an inconsistent class identity: {case.attrib}")
    return f"{file}::{classes}{name}"


def read_cases(report: Path) -> list[ET.Element]:
    if not report.is_file():
        raise AcceptanceError("pytest did not write its JUnit report")
    return ET.parse(report).findall(".//testcase")


def read_evidence(report: Path, wheel_sha256: str) -> dict:
    """Require the wheel case plus every registered gate, with no silent skips."""
    cases = read_cases(report)
    nodes = [test_node_id(case) for case in cases]
    if nodes.count(TEST_NODE) != 1:
        raise AcceptanceError(f"Expected exactly one {TEST_NODE} result")
    if len(nodes) != len(set(nodes)):
        raise AcceptanceError("Duplicate nightly testcase identities")
    missing = set(REQUIRED_TEST_NODES) - set(nodes)
    if missing:
        raise AcceptanceError(f"Missing required nightly test nodes: {sorted(missing)}")
    for node, case in zip(nodes, cases, strict=True):
        if any(case.find(tag) is not None for tag in ("skipped", "failure", "error")):
            raise AcceptanceError(f"Nightly acceptance must pass, without skips: {node}")
    wheel_case = cases[nodes.index(TEST_NODE)]
    properties = wheel_case.findall("./properties/property[@name='dataset_acceptance']")
    if len(properties) != 1:
        raise AcceptanceError("Expected exactly one dataset_acceptance evidence property")
    evidence = json.loads(properties[0].get("value", ""))
    if not isinstance(evidence, dict) or evidence.get("wheel_sha256") != wheel_sha256:
        raise AcceptanceError("Acceptance evidence does not match the supplied wheel SHA-256")
    return evidence


def run_acceptance(wheel: Path, output_dir: Path) -> None:
    wheel = wheel.resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report = output_dir / "junit.xml"
    # Reusing an output directory must never let a previous green run mask this one.
    for name in ("junit.xml", "summary.json", "pytest.log"):
        (output_dir / name).unlink(missing_ok=True)
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-m",
        "nightly",
        "-o",
        "junit_family=xunit1",
        f"--junitxml={report}",
    ]
    env = os.environ.copy()
    env["PT_SNAP_ACCEPTANCE_WHEEL"] = str(wheel)
    env["PT_SNAP_ACCEPTANCE_EVIDENCE_DIR"] = str(output_dir)
    summary = {
        "wheel": str(wheel),
        "test_node": TEST_NODE,
        "required_test_nodes": list(REQUIRED_TEST_NODES),
        "test_nodes": [],
        "command": command,
        "status": "failed",
    }
    try:
        if not wheel.is_file() or wheel.suffix != ".whl":
            raise AcceptanceError(f"A built wheel is required: {wheel}")
        wheel_sha256 = hashlib.sha256(wheel.read_bytes()).hexdigest()
        summary["wheel_sha256"] = wheel_sha256
        source_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.strip()
        summary["source_sha"] = source_sha
        print(
            f"Running nightly acceptance at {source_sha}; required: {REQUIRED_TEST_NODES}",
            flush=True,
        )
        with (output_dir / "pytest.log").open("w") as log:
            result = subprocess.run(
                command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT
            )
        print((output_dir / "pytest.log").read_text(), end="", flush=True)
        summary["pytest_exit_code"] = result.returncode
        if report.is_file():
            summary["test_nodes"] = [test_node_id(case) for case in read_cases(report)]
        if result.returncode != 0:
            raise AcceptanceError(f"pytest exited with {result.returncode}; see pytest.log")
        summary["acceptance"] = read_evidence(report, wheel_sha256)
        summary["status"] = "passed"
    except Exception as exc:
        summary["error"] = str(exc)
        raise
    finally:
        (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wheel", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        run_acceptance(args.wheel, args.output_dir)
    except (
        AcceptanceError,
        OSError,
        ValueError,
        ET.ParseError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"Dataset acceptance failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
