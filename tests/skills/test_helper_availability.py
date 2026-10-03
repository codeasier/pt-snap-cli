"""Availability instructions and the real CLI evidence used by the helper."""

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pt_snap_cli.cli import app

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "required_rule",
    [
        "`missing` means no copy was found in the inspected locations",
        "pt-snap skill list --dir '<skills_dir>' --json",
        "A readable `source_dir` is catalog content, not proof of installation or host loading",
        "If the host has already loaded the needed skill, hand off to it even when the default list says `missing`",
        "If the host cannot load the skill, pause the diagnostic handoff",
        "If the active copy is known to be outdated, request an upgrade and restart before diagnostic handoff",
        "Report the inspected directory/scope, its status, and host-loading evidence separately",
    ],
)
def test_helper_availability_decision_rules(required_rule: str) -> None:
    skill = (REPO_ROOT / "skills/pt-snap-helper/SKILL.md").read_text(encoding="utf-8")
    availability = skill.split("## Prerequisite: check skill availability", 1)[1].split(
        "## Prefer `--json` where supported", 1
    )[0]
    assert required_rule in " ".join(availability.split())


@pytest.mark.parametrize("custom_status", ["installed", "outdated", "missing"])
def test_custom_install_status_is_scoped_to_inspected_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, custom_status: str
) -> None:
    # Keep both default scopes and host overrides away from developer directories.
    home = tmp_path / "home"
    project = tmp_path / "project"
    home.mkdir()
    project.mkdir()
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.chdir(project)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.setenv("PT_SNAP_SKILLS_DIR", str(REPO_ROOT / "skills"))
    dest = tmp_path / "custom skills"
    runner = CliRunner()

    installed = runner.invoke(app, ["skill", "install", "--dir", str(dest), "--json"])
    assert installed.exit_code == 0, installed.output
    report = json.loads(installed.stdout)
    assert report["restart_required"] is True
    assert len(report["results"]) == 6
    assert {item["action"] for item in report["results"]} == {"installed"}
    needed = "pt-snap-memory-leak"
    skill_file = dest / needed / "SKILL.md"
    assert skill_file.is_file()
    if custom_status == "outdated":
        skill_file.write_text("older skill instructions\n", encoding="utf-8")
    elif custom_status == "missing":
        skill_file.unlink()
        skill_file.parent.rmdir()

    default = runner.invoke(app, ["skill", "list", "--json"])
    assert default.exit_code == 0, default.output
    default_skills = json.loads(default.stdout)["skills"]
    assert {item["status"] for item in default_skills} == {"missing"}
    for item in default_skills:
        assert (Path(item["source_dir"]) / "SKILL.md").is_file()
        assert all(location["host"] != "custom" for location in item["locations"])

    scoped = runner.invoke(app, ["skill", "list", "--dir", str(dest), "--json"])
    assert scoped.exit_code == 0, scoped.output
    scoped_skills = {item["name"]: item for item in json.loads(scoped.stdout)["skills"]}
    for name, item in scoped_skills.items():
        expected = custom_status if name == needed else "installed"
        assert item["status"] == expected
        assert item["locations"] == [
            {"host": "custom", "scope": "user", "path": str(dest / name), "status": expected}
        ]
    assert not list(home.iterdir())
    assert not list(project.iterdir())
