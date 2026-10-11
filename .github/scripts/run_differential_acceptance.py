"""Run the required paired seed profile and reject skipped, partial or stale evidence."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEST_FILE = "tests/core/test_dataset_realistic.py"
TEST_NAME = "test_seeded_lifecycle_windows_match_single_database_strictly"
TEST_NODE = f"{TEST_FILE}::{TEST_NAME}"


class AcceptanceError(RuntimeError):
    pass


def expected_records(seed_count: int) -> dict[tuple[int, str], dict]:
    # This runner is intentionally source-test acceptance, separate from the
    # installed-wheel gate. Import the exact same deterministic profile contract.
    sys.path[:0] = [str(ROOT), str(ROOT / "src")]
    try:
        from tests.core.dataset_differential_cases import (
            SUPPORTED_TEMPLATES,
            capacity_for_seed,
            configured_seeds,
            query_cases,
        )
        from tests.core.dataset_lifecycle_fixtures import EVENT_COUNT
    finally:
        del sys.path[:2]
    seeds = configured_seeds({"PT_SNAP_DIFFERENTIAL_SEEDS": str(seed_count)})
    return {
        (seed, layout): {
            "seed": seed,
            "format": layout,
            "capacity": capacity_for_seed(seed),
            "shards": (EVENT_COUNT + capacity_for_seed(seed) - 1) // capacity_for_seed(seed),
            "comparisons": len(query_cases(seed, capacity_for_seed(seed))),
            "unexpected_errors": 0,
            "templates": sorted(SUPPORTED_TEMPLATES),
        }
        for seed in seeds
        for layout in ("v1", "v2")
    }


def read_evidence(report: Path, temp_dir: Path, seed_count: int) -> dict:
    expected = expected_records(seed_count)
    if not report.is_file():
        raise AcceptanceError("pytest did not write its JUnit report")
    cases = ET.parse(report).findall(".//testcase")
    names = [case.get("name") for case in cases]
    expected_names = {f"{TEST_NAME}[{layout}-seed-{seed}]" for seed, layout in expected}
    if len(names) != len(expected_names) or set(names) != expected_names:
        raise AcceptanceError(f"Expected exactly {len(expected_names)} distinct seed/format tests")
    case_by_key = {}
    for case in cases:
        if case.get("file") != TEST_FILE or case.get("classname") != TEST_FILE[:-3].replace(
            "/", "."
        ):
            raise AcceptanceError("JUnit seed case has the wrong source identity")
        if any(case.find(tag) is not None for tag in ("failure", "error", "skipped")):
            raise AcceptanceError(
                f"Every seed/format test must pass without skips: {case.get('name')}"
            )
        properties = case.findall("./properties/property")
        values = {p.get("name"): p.get("value") for p in properties}
        if len(values) != len(properties):
            raise AcceptanceError("Duplicate JUnit evidence properties")
        try:
            key = (int(values["seed"]), values["format"])
        except (KeyError, TypeError, ValueError) as exc:
            raise AcceptanceError("Missing or invalid seed/format properties") from exc
        if key not in expected or case.get("name") != f"{TEST_NAME}[{key[1]}-seed-{key[0]}]":
            raise AcceptanceError("JUnit seed properties do not match the executed test identity")
        case_by_key[key] = values
    paths = list(temp_dir.rglob("coverage.json"))
    if len(paths) != len(expected):
        raise AcceptanceError("Missing or extra per-seed coverage artifacts")
    records = {}
    for path in paths:
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise AcceptanceError("Invalid per-seed coverage object")
        if type(value.get("seed")) is not int or type(value.get("format")) is not str:
            raise AcceptanceError("Invalid per-seed coverage identity types")
        key = (value["seed"], value["format"])
        if key not in expected or key in records:
            raise AcceptanceError("Duplicate or unexpected per-seed coverage identity")
        wanted = expected[key]
        for field, required in wanted.items():
            if type(value.get(field)) is not type(required) or value[field] != required:
                raise AcceptanceError(f"Invalid seed coverage {key}: {field}")
        builds = value.get("scratch_builds")
        if type(builds) is not int or builds < 0:
            raise AcceptanceError("Invalid observed scratch build count")
        for field in (*wanted, "scratch_builds"):
            if case_by_key[key].get(field) != str(value[field]):
                raise AcceptanceError(f"JUnit and artifact evidence disagree for {key}: {field}")
        if (path.parent / "differential-failure.json").exists():
            raise AcceptanceError("A seed retained unexpected failure evidence")
        records[key] = value
    if not any(value["scratch_builds"] for value in records.values()):
        raise AcceptanceError("Profile did not execute the scratch reducer")
    return {
        "seed_count": seed_count,
        "seed_format_cases": len(records),
        "seeds": sorted({seed for seed, _ in records}),
        "formats": ["v1", "v2"],
        "test_nodes": [f"{TEST_FILE}::{name}" for name in sorted(names)],
        "comparisons": sum(value["comparisons"] for value in records.values()),
        "unexpected_errors": 0,
        "scratch_builds": sum(value["scratch_builds"] for value in records.values()),
        "cases_with_scratch": sum(value["scratch_builds"] > 0 for value in records.values()),
        "templates": next(iter(expected.values()))["templates"],
    }


def run_acceptance(output_dir: Path, seed_count: int = 200) -> None:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report, temp_dir = output_dir / "junit.xml", output_dir / "pytest-temp"
    for name in ("junit.xml", "summary.json", "pytest.log"):
        (output_dir / name).unlink(missing_ok=True)
    command = [
        sys.executable,
        "-m",
        "pytest",
        TEST_NODE,
        "-o",
        "junit_family=xunit1",
        f"--junitxml={report}",
        f"--basetemp={temp_dir}",
    ]
    env = os.environ.copy()
    env.pop("PT_SNAP_DIFFERENTIAL_SEED", None)
    env.pop("PYTEST_ADDOPTS", None)
    env["PT_SNAP_DIFFERENTIAL_SEEDS"] = str(seed_count)
    env["PYTHONPATH"] = str(ROOT / "src")
    summary = {
        "status": "failed",
        "seed_count": seed_count,
        "test_node": TEST_NODE,
        "command": command,
    }
    try:
        expected_records(seed_count)  # Setup errors must replace stale green evidence too.
        summary["source_sha"] = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, text=True, capture_output=True
        ).stdout.strip()
        with (output_dir / "pytest.log").open("w") as log:
            result = subprocess.run(
                command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT
            )
        print((output_dir / "pytest.log").read_text(), end="", flush=True)
        summary["pytest_exit_code"] = result.returncode
        if result.returncode:
            raise AcceptanceError(f"pytest exited with {result.returncode}; see pytest.log")
        summary["acceptance"] = read_evidence(report, temp_dir, seed_count)
        summary["status"] = "passed"
    except Exception as exc:
        summary["error"] = str(exc)
        raise
    finally:
        (output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed-count", type=int, default=200)
    args = parser.parse_args()
    try:
        run_acceptance(args.output_dir, args.seed_count)
    except (
        AcceptanceError,
        OSError,
        ValueError,
        ET.ParseError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"Differential acceptance failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
