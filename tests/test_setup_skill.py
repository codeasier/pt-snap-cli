from __future__ import annotations

import os
import subprocess
import venv
from pathlib import Path

import pytest

SKILL_PATH = Path("skills/pt-snap-setup/SKILL.md")


@pytest.mark.skipif(os.name == "nt", reason="POSIX venvs use interpreter symlinks")
def test_setup_skill_preserves_virtual_environment_interpreter_path(tmp_path: Path) -> None:
    environment = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True, symlinks=True).create(environment)
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
