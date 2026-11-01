"""Exercise the coverage guard with real coverage databases, without running code."""

import importlib.util
from pathlib import Path

import pytest
from coverage import CoverageData


@pytest.fixture
def guard():
    path = Path(".github/scripts/check_critical_coverage.py")
    spec = importlib.util.spec_from_file_location("critical_coverage_guard", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_evidence(guard, root, *, missing=None, uncovered=None, branches=True):
    (root / "pyproject.toml").write_text(
        "[tool.coverage.run]\nbranch = true\n[tool.coverage.report]\nfail_under = 90\n",
        encoding="utf-8",
    )
    data = CoverageData(basename=str(root / ".coverage"))
    for relative in guard.CRITICAL_FLOORS:
        source = root / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("if flag:\n    result = 1\nelse:\n    result = 2\n", encoding="utf-8")
        if relative == missing:
            continue
        if branches:
            arcs = [(-1, 1), (1, 2), (2, -1)]
            if relative != uncovered:
                arcs.extend([(1, 4), (4, -1)])
            data.add_arcs({str(source): arcs})
        else:
            data.add_lines({str(source): [1, 2, 4]})
    data.write()


def test_critical_floor_inventory_preserves_existing_and_adds_risky_modules(guard):
    assert guard.CRITICAL_FLOORS == {
        "src/pt_snap_cli/core/snapshot_import_backend.py": 90,
        "src/pt_snap_cli/snapshot/simulate/simulated_caching_allocator.py": 88,
        "src/pt_snap_cli/snapshot/simulate/snapshot_mutator.py": 84,
        "src/pt_snap_cli/core/import_metadata_contract.py": 100,
        "src/pt_snap_cli/core/import_metadata.py": 90,
        "src/pt_snap_cli/core/split_service.py": 90,
        "src/pt_snap_cli/core/focus_service.py": 90,
        "src/pt_snap_cli/core/skill_service.py": 90,
        "src/pt_snap_cli/core/snapshot_cache.py": 90,
        "src/pt_snap_cli/snapshot/representation.py": 95,
    }


def test_guard_accepts_complete_branch_evidence(guard, tmp_path, capsys):
    write_evidence(guard, tmp_path)
    guard.check_coverage(tmp_path)
    output = capsys.readouterr().out
    assert output.count("100.0000%") == len(guard.CRITICAL_FLOORS)


def test_guard_rejects_missing_data_without_creating_it(guard, tmp_path):
    with pytest.raises(guard.CoverageGuardError, match="Missing coverage data"):
        guard.check_coverage(tmp_path)
    assert not (tmp_path / ".coverage").exists()


@pytest.mark.parametrize("failure", ["corrupt", "empty", "line-only"])
def test_guard_rejects_unusable_evidence(guard, tmp_path, failure):
    write_evidence(guard, tmp_path, branches=failure != "line-only")
    if failure == "corrupt":
        (tmp_path / ".coverage").write_bytes(b"not a coverage database")
    elif failure == "empty":
        (tmp_path / ".coverage").write_bytes(b"")
    with pytest.raises(guard.CoverageGuardError):
        guard.check_coverage(tmp_path)


@pytest.mark.parametrize("failure", ["unmeasured", "deleted", "no-statements", "below-floor"])
def test_one_critical_file_cannot_be_hidden_by_other_full_coverage(guard, tmp_path, failure):
    relative = "src/pt_snap_cli/core/focus_service.py"
    write_evidence(
        guard,
        tmp_path,
        missing=relative if failure == "unmeasured" else None,
        uncovered=relative if failure == "below-floor" else None,
    )
    if failure == "deleted":
        (tmp_path / relative).unlink()
    elif failure == "no-statements":
        (tmp_path / relative).write_text("# no executable source\n", encoding="utf-8")
    with pytest.raises(guard.CoverageGuardError, match="core/focus_service.py"):
        guard.check_coverage(tmp_path)


def test_guard_compares_unrounded_percentage(guard, tmp_path, monkeypatch):
    write_evidence(guard, tmp_path)
    real_report = guard.Coverage.report

    def almost_passes(coverage, **kwargs):
        if Path(kwargs["morfs"][0]).as_posix().endswith("core/focus_service.py"):
            return 89.9999
        return real_report(coverage, **kwargs)

    monkeypatch.setattr(guard.Coverage, "report", almost_passes)
    with pytest.raises(guard.CoverageGuardError, match="89.9999% is below 90%"):
        guard.check_coverage(tmp_path)


@pytest.mark.parametrize("failure", [False, True])
def test_command_exit_status_reflects_gate_result(guard, monkeypatch, capsys, failure):
    def check(root):
        assert root == Path(guard.__file__).resolve().parents[2]
        if failure:
            raise guard.CoverageGuardError("independent floor failed")

    monkeypatch.setattr(guard, "check_coverage", check)
    assert guard.main() == (1 if failure else 0)
    error = capsys.readouterr().err
    assert ("independent floor failed" in error) is failure
