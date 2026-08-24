from pathlib import Path
from shutil import copytree

import pytest
import yaml

from tests.skills.harness.descriptors import DescriptorError, load_suite

SUITE_DIRECTORY = Path("tests/skills/suites/pt-snap-memory-leak")
SUITE_PATH = SUITE_DIRECTORY / "suite.yaml"


def test_memory_leak_suite_loads_and_covers_required_branches() -> None:
    suite = load_suite(SUITE_PATH)

    assert suite.skill_name == "pt-snap-memory-leak"
    assert suite.profile == "diagnostic-readonly"
    assert [case.id for case in suite.cases] == [
        "allocator-cache",
        "pending-free",
        "address-reuse",
        "pickle-refusal",
    ]
    covered = {branch for case in suite.cases for branch in case.covers}
    assert set(suite.required_branches) <= covered
    assert (
        sum(objective.weight for objective in suite.objectives if objective.mode == "score") == 100
    )


def test_suite_rejects_an_uncovered_required_branch(tmp_path: Path) -> None:
    copied_suite = tmp_path / "suite"
    copytree(SUITE_DIRECTORY, copied_suite)
    suite_path = copied_suite / "suite.yaml"
    data = yaml.safe_load(suite_path.read_text())
    data["coverage"]["required_branches"].append("device.ambiguous")
    suite_path.write_text(yaml.safe_dump(data, sort_keys=False))

    with pytest.raises(DescriptorError, match="required branches are uncovered"):
        load_suite(suite_path)


def test_case_rejects_a_cyclic_tool_order(tmp_path: Path) -> None:
    copied_suite = tmp_path / "suite"
    copytree(SUITE_DIRECTORY, copied_suite)
    case_path = copied_suite / "cases" / "allocator-cache.yaml"
    data = yaml.safe_load(case_path.read_text())
    data["expected_tools"]["partial_order"].append(
        {"before": "inspect_peaks", "after": "validate_database"}
    )
    case_path.write_text(yaml.safe_dump(data, sort_keys=False))

    with pytest.raises(DescriptorError, match="contains a cycle"):
        load_suite(copied_suite / "suite.yaml")


def test_case_rejects_mount_path_traversal(tmp_path: Path) -> None:
    copied_suite = tmp_path / "suite"
    copytree(SUITE_DIRECTORY, copied_suite)
    case_path = copied_suite / "cases" / "allocator-cache.yaml"
    data = yaml.safe_load(case_path.read_text())
    data["fixture"]["mount_path"] = "/fixtures/../project/result.db"
    case_path.write_text(yaml.safe_dump(data, sort_keys=False))

    with pytest.raises(DescriptorError, match="cannot contain '..'"):
        load_suite(copied_suite / "suite.yaml")


def test_case_rejects_unnormalized_mount_path(tmp_path: Path) -> None:
    copied_suite = tmp_path / "suite"
    copytree(SUITE_DIRECTORY, copied_suite)
    case_path = copied_suite / "cases" / "allocator-cache.yaml"
    data = yaml.safe_load(case_path.read_text())
    data["fixture"]["mount_path"] = "/fixtures//cache.db"
    case_path.write_text(yaml.safe_dump(data, sort_keys=False))

    with pytest.raises(DescriptorError, match="normalized POSIX path"):
        load_suite(copied_suite / "suite.yaml")


def test_suite_exposes_runner_defaults_and_result_contract() -> None:
    suite = load_suite(SUITE_PATH)

    assert suite.runner == "local-agent"
    assert suite.repetitions == 3
    assert suite.timeout_seconds == 240
    assert suite.sandbox.network == "disabled"
    assert suite.sandbox.home == "isolated"
    assert suite.sandbox.project == "read_only"
    assert suite.sandbox.fixtures == "read_only"
    assert suite.sandbox.clear_environment == ("PT_SNAP_DB_PATH",)
    assert suite.required_result_fields == ("classification", "facts", "claims", "unknowns")


def test_refusal_case_declares_a_zero_call_budget() -> None:
    suite = load_suite(SUITE_PATH)

    assert suite.case("pickle-refusal").max_tool_calls == 0
    assert suite.case("allocator-cache").max_tool_calls is None


def test_case_rejects_a_negative_call_budget(tmp_path: Path) -> None:
    copied_suite = tmp_path / "suite"
    copytree(SUITE_DIRECTORY, copied_suite)
    case_path = copied_suite / "cases" / "pickle-refusal.yaml"
    data = yaml.safe_load(case_path.read_text())
    data["expected_tools"]["max_calls"] = -1
    case_path.write_text(yaml.safe_dump(data, sort_keys=False))

    with pytest.raises(DescriptorError, match="max_calls must be an integer >= 0"):
        load_suite(copied_suite / "suite.yaml")


def test_case_rejects_non_mapping_expect_output(tmp_path: Path) -> None:
    copied_suite = tmp_path / "suite"
    copytree(SUITE_DIRECTORY, copied_suite)
    case_path = copied_suite / "cases" / "allocator-cache.yaml"
    data = yaml.safe_load(case_path.read_text())
    data["expected_tools"]["actions"][1]["expect_output"] = ["peak_reserved: 8192"]
    case_path.write_text(yaml.safe_dump(data, sort_keys=False))

    with pytest.raises(DescriptorError, match="expect_output must be a mapping"):
        load_suite(copied_suite / "suite.yaml")
