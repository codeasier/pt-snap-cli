"""Keep supplemental platform CI bounded without hiding compatibility failures."""

from pathlib import Path

import yaml


def workflow():
    return yaml.load(
        Path(".github/workflows/platform.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )


def test_platform_ci_runs_exactly_two_non_linux_python_313_jobs():
    data = workflow()
    assert set(data["on"]) == {"push", "pull_request", "workflow_dispatch"}
    assert data["on"]["push"]["branches"] == ["main"]
    assert data["on"]["pull_request"]["branches"] == ["main"]
    assert set(data["on"]["pull_request"]["types"]) == {
        "opened",
        "synchronize",
        "reopened",
        "edited",
    }
    assert data["permissions"] == {"contents": "read"}
    assert data["concurrency"]["cancel-in-progress"] == "true"
    jobs = data["jobs"]
    assert set(jobs) == {"platform"}
    job = jobs["platform"]
    assert job["runs-on"] == "${{ matrix.os }}"
    assert job["strategy"] == {
        "fail-fast": "false",
        "max-parallel": "2",
        "matrix": {"os": ["windows-latest", "macos-latest"]},
    }
    assert 1 <= int(job["timeout-minutes"]) <= 20
    setup = next(step for step in job["steps"] if step.get("uses") == "actions/setup-python@v5")
    assert setup["with"]["python-version"] == "3.13"


def test_platform_ci_preserves_full_non_slow_collection_and_failure_evidence():
    job = workflow()["jobs"]["platform"]
    steps = job["steps"]
    commands = [step["run"] for step in steps if "run" in step]
    assert commands == [
        'python -m pip install -e ".[dev]"',
        "python -m pytest tests/test_fixture_provenance.py",
        'python -m pytest -m "not slow" --junitxml=platform-tests.xml -o junit_family=legacy',
    ]
    assert "continue-on-error" not in job
    assert all("continue-on-error" not in step for step in steps)
    assert all("PYTHONWARNINGS" not in env for env in (workflow().get("env", {}), job["env"]))
    upload = next(step for step in steps if step.get("uses") == "actions/upload-artifact@v4")
    assert upload["if"] == "always()"
    assert upload["with"]["path"] == "platform-tests.xml"
    assert "${{ matrix.os }}" in upload["with"]["name"]
