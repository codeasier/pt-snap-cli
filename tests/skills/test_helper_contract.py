from pathlib import Path

SKILL_PATH = Path("skills/pt-snap-helper/SKILL.md")
AGENTS_PATH = Path("skills/AGENTS.md")
CLI_PATH = Path("src/pt_snap_cli/cli.py")

ROUTED_SKILLS = (
    "pt-snap-setup",
    "pt-snap-ascend-npu-collect",
    "pt-snap-memory-leak",
    "pt-snap-memory-peak-breakdown",
    "pt-snap-memory-fragmentation",
)


def _skill() -> str:
    return SKILL_PATH.read_text(encoding="utf-8")


def test_helper_skill_frontmatter_and_index() -> None:
    skill = _skill()
    agents = AGENTS_PATH.read_text(encoding="utf-8")

    assert skill.startswith("---\nname: pt-snap-helper\n")
    assert "read-only navigator" in skill
    assert "pt-snap-helper/SKILL.md" in agents
    assert "Routes by user goal and input type" in agents


def test_helper_skill_checks_availability_and_restart() -> None:
    skill = _skill()

    assert "pt-snap skill list --json" in skill
    assert "pt-snap skill install pt-snap-helper --json" in skill
    assert "Do not run install or upgrade from this skill." in skill
    assert (
        "Restart the agent after install, upgrade, or uninstall so the skill "
        "change takes effect."
    ) in skill


def test_helper_skill_uses_current_json_capability() -> None:
    skill = _skill()
    cli = CLI_PATH.read_text(encoding="utf-8")

    assert "Prefer `--json` where supported" in skill
    assert "pt-snap metadata '<db_path>' --json" in skill
    assert "pt-snap report peak-memory '<db_path>' --device <device_id> --json" in skill
    assert "Do not add `--json` to `query`, `focus`, `import`, `split`, or `config`." in skill
    assert "Do not invent a global `--json` flag on `pt-snap`." in skill
    assert "pt-snap query --json" not in skill
    assert "pt-snap import --json" not in skill
    assert "pt-snap focus --json" not in skill
    assert '@app.command("query")' in cli
    assert "json_output" in cli


def test_helper_skill_routes_by_goal_and_input_type() -> None:
    skill = _skill()

    assert "## Routing matrix" in skill
    assert "Existing SnapshotDB" in skill
    assert "Only pickle" in skill
    assert "`pt-snap` missing" in skill
    assert "Need Ascend NPU capture" in skill
    for name in ROUTED_SKILLS:
        assert f"`{name}`" in skill
    assert "CSV, SVG, and other visualization files are not SnapshotDB input" in skill


def test_helper_skill_keeps_pickle_import_and_focus_as_handoffs() -> None:
    skill = _skill()

    assert "import is an independent trusted-input decision" in skill
    assert "Do not run `pt-snap import`." in skill
    assert "Do not run `pt-snap focus` with a database path." in skill
    assert "Do not persist focus" in skill
    assert "This helper must not run that command or change focus." in skill
    assert "pt-snap import <snapshot.pkl>" in skill
    assert "That command currently has no `--json` option." in skill
    assert "Do not run `pt-snap skill install`" in skill
