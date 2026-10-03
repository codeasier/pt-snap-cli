from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest
import yaml

AUDIT_PATH = Path(__file__).resolve().parents[1] / ".github/scripts/audit_wheel.py"


@pytest.fixture
def audit():
    spec = importlib.util.spec_from_file_location("audit_wheel", AUDIT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.audit_wheel


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "src"
    for name, content in {
        "__init__.py": b"",
        "current.py": b"VALUE = 1\n",
        "query/templates/root.yaml": b"name: root\n",
        "query/templates/memory/current.yaml": b"name: current\n",
        "bundled_skills/example/SKILL.md": b"# Skill\n",
        "snapshot/LICENSE": b"MIT\n",
        "snapshot/PROVENANCE.md": b"Evidence\n",
    }.items():
        path = root / "pt_snap_cli" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    return root


def _wheel(source, path, *, changed=None, missing=()):
    entries = {
        file.relative_to(source).as_posix(): file.read_bytes()
        for file in source.rglob("*")
        if file.is_file()
    }
    entries.update(
        {
            "pt_snap_cli-1.0.dist-info/METADATA": b"Name: pt-snap-cli\nVersion: 1.0\n",
            "pt_snap_cli-1.0.dist-info/licenses/LICENSE": b"MIT\n",
            "pt_snap_cli/AGENTS.md": b"SCM-included documentation\n",
        }
    )
    entries.update(changed or {})
    with ZipFile(path, "w") as archive:
        for name, content in entries.items():
            if name not in missing:
                archive.writestr(name, content)
    return path


def test_clean_wheel_allows_generated_metadata_and_scm_documentation(audit, source, tmp_path):
    wheel = _wheel(source, tmp_path / "clean.whl")
    before = wheel.read_bytes()
    assert audit(wheel, source) == []
    assert wheel.read_bytes() == before


@pytest.mark.parametrize(
    "name",
    [
        "pt_snap_cli/arbitrary_retired.py",
        "pt_snap_cli/old_package/__init__.py",
        "unrelated_package/deleted.py",
    ],
)
def test_extra_python_modules_are_rejected_without_a_name_blacklist(audit, source, tmp_path, name):
    wheel = _wheel(source, tmp_path / "dirty.whl", changed={name: b"raise RuntimeError\n"})
    before = wheel.read_bytes()
    assert audit(wheel, source) == [f"Unexpected Python module: {name}"]
    assert wheel.read_bytes() == before


@pytest.mark.parametrize(
    ("name", "label"),
    [
        ("pt_snap_cli/current.py", "Python module"),
        ("pt_snap_cli/query/templates/memory/current.yaml", "resource"),
        ("pt_snap_cli/bundled_skills/example/SKILL.md", "resource"),
        ("pt_snap_cli/snapshot/LICENSE", "resource"),
        ("pt_snap_cli/snapshot/PROVENANCE.md", "resource"),
    ],
)
def test_missing_and_changed_contract_files_fail(audit, source, tmp_path, name, label):
    missing = _wheel(source, tmp_path / "missing.whl", missing=[name])
    assert audit(missing, source) == [f"Missing {label}: {name}"]
    changed = _wheel(source, tmp_path / "changed.whl", changed={name: b"stale content"})
    assert audit(changed, source) == [f"Content mismatch for {label}: {name}"]


def test_stale_resource_and_duplicate_member_fail(audit, source, tmp_path):
    name = "pt_snap_cli/query/templates/retired.yaml"
    wheel = _wheel(source, tmp_path / "stale.whl", changed={name: b"old"})
    assert audit(wheel, source) == [f"Unexpected resource: {name}"]
    with ZipFile(wheel, "a") as archive, pytest.warns(UserWarning, match="Duplicate name"):
        archive.writestr(name, b"old")
    assert audit(wheel, source) == [
        f"Duplicate wheel member: {name}",
        f"Unexpected resource: {name}",
    ]


def test_cli_reports_bad_artifact_and_invalid_source(source, tmp_path):
    wheel = tmp_path / "invalid.whl"
    wheel.write_bytes(b"not a zip")
    for root, expected in (
        (source, "File is not a zip file"),
        (tmp_path / "absent", "Expected source package"),
    ):
        result = subprocess.run(
            [sys.executable, str(AUDIT_PATH), "--wheel", str(wheel), "--source", str(root)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 1
        assert expected in result.stderr
        assert "No files were modified" in result.stderr


def test_repeated_setuptools_build_rejects_arbitrary_build_lib_residue(audit, source, tmp_path):
    # Exercise the real backend offline in a disposable project: no installation,
    # SCM version lookup, dependency download, or alteration of the checkout.
    (tmp_path / "pyproject.toml").write_text(
        '[build-system]\nrequires = ["setuptools", "wheel"]\n'
        'build-backend = "setuptools.build_meta"\n'
        '[project]\nname = "pt-snap-cli"\nversion = "1.0"\n'
        '[tool.setuptools.packages.find]\nwhere = ["src"]\n'
        "[tool.setuptools.package-data]\n"
        'pt_snap_cli = ["query/templates/*.yaml", "query/templates/*/*.yaml", '
        '"bundled_skills/**/*", "snapshot/LICENSE", "snapshot/PROVENANCE.md"]\n'
    )

    def build(directory):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from setuptools.build_meta import build_wheel; "
                f"build_wheel({str(directory)!r})",
            ],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stdout + result.stderr
        return next(directory.glob("*.whl"))

    clean = build(tmp_path / "clean-dist")
    assert audit(clean, source) == []
    stale = tmp_path / "build/lib/pt_snap_cli/unexpected_legacy/retired.py"
    stale.parent.mkdir(parents=True)
    stale.write_bytes(b"raise RuntimeError('must never execute')\n")
    dirty = build(tmp_path / "dirty-dist")
    result = subprocess.run(
        [sys.executable, str(AUDIT_PATH), "--wheel", str(dirty), "--source", str(source)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    assert "Unexpected Python module: pt_snap_cli/unexpected_legacy/retired.py" in result.stderr
    assert stale.read_bytes() == b"raise RuntimeError('must never execute')\n"
    assert audit(clean, source) == []


@pytest.mark.parametrize(
    ("workflow", "job", "build", "next_step"),
    [
        ("test.yml", "test", "Build wheel", "Clean-wheel Agent acceptance"),
        ("release.yml", "build", "Build sdist and wheel", "Upload build artifacts"),
    ],
)
def test_actual_built_wheel_is_audited_before_acceptance_or_upload(workflow, job, build, next_step):
    path = Path(".github/workflows") / workflow
    steps = yaml.load(path.read_text(), Loader=yaml.BaseLoader)["jobs"][job]["steps"]
    names = [step.get("name") for step in steps]
    index = names.index("Audit wheel contents against source")
    assert names.index(build) < index < names.index(next_step)
    audit_step = steps[index]
    assert 'Path("dist").glob("*.whl")' in audit_step["run"]
    assert "assert len(wheels) == 1" in audit_step["run"]
    assert 'python .github/scripts/audit_wheel.py --wheel "$WHEEL"' in audit_step["run"]
    assert audit_step.get("if") == steps[names.index(build)].get("if")
    assert "continue-on-error" not in audit_step
