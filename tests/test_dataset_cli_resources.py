"""Small deterministic CLI resource contracts, required on every PR (#253)."""

import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest

import pt_snap_cli
from pt_snap_cli.core.native_dataset_contract import NATIVE_FORMAT
from tests.test_dataset_focus import make_dataset
from tests.test_native_dataset import dataset as native_dataset

PROBE = Path(__file__).with_name("dataset_cli_resource_probe.py")


@pytest.fixture(params=["compatibility", "native"])
def artifact(request, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    for name in ("PT_SNAP_DB_PATH", "PT_SNAP_QUERY_TIMEOUT", "PT_SNAP_DATASET_CACHE"):
        monkeypatch.delenv(name, raising=False)
    return (
        make_dataset(tmp_path / "dataset", devices=(0, 1), slices=2)
        if request.param == "compatibility"
        else native_dataset(tmp_path)
    )


def run_probe(tmp_path, root, arguments, *, cache=None, stage="none", completion=False):
    env = os.environ.copy()
    # Use the same runtime as the parent test, from an isolated CWD/home. No
    # editable installation is repointed and no source checkout is inferred.
    env["PYTHONPATH"] = str(Path(pt_snap_cli.__file__).resolve().parents[1])
    env["HOME"] = env["USERPROFILE"] = str(tmp_path)
    for key in ("PT_SNAP_DB_PATH", "PT_SNAP_QUERY_TIMEOUT", "PT_SNAP_DATASET_CACHE"):
        env.pop(key, None)
    if cache is not None:
        env["PT_SNAP_DATASET_CACHE"] = cache
    if completion:
        env.update(
            _PT_SNAP_COMPLETE="complete_bash",
            COMP_WORDS="pt-snap report peak-memory --device ",
            COMP_CWORD="4",
        )
    evidence = tmp_path / "cli-resource-evidence.json"
    result = subprocess.run(
        [sys.executable, str(PROBE), str(evidence), str(root), stage, *arguments],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    assert evidence.exists(), (result.stdout, result.stderr)
    return result, json.loads(evidence.read_text())


@pytest.mark.parametrize("cache", [None, "immutable"], ids=["default-strong", "explicit-immutable"])
def test_cli_report_hash_passes_and_logical_bytes(artifact, tmp_path, cache):
    root = artifact
    result, evidence = run_probe(
        tmp_path, root, ["report", "peak-memory", str(root), "--device", "0", "--json"], cache=cache
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["event_id"] is not None
    files = {
        str(path.relative_to(root)): path.stat().st_size
        for path in root.rglob("*")
        if path.is_file()
    }
    reads = evidence["hash_reads"]
    assert evidence["guards"] == 2
    assert all(row["completed"] and row["bytes_read"] == files[row["path"]] for row in reads)
    # Immutable is opt-in and only supported with POSIX change-time tokens.
    strong = cache != "immutable" or os.name != "posix"
    native = json.loads((root / "manifest.json").read_text()).get("format") == NATIVE_FORMAT
    expected = {
        ("inspect", name): 2 if name == "manifest.json" or native or cache is None else 1
        for name in files
    }
    if strong:
        expected.update({(phase, name): 1 for phase in ("guard1", "guard2") for name in files})
    assert Counter((row["phase"], row["path"]) for row in reads) == expected
    assert sum(row["bytes_read"] for row in reads) == sum(
        count * files[name] for (_, name), count in expected.items()
    )


@pytest.mark.parametrize("stage", ["peak", "attribution"])
def test_default_cli_report_retains_both_strong_guards(artifact, tmp_path, stage):
    result, evidence = run_probe(
        tmp_path,
        artifact,
        ["report", "peak-memory", str(artifact), "--device", "0", "--json"],
        stage=stage,
    )
    assert result.returncode != 0
    assert "content changed during operation" in result.stderr
    assert not result.stdout.strip()  # Never return a mixed-generation report.
    assert evidence["guards"] == (1 if stage == "peak" else 2)
    assert evidence["mutated"] == "device_1/slice_00000.db"
    assert any(row["phase"] == f"guard{evidence['guards']}" for row in evidence["hash_reads"])


@pytest.mark.parametrize("manifest_path", [False, True], ids=["directory", "manifest"])
def test_cli_tab_completion_reads_only_focused_manifest(artifact, tmp_path, manifest_path):
    focus = tmp_path / ".pt-snap/focus.json"
    focus.parent.mkdir()
    target = artifact / "manifest.json" if manifest_path else artifact
    focus.write_text(json.dumps({"db_path": str(target)}))
    result, evidence = run_probe(tmp_path, artifact, [], completion=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines() == ["0", "1"]
    assert evidence["sqlite_opens"] == 0
    assert evidence["member_opens"] == 0
    assert evidence["hash_reads"] == []
    assert evidence["guards"] == 0
