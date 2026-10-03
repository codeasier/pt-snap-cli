from __future__ import annotations

import json
import os
import subprocess
import sys
import venv
from pathlib import Path

import pytest

SKILL_PATH = Path("skills/pt-snap-setup/SKILL.md")


@pytest.mark.skipif(os.name == "nt", reason="POSIX venvs use interpreter symlinks")
def test_setup_skill_preserves_virtual_environment_interpreter_path(tmp_path: Path) -> None:
    environment = tmp_path / "venv"
    venv.EnvBuilder(with_pip=False, symlinks=True).create(environment)
    candidate = environment / "bin" / "python"
    child_env = os.environ.copy()
    child_env.pop("__PYVENV_LAUNCHER__", None)

    executable = subprocess.run(
        [candidate, "-c", "import sys; print(sys.executable)"],
        check=True,
        capture_output=True,
        env=child_env,
        text=True,
    ).stdout.strip()
    selected_prefix = subprocess.run(
        [executable, "-c", "import sys; print(sys.prefix)"],
        check=True,
        capture_output=True,
        env=child_env,
        text=True,
    ).stdout.strip()
    base_prefix = subprocess.run(
        [os.path.realpath(executable), "-c", "import sys; print(sys.prefix)"],
        check=True,
        capture_output=True,
        env=child_env,
        text=True,
    ).stdout.strip()

    assert Path(selected_prefix) == environment
    assert Path(base_prefix) != environment

    skill = SKILL_PATH.read_text()
    assert '"<python_candidate>" -c "import sys; print(sys.executable)"' in skill
    assert "Never replace `<python_executable>` with its `realpath`" in skill


def _run_ownership_probe(selected: Path, cli: Path) -> list[str]:
    """Execute the shipped probe, not a test-only copy of its decision rule."""
    skill = SKILL_PATH.read_text()
    probe = skill.split("<<'PY'\n", 1)[1].split("\nPY\n", 1)[0]
    child_env = os.environ.copy()
    child_env.pop("__PYVENV_LAUNCHER__", None)
    return subprocess.run(
        [selected, "-", cli],
        input=probe,
        check=True,
        capture_output=True,
        env=child_env,
        text=True,
        timeout=20,
    ).stdout.splitlines()


@pytest.mark.skipif(os.name == "nt", reason="POSIX venvs use interpreter symlinks")
@pytest.mark.parametrize(
    ("selected_name", "cli_name", "matches"),
    [
        ("first", "first", True),
        ("first", "second", False),
        ("first", "base", False),
        ("base", "first", False),
        ("first", "alias", True),
        ("alias", "first", True),
    ],
)
def test_setup_ownership_distinguishes_environments_sharing_an_interpreter(
    tmp_path: Path, selected_name: str, cli_name: str, matches: bool
) -> None:
    for name in ("first", "second"):
        venv.EnvBuilder(with_pip=False, symlinks=True).create(tmp_path / name)
    (tmp_path / "alias").symlink_to(tmp_path / "first", target_is_directory=True)
    interpreters = {
        name: tmp_path / name / "bin" / "python" for name in ("first", "second", "alias")
    }
    interpreters["base"] = interpreters["first"].resolve()
    selected, cli = interpreters[selected_name], interpreters[cli_name]
    # This is the old false-positive condition, shared by every test case.
    assert selected.resolve() == cli.resolve()

    evidence, status = _run_ownership_probe(selected, cli)
    identities = json.loads(evidence)
    assert identities["selected"]["executable"] == str(selected)
    assert identities["cli"]["executable"] == str(cli)
    if selected_name != cli_name:
        assert identities["selected"]["prefix"] != identities["cli"]["prefix"]
    assert status == (
        "matches selected Python" if matches else "CLI belongs to another Python environment"
    )


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable launcher fixture")
@pytest.mark.parametrize("failure", ["missing", "invalid-json", "nonzero"])
def test_setup_ownership_probe_failure_remains_unverified(tmp_path: Path, failure: str) -> None:
    cli = tmp_path / "broken-python"
    if failure != "missing":
        cli.write_text(
            f"#!{sys.executable}\n"
            + ("print('not JSON')\n" if failure == "invalid-json" else "exit(1)\n")
        )
        cli.chmod(0o755)
    output = _run_ownership_probe(Path(sys.executable), cli)
    assert output[0].startswith("CLI ownership unverified:")
    assert not any("matches selected Python" in line for line in output)


def test_setup_ownership_contract_requires_identity_and_preserves_shebang_semantics() -> None:
    skill = SKILL_PATH.read_text()
    assert "resolve `<name>` in the current `PATH` without dereferencing symlinks" in skill
    assert "including `env -S`" in skill
    assert "do not drop arguments and probe a different invocation" in skill
    ready_definition = next(line for line in skill.splitlines() if line.startswith("- `ready`:"))
    assert "CLI help succeeds" in ready_definition
    assert "normalized `sys.executable` and `sys.prefix`" in ready_definition
