"""Protect fast/full/nightly boundaries and the existing quality gates."""

from pathlib import Path

import yaml


def workflow():
    return yaml.load(Path(".github/workflows/test.yml").read_text(), Loader=yaml.BaseLoader)


def named_steps(job):
    return {step["name"]: step for step in job["steps"] if "name" in step}


def test_compatibility_matrix_leaves_slow_and_coverage_on_python_313():
    job = workflow()["jobs"]["test"]
    assert job["strategy"]["matrix"]["python-version"] == ["3.10", "3.11", "3.12", "3.13"]
    steps = named_steps(job)
    fast = steps["Run non-slow compatibility tests"]
    assert fast["if"] == "matrix.python-version != '3.13'"
    assert fast["run"] == 'pytest -m "not slow and not nightly"'
    full = steps["Run full PR tests with coverage"]
    assert full["if"] == "matrix.python-version == '3.13'"
    assert full["run"] == 'pytest -m "not nightly" --cov --cov-report=xml --cov-report=term-missing'
    assert (
        'markers = ["nightly: million-scale acceptance gate (scheduled/manual only)"]'
        in Path("pyproject.toml").read_text()
    )
    assert "if" not in steps["Verify executable fixture provenance"]
    names = list(steps)
    assert names.index("Verify executable fixture provenance") < names.index(fast["name"])
    assert names.index("Verify executable fixture provenance") < names.index(full["name"])


def test_full_tier_preserves_independent_coverage_floors_and_packaging():
    steps = named_steps(workflow()["jobs"]["test"])
    guard = steps["Guard critical runtime coverage"]
    assert guard["if"] == "matrix.python-version == '3.13'"
    for file, floor in (
        ("core/snapshot_import_backend.py", 90),
        ("simulate/simulated_caching_allocator.py", 88),
        ("simulate/snapshot_mutator.py", 84),
    ):
        assert f"--include='*/{file}' --fail-under={floor}" in guard["run"]
    config = Path("pyproject.toml").read_text()
    assert "branch = true" in config and "fail_under = 90" in config
    for name in (
        "Build wheel",
        "Audit wheel contents against source",
        "Clean-wheel Agent acceptance",
    ):
        assert steps[name]["if"] == "matrix.python-version == '3.13'"
    assert steps["Upload coverage report"]["if"] == "matrix.python-version == '3.13' && always()"


def test_ci_preserves_least_privilege_and_checks_the_published_commit():
    config = workflow()
    assert config["permissions"] == {"contents": "read"}
    assert "pull_request_target" not in config["on"]
    assert config["on"]["pull_request"]["types"] == ["opened", "synchronize", "reopened", "edited"]
    assert "workflow_call" in config["on"]
    jobs = config["jobs"]
    for name in ("snapshot-provenance", "lint", "browser", "test"):
        checkout = jobs[name]["steps"][0]
        assert checkout["uses"] == "actions/checkout@v4"
        assert checkout["with"]["ref"] == "${{ github.event.pull_request.head.sha || github.sha }}"
    assert jobs["snapshot-provenance"]["steps"][0]["with"]["fetch-depth"] == "0"
    assert (
        "--require-decision"
        in named_steps(jobs["snapshot-provenance"])[
            "Require provenance evaluation for snapshot runtime changes"
        ]["run"]
    )
    browser = named_steps(jobs["browser"])["Run required Chromium interaction tests"]
    assert browser["env"]["PT_SNAP_REQUIRE_BROWSER"] == "1"
    assert "tests/test_memory_tree_browser.py" in browser["run"]
    lint = named_steps(jobs["lint"])
    for name in ("Ruff lint check", "Black format check", "basedPyright check"):
        assert name in lint


def test_nightly_and_manual_gate_build_and_audit_before_required_acceptance():
    config = workflow()
    assert "workflow_dispatch" in config["on"]
    assert config["on"]["schedule"] == [{"cron": "17 3 * * *"}]
    job = config["jobs"]["dataset-acceptance"]
    assert (
        job["if"] == "github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'"
    )
    assert job["timeout-minutes"] == "30"
    assert job["steps"][0]["with"] == {"fetch-depth": "0", "ref": "${{ github.sha }}"}
    steps = named_steps(job)
    names = list(steps)
    order = [
        "Verify executable fixture provenance",
        "Build wheel",
        "Audit wheel contents against source",
        "Run required installed-wheel dataset acceptance",
        "Upload dataset acceptance evidence",
    ]
    assert [names.index(name) for name in order] == sorted(names.index(name) for name in order)
    acceptance = steps["Run required installed-wheel dataset acceptance"]["run"]
    assert "assert len(wheels) == 1" in acceptance
    assert "python .github/scripts/run_dataset_acceptance.py" in acceptance
    assert '--wheel "$WHEEL" --output-dir .tmp/dataset-acceptance' in acceptance
    for step in job["steps"]:
        assert "continue-on-error" not in step
    upload = steps["Upload dataset acceptance evidence"]
    assert upload["if"] == "always()"
    assert upload["with"]["if-no-files-found"] == "error"
    assert upload["with"]["include-hidden-files"] == "true"
    assert upload["with"]["path"] == ".tmp/dataset-acceptance/"
    assert "${{ github.sha }}" in upload["with"]["name"]
