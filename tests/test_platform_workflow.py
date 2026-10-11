"""Keep supplemental platform CI bounded without hiding compatibility failures."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / ".github/scripts/run_platform_tests.py"


def runner():
    spec = importlib.util.spec_from_file_location("platform_test_runner", RUNNER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def workflow():
    return yaml.load(
        (ROOT / ".github/workflows/platform.yml").read_text(encoding="utf-8"),
        Loader=yaml.BaseLoader,
    )


def test_platform_ci_runs_exactly_five_bounded_non_linux_python_313_jobs():
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
    assert set(data["jobs"]) == {"platform"}
    job = data["jobs"]["platform"]
    assert job["runs-on"] == "${{ matrix.os }}"
    assert job["strategy"] == {
        "fail-fast": "false",
        "max-parallel": "2",
        "matrix": {
            "include": [
                {
                    "os": "windows-latest",
                    "partition": "shard-0",
                    "command": "python .github/scripts/run_platform_tests.py --shard 0",
                },
                {
                    "os": "windows-latest",
                    "partition": "shard-1",
                    "command": "python .github/scripts/run_platform_tests.py --shard 1",
                },
                {
                    "os": "windows-latest",
                    "partition": "shard-2",
                    "command": "python .github/scripts/run_platform_tests.py --shard 2",
                },
                {
                    "os": "windows-latest",
                    "partition": "shard-3",
                    "command": "python .github/scripts/run_platform_tests.py --shard 3",
                },
                {
                    "os": "macos-latest",
                    "partition": "all",
                    "command": 'python -m pytest -m "not slow" --junitxml=platform-tests.xml -o junit_family=legacy',
                },
            ]
        },
    }
    assert 1 <= int(job["timeout-minutes"]) <= 20
    setup = next(step for step in job["steps"] if step.get("uses") == "actions/setup-python@v5")
    assert setup["with"]["python-version"] == "3.13"


def test_platform_ci_preserves_full_non_slow_collection_and_failure_evidence(monkeypatch):
    job = workflow()["jobs"]["platform"]
    steps = job["steps"]
    commands = [step["run"] for step in steps if "run" in step]
    assert commands == [
        'python -m pip install -e ".[dev]"',
        "python -m pytest tests/test_fixture_provenance.py",
        "${{ matrix.command }}",
    ]
    assert "continue-on-error" not in job
    assert all("continue-on-error" not in step for step in steps)
    assert all("PYTHONWARNINGS" not in env for env in (workflow().get("env", {}), job["env"]))
    upload = next(step for step in steps if step.get("uses") == "actions/upload-artifact@v4")
    assert upload["if"] == "always()"
    assert upload["with"]["path"].splitlines() == ["platform-tests.xml", "platform-partition.json"]
    assert "${{ matrix.os }}" in upload["with"]["name"]
    assert "${{ matrix.partition }}" in upload["with"]["name"]
    module = runner()
    calls = []
    monkeypatch.setattr(module.pytest, "main", lambda *args, **kwargs: calls.append((args, kwargs)))
    module.main(["--shard", "0"])
    assert calls[0][0] == (
        ["-m", "not slow", "--junitxml=platform-tests.xml", "-o", "junit_family=legacy"],
    )
    assert calls[0][1]["plugins"][0].shard == 0


def test_partition_is_deterministic_disjoint_exhaustive_and_balanced():
    module = runner()
    nodeids = [f"tests/test_sample.py::test_value[{n}]" for n in range(101)]
    parts = module.partition_nodeids(nodeids)
    assert parts == module.partition_nodeids(list(reversed(nodeids)))
    assert module.SHARD_COUNT == 4
    assert [len(part) for part in parts] == [26, 25, 25, 25]
    flattened = [node for part in parts for node in part]
    assert len(flattened) == len(set(flattened))
    assert set(flattened) == set(nodeids)


@pytest.mark.parametrize(
    "nodeids,parts",
    [
        (["a", "b", "c"], [["a"], ["b"], ["c"], []]),
        (["a", "b", "c", "d", "e"], [["a"], ["b"], ["c"], ["d"]]),
        (["a", "b", "c", "d"], [["a", "b"], ["b"], ["c"], ["d"]]),
        (["a", "b", "c", "d"], [["a"], ["b"], ["c"], ["unknown"]]),
        (["a", "b", "c", "d"], [["a", "b"], ["c", "d"]]),
        (["a", "a", "b", "c"], [["a"], ["a"], ["b"], ["c"]]),
    ],
)
def test_partition_rejects_missing_duplicate_unknown_or_empty_coverage(nodeids, parts):
    with pytest.raises(pytest.UsageError):
        runner().validate_partition(nodeids, parts)


@pytest.mark.parametrize("shard", [-1, 4])
def test_partition_rejects_unknown_shard(shard):
    with pytest.raises(pytest.UsageError):
        runner().PlatformPartition(shard)


def run_toy_suite(tmp_path, shard, *, corrupt=False):
    # Exercise real pytest marker filtering and execution, not only the helper.
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\nmarkers = slow: large fixture\n", encoding="utf-8"
    )
    (tmp_path / "test_toy.py").write_text(
        "import pytest\n"
        "@pytest.mark.parametrize('value', range(7))\n"
        "def test_regular(value):\n    assert value >= 0\n"
        "@pytest.mark.slow\ndef test_slow():\n    assert False\n",
        encoding="utf-8",
    )
    code = (
        "import importlib.util, pytest\n"
        f"spec = importlib.util.spec_from_file_location('runner', {str(RUNNER)!r})\n"
        "module = importlib.util.module_from_spec(spec)\nspec.loader.exec_module(module)\n"
    )
    if corrupt:
        code += "module.partition_nodeids = lambda ids: [[ids[n]] for n in range(4)]\n"
    code += (
        f"raise SystemExit(pytest.main(['-m', 'not slow', '-v', '--junitxml=toy.xml'], "
        f"plugins=[module.PlatformPartition({shard})]))\n"
    )
    return subprocess.run(
        [sys.executable, "-c", code], cwd=tmp_path, text=True, capture_output=True, check=False
    )


def test_real_pytest_shards_cover_exact_non_slow_collection(tmp_path):
    manifests = []
    for shard in range(4):
        result = run_toy_suite(tmp_path, shard)
        assert result.returncode == 0, result.stdout + result.stderr
        manifest = json.loads((tmp_path / "platform-partition.json").read_text(encoding="utf-8"))
        assert manifest["shard"] == shard
        assert manifest["shard_count"] == 4
        assert manifest["selected"] == manifest["partitions"][shard]
        assert manifest["selection"] == "not slow"
        assert len(manifest["full_collection"]) == 7
        assert all("test_slow" not in node for node in manifest["full_collection"])
        assert f"{len(manifest['selected'])} passed" in result.stdout
        manifests.append(manifest)
    assert len({manifest["collection_sha256"] for manifest in manifests}) == 1
    assert all(
        manifest["full_collection"] == manifests[0]["full_collection"] for manifest in manifests
    )
    assert all(manifest["partitions"] == manifests[0]["partitions"] for manifest in manifests)
    flattened = [node for manifest in manifests for node in manifest["selected"]]
    assert len(flattened) == len(set(flattened))
    assert sorted(flattened) == manifests[0]["full_collection"]


def test_real_pytest_partition_corruption_fails_before_execution(tmp_path):
    result = run_toy_suite(tmp_path, 0, corrupt=True)
    assert result.returncode != 0
    assert "must cover every selected test exactly once" in result.stdout + result.stderr
    assert " PASSED" not in result.stdout
    assert not (tmp_path / "platform-partition.json").exists()
