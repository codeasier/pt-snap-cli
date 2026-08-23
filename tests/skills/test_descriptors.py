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
